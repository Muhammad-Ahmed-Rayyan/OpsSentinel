import json
from pathlib import Path

from helpers import FakeLLM
from langgraph.types import Command

from opssentinel.graph import build_graph
from opssentinel.tools.remediation import SimulatedInfrastructure

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"

ROLLBACK = ("rollback_deployment", {"service": "checkout-api", "target_version": "v2.13.2"})
CLEANUP = ("cleanup_old_logs", {"host": "log-server-02", "path": "/var/log"})


class RecordingNotifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)

    @property
    def kinds(self):
        return [message["kind"] for message in self.messages]


class BrokenNotifier:
    def send(self, message):
        raise OSError("webhook down")


def proposal_response(action, parameters):
    return json.dumps(
        {
            "hypotheses": [{"cause": "Bad release", "confidence": 0.9, "evidence": ["e"]}],
            "proposed_action": {"action": action, "parameters": parameters, "rationale": "test"},
        }
    )


def no_history(query):
    return []


def build(llm, notifier, tmp_path):
    return build_graph(
        llm,
        SimulatedInfrastructure(),
        no_history,
        reports_dir=tmp_path,
        learn_fn=lambda record: None,
        notifier=notifier,
    )


def start(graph, index, thread):
    config = {"configurable": {"thread_id": thread}}
    raw_alert = json.loads(ALERTS_PATH.read_text())[index]
    state = {"incident_id": thread, "raw_alert": raw_alert, "audit_log": [], "errors": []}
    return graph.invoke(state, config), config


def test_approval_request_is_notified_once_even_though_the_gate_resumes(tmp_path):
    notifier = RecordingNotifier()
    graph = build(FakeLLM(proposal_response(*ROLLBACK)), notifier, tmp_path)
    _, config = start(graph, 0, "INC-N-1")
    assert notifier.kinds == ["approval"]

    graph.invoke(Command(resume={"decision": "approved", "reviewer": "tester"}), config)
    # Resuming re-ran the gate, but the approval request was not sent a second time.
    assert notifier.kinds == ["approval", "review"]

    graph.invoke(Command(resume={"decision": "confirmed", "reviewer": "tester"}), config)
    assert notifier.kinds == ["approval", "review"]


def test_low_risk_incident_notifies_only_for_the_review(tmp_path):
    notifier = RecordingNotifier()
    graph = build(FakeLLM(proposal_response(*CLEANUP)), notifier, tmp_path)

    start(graph, 1, "INC-N-2")

    assert notifier.kinds == ["review"]


def test_escalated_incident_notifies_the_on_call_engineer(tmp_path):
    notifier = RecordingNotifier()
    graph = build(FakeLLM("not json", "still not json"), notifier, tmp_path)

    result, _ = start(graph, 0, "INC-N-3")

    assert result["status"] == "escalated"
    assert notifier.kinds == ["escalation"]
    message = notifier.messages[0]
    assert message["incident_id"] == "INC-N-3"
    assert "HighErrorRate" in message["alert"]
    assert message["reasons"]
    assert any(entry["action"] == "human_notified" for entry in result["audit_log"])


def test_rejected_incident_does_not_page_anyone(tmp_path):
    notifier = RecordingNotifier()
    graph = build(FakeLLM(proposal_response(*ROLLBACK)), notifier, tmp_path)
    _, config = start(graph, 0, "INC-N-4")

    result = graph.invoke(Command(resume={"decision": "rejected", "reviewer": "tester"}), config)

    assert result["status"] == "rejected"
    assert notifier.kinds == ["approval"]


def test_notification_failure_does_not_stop_the_incident(tmp_path):
    graph = build(FakeLLM(proposal_response(*CLEANUP)), BrokenNotifier(), tmp_path)

    result, config = start(graph, 1, "INC-N-5")

    assert "__interrupt__" in result  # the review still pauses for a human
    errors = graph.get_state(config).values["errors"]
    assert any("notification failed" in error["error"] for error in errors)

    result = graph.invoke(Command(resume={"decision": "confirmed", "reviewer": "tester"}), config)
    assert result["status"] == "resolved"