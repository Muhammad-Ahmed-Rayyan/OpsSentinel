import json
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


def proposal(action, parameters):
    return json.dumps(
        {
            "hypotheses": [{"cause": "Bad release", "confidence": 0.9, "evidence": ["e"]}],
            "proposed_action": {"action": action, "parameters": parameters, "rationale": "test"},
        }
    )


def no_history(query):
    return []


def sample_alert(index):
    return json.loads(ALERTS_PATH.read_text())[index]


def start(graph, raw_alert, thread):
    config = {"configurable": {"thread_id": thread}}
    state = {"incident_id": thread, "raw_alert": raw_alert, "audit_log": [], "errors": []}
    return graph.invoke(state, config), config


def test_duplicate_alert_during_an_open_incident_is_suppressed_without_calling_the_llm(tmp_path):
    llm = FakeLLM(proposal(*ROLLBACK))
    graph = build_graph(
        llm, SimulatedInfrastructure(), no_history, reports_dir=tmp_path, learn_fn=lambda r: None
    )

    first, _ = start(graph, sample_alert(0), "INC-1")  # pauses at the approval gate
    assert first["__interrupt__"][0].value["kind"] == "approval"

    second, _ = start(graph, sample_alert(0), "INC-2")  # same alert while INC-1 is open

    assert second["status"] == "suppressed"
    assert len(llm.calls) == 1
    assert not (tmp_path / "INC-2.md").exists()


def test_same_alert_after_the_incident_closed_opens_a_new_incident(tmp_path):
    llm = FakeLLM(proposal(*CLEANUP), proposal(*CLEANUP))
    graph = build_graph(
        llm, SimulatedInfrastructure(), no_history, reports_dir=tmp_path, learn_fn=lambda r: None
    )

    _, config = start(graph, sample_alert(1), "INC-1")
    graph.invoke(
        Command(resume={"decision": "skipped", "reviewer": "tester"}), config
    )  # INC-1 finishes and is closed

    second, _ = start(graph, sample_alert(1), "INC-2")

    assert second["__interrupt__"][0].value["kind"] == "review"
    assert len(llm.calls) == 2