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


def sample_alert(index):
    return json.loads(ALERTS_PATH.read_text())[index]


def start(graph, raw_alert, thread):
    config = {"configurable": {"thread_id": thread}}
    state = {"incident_id": thread, "raw_alert": raw_alert, "audit_log": [], "errors": []}
    return graph.invoke(state, config), config


def agents(result):
    return [entry["agent"] for entry in result["audit_log"]]


def approve(decision, comment=""):
    return Command(resume={"decision": decision, "reviewer": "tester", "comment": comment})


def test_low_risk_incident_runs_to_completion_without_human():
    infra = SimulatedInfrastructure()
    graph = build_graph(llm_proposing(*CLEANUP), infra, no_history)

    result, _ = start(graph, sample_alert(1), "INC-LOW")

    assert "__interrupt__" not in result
    assert result["status"] == "verifying"
    assert infra.state["hosts"]["log-server-02"]["disk_usage_percent"] < 60
    assert agents(result) == ["alert_ingestion", "correlation", "hypothesis", "execution"]


def test_high_risk_incident_pauses_before_any_change():
    infra = SimulatedInfrastructure()
    graph = build_graph(llm_proposing(*ROLLBACK), infra, no_history)

    result, config = start(graph, sample_alert(0), "INC-HIGH-1")

    assert "__interrupt__" in result
    request = result["__interrupt__"][0].value
    assert request["proposed_action"] == "rollback_deployment"
    assert request["risk_tier"] == "high"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"
    assert graph.get_state(config).next == ("approval_gate",)


def test_approved_action_executes_after_resume():
    infra = SimulatedInfrastructure()
    graph = build_graph(llm_proposing(*ROLLBACK), infra, no_history)
    _, config = start(graph, sample_alert(0), "INC-HIGH-2")

    result = graph.invoke(approve("approved", "looks right"), config)

    assert result["status"] == "verifying"
    assert result["approval"]["reviewer"] == "tester"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.13.2"
    assert agents(result)[-2:] == ["approval_gate", "execution"]


def test_rejected_action_is_not_executed():
    infra = SimulatedInfrastructure()
    graph = build_graph(llm_proposing(*ROLLBACK), infra, no_history)
    _, config = start(graph, sample_alert(0), "INC-HIGH-3")

    result = graph.invoke(approve("rejected", "wait for the team"), config)

    assert result["status"] == "rejected"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"
    assert "execution" not in agents(result)


def test_unclear_human_response_counts_as_rejection():
    infra = SimulatedInfrastructure()
    graph = build_graph(llm_proposing(*ROLLBACK), infra, no_history)
    _, config = start(graph, sample_alert(0), "INC-HIGH-4")

    result = graph.invoke(approve("maybe"), config)

    assert result["status"] == "rejected"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"


def test_ingestion_failure_stops_the_pipeline():
    llm = FakeLLM()
    graph = build_graph(llm, SimulatedInfrastructure(), no_history)

    result, _ = start(graph, {"source": "nagios", "payload": {}}, "INC-BAD")

    assert result["status"] == "failed"
    assert agents(result) == ["alert_ingestion"]
    assert llm.calls == []


def test_llm_failure_pages_a_human_through_escalation():
    infra = SimulatedInfrastructure()
    before = deepcopy(infra.state)
    graph = build_graph(FakeLLM("not json", "still not json"), infra, no_history)

    result, _ = start(graph, sample_alert(0), "INC-LLM-FAIL")

    assert "__interrupt__" not in result
    assert result["status"] == "escalated"
    assert result["execution_result"]["action"] == "escalate_to_human"
    assert infra.state == before