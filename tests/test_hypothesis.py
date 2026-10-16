import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.hypothesis import make_hypothesis_agent
from opssentinel.agents.ingestion import ingest_alert

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


class FakeLLM:
    """Returns canned responses in order and records the prompts it receives."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


class BrokenLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        raise RuntimeError("429 rate limited")


def fake_search(query):
    return [
        {
            "id": "PM-001",
            "title": "Checkout 5xx spike after payment refactor release",
            "root_cause": "Null handling bug introduced by the latest release",
            "remediation_action": "rollback_deployment",
            "resolution": "Rolled back; recovered in 6 minutes",
        }
    ]


def failing_search(query):
    raise RuntimeError("chroma down")


def correlated_state(index: int) -> dict:
    with open(ALERTS_PATH) as f:
        raw = json.load(f)[index]
    state = {"incident_id": "INC-TEST", "raw_alert": raw, "audit_log": [], "errors": []}
    for node in (ingest_alert, correlate_incident):
        state = {**state, **node(state)}
    return state


def report(action, parameters, confidence=0.9, **extra):
    return json.dumps(
        {
            "hypotheses": [
                {
                    "cause": "Bad release",
                    "confidence": confidence,
                    "evidence": ["deployment 9 min before alert"],
                }
            ],
            "proposed_action": {
                "action": action,
                "parameters": parameters,
                "rationale": "Matches past incident",
            },
            **extra,
        }
    )


ROLLBACK = report("rollback_deployment", {"service": "checkout-api", "target_version": "v2.13.2"})

BAD_RESPONSES = [
    "I think the deployment is to blame.",
    report("delete_database", {}),
    report("rollback_deployment", {"service": "checkout-api"}),
    report(
        "rollback_deployment",
        {"service": "checkout-api", "target_version": "v2.13.2"},
        confidence=85,
    ),
]


def test_successful_hypothesis_updates_state():
    llm = FakeLLM(ROLLBACK)
    update = make_hypothesis_agent(llm, fake_search)(correlated_state(0))

    assert update["status"] == "hypothesized"
    assert update["hypotheses"][0]["cause"] == "Bad release"
    assert update["proposed_action"]["action"] == "rollback_deployment"
    assert update["proposed_action"]["parameters"]["target_version"] == "v2.13.2"
    assert update["risk_tier"] == "high"
    assert len(llm.calls) == 1
    user_prompt = llm.calls[0][1].content
    assert "v2.14.0" in user_prompt
    assert "PM-001" in user_prompt


def test_markdown_fenced_json_is_accepted():
    llm = FakeLLM("```json\n" + ROLLBACK + "\n```")
    update = make_hypothesis_agent(llm, fake_search)(correlated_state(0))

    assert update["status"] == "hypothesized"


@pytest.mark.parametrize("bad_response", BAD_RESPONSES)
def test_invalid_output_is_retried_with_feedback(bad_response):
    llm = FakeLLM(bad_response, ROLLBACK)
    update = make_hypothesis_agent(llm, fake_search)(correlated_state(0))

    assert update["status"] == "hypothesized"
    assert len(llm.calls) == 2
    assert "invalid" in llm.calls[1][-1].content.lower()


def test_two_invalid_outputs_escalate_to_human():
    llm = FakeLLM("not json", "still not json")
    update = make_hypothesis_agent(llm, fake_search)(correlated_state(0))

    assert update["status"] == "escalated"
    assert update["proposed_action"]["action"] == "escalate_to_human"
    assert update["risk_tier"] == "low"
    assert update["hypotheses"] == []
    assert len(update["errors"]) == 1
    assert len(llm.calls) == 2


def test_llm_failure_escalates_without_retry():
    llm = BrokenLLM()
    update = make_hypothesis_agent(llm, fake_search)(correlated_state(0))

    assert update["status"] == "escalated"
    assert llm.calls == 1
    assert "LLM call failed" in update["errors"][0]["error"]


def test_knowledge_base_failure_does_not_stop_analysis():
    llm = FakeLLM(ROLLBACK)
    update = make_hypothesis_agent(llm, failing_search)(correlated_state(0))

    assert update["status"] == "hypothesized"
    assert len(update["errors"]) == 1
    assert "knowledge base unavailable" in update["errors"][0]["error"]


def test_low_risk_action_for_disk_incident():
    response = report("cleanup_old_logs", {"host": "log-server-02", "path": "/var/log"})
    update = make_hypothesis_agent(FakeLLM(response), fake_search)(correlated_state(1))

    assert update["status"] == "hypothesized"
    assert update["risk_tier"] == "low"


def test_risk_tier_comes_from_catalog_not_llm():
    response = report(
        "rollback_deployment",
        {"service": "checkout-api", "target_version": "v2.13.2"},
        risk_tier="low",
    )
    update = make_hypothesis_agent(FakeLLM(response), fake_search)(correlated_state(0))

    assert update["risk_tier"] == "high"


def test_missing_context_fails_without_crashing():
    llm = FakeLLM()
    update = make_hypothesis_agent(llm, fake_search)(
        {"incident_id": "INC-X", "audit_log": [], "errors": []}
    )

    assert update["status"] == "failed"
    assert update["errors"][0]["agent"] == "hypothesis"
    assert llm.calls == []