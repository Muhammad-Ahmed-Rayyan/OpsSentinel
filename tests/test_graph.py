import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from langgraph.types import Command

from opssentinel.graph import build_graph
from opssentinel.tools.remediation import SimulatedInfrastructure

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"

ROLLBACK = ("rollback_deployment", {"service": "checkout-api", "target_version": "v2.13.2"})
CLEANUP = ("cleanup_old_logs", {"host": "log-server-02", "path": "/var/log"})


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


class StubbornInfra(SimulatedInfrastructure):
    """Accepts the cleanup but does not actually free any space."""

    def cleanup_old_logs(self, host, path):
        return {"message": "cleanup ran"}


def llm_proposing(action, parameters):
    return FakeLLM(
        json.dumps(
            {
                "hypotheses": [{"cause": "Bad release", "confidence": 0.9, "evidence": ["e"]}],
                "proposed_action": {"action": action, "parameters": parameters, "rationale": "test"},
            }
        )
    )


def no_history(query):
    return []


def make_graph(llm, infra, tmp_path, learned):
    return build_graph(llm, infra, no_history, reports_dir=tmp_path, learn_fn=learned.append)


def sample_alert(index):
    return json.loads(ALERTS_PATH.read_text())[index]


def start(graph, raw_alert, thread):
    config = {"configurable": {"thread_id": thread}}
    state = {"incident_id": thread, "raw_alert": raw_alert, "audit_log": [], "errors": []}
    return graph.invoke(state, config), config


def agents(result):
    """Agent names in order, with consecutive repeats collapsed."""
    names = []
    for entry in result["audit_log"]:
        if not names or names[-1] != entry["agent"]:
            names.append(entry["agent"])
    return names


def decision(value, comment=""):
    return Command(resume={"decision": value, "reviewer": "tester", "comment": comment})


def test_low_risk_incident_runs_to_resolution_without_human(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    graph = make_graph(llm_proposing(*CLEANUP), infra, tmp_path, learned)

    result, _ = start(graph, sample_alert(1), "INC-LOW")

    assert "__interrupt__" not in result
    assert result["status"] == "resolved"
    assert infra.state["hosts"]["log-server-02"]["disk_usage_percent"] < 60
    assert agents(result) == [
        "alert_ingestion", "correlation", "hypothesis", "execution", "verification", "reporting",
    ]
    assert (tmp_path / "INC-LOW.md").exists()
    assert [record["id"] for record in learned] == ["PM-INC-LOW"]


def test_high_risk_incident_pauses_before_any_change(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    graph = make_graph(llm_proposing(*ROLLBACK), infra, tmp_path, learned)

    result, config = start(graph, sample_alert(0), "INC-HIGH-1")

    assert "__interrupt__" in result
    request = result["__interrupt__"][0].value
    assert request["proposed_action"] == "rollback_deployment"
    assert request["risk_tier"] == "high"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"
    assert graph.get_state(config).next == ("approval_gate",)
    assert learned == []


def test_approved_action_is_executed_verified_and_learned(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    graph = make_graph(llm_proposing(*ROLLBACK), infra, tmp_path, learned)
    _, config = start(graph, sample_alert(0), "INC-HIGH-2")

    result = graph.invoke(decision("approved", "looks right"), config)

    assert result["status"] == "resolved"
    assert result["approval"]["reviewer"] == "tester"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.13.2"
    assert agents(result)[-4:] == ["approval_gate", "execution", "verification", "reporting"]
    assert learned[0]["approved_by"] == "tester"


def test_rejected_action_is_reported_but_not_executed_or_learned(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    graph = make_graph(llm_proposing(*ROLLBACK), infra, tmp_path, learned)
    _, config = start(graph, sample_alert(0), "INC-HIGH-3")

    result = graph.invoke(decision("rejected", "wait for the team"), config)

    assert result["status"] == "rejected"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"
    assert "execution" not in agents(result)
    assert agents(result)[-1] == "reporting"
    assert "rejected" in result["report"]
    assert learned == []


def test_unclear_human_response_counts_as_rejection(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    graph = make_graph(llm_proposing(*ROLLBACK), infra, tmp_path, learned)
    _, config = start(graph, sample_alert(0), "INC-HIGH-4")

    result = graph.invoke(decision("maybe"), config)

    assert result["status"] == "rejected"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"


def test_ingestion_failure_is_reported_without_calling_the_llm(tmp_path):
    llm, learned = FakeLLM(), []
    graph = make_graph(llm, SimulatedInfrastructure(), tmp_path, learned)

    result, _ = start(graph, {"source": "nagios", "payload": {}}, "INC-BAD")

    assert result["status"] == "failed"
    assert agents(result) == ["alert_ingestion", "reporting"]
    assert llm.calls == []
    assert (tmp_path / "INC-BAD.md").exists()


def test_llm_failure_pages_a_human_and_is_reported(tmp_path):
    infra, learned = SimulatedInfrastructure(), []
    before = deepcopy(infra.state)
    graph = make_graph(FakeLLM("not json", "still not json"), infra, tmp_path, learned)

    result, _ = start(graph, sample_alert(0), "INC-LLM-FAIL")

    assert "__interrupt__" not in result
    assert result["status"] == "escalated"
    assert result["execution_result"]["action"] == "escalate_to_human"
    assert agents(result) == [
        "alert_ingestion", "correlation", "hypothesis", "execution", "reporting",
    ]
    assert infra.state == before
    assert learned == []


def test_fix_that_does_not_work_is_escalated_and_not_learned(tmp_path):
    infra, learned = StubbornInfra(), []
    graph = make_graph(llm_proposing(*CLEANUP), infra, tmp_path, learned)

    result, _ = start(graph, sample_alert(1), "INC-STUBBORN")

    assert result["status"] == "escalated"
    assert result["verification"]["verified"] is False
    assert "verification" in agents(result)
    assert agents(result)[-1] == "reporting"
    assert learned == []