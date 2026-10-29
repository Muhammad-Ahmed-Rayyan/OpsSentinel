import json
from pathlib import Path

from helpers import FakeLLM
from langgraph.types import Command

from opssentinel.graph import build_graph
from opssentinel.tools.remediation import SimulatedInfrastructure

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"

PRIMARY = {
    "action": "rollback_deployment",
    "parameters": {"service": "checkout-api", "target_version": "v2.13.2"},
    "rationale": "Matches past incident",
}
RESTART = {
    "action": "restart_service",
    "parameters": {"service": "checkout-api"},
    "rationale": "Clears bad state",
}
CACHE = {
    "action": "clear_cache",
    "parameters": {"service": "checkout-api"},
    "rationale": "Possible stale data",
}


def options_response():
    return json.dumps(
        {
            "hypotheses": [{"cause": "Bad release", "confidence": 0.9, "evidence": ["e"]}],
            "proposed_action": PRIMARY,
            "alternatives": [RESTART, CACHE],
        }
    )


def no_history(query):
    return []


def start(tmp_path, thread):
    infra, learned = SimulatedInfrastructure(), []
    graph = build_graph(
        FakeLLM(options_response()), infra, no_history, reports_dir=tmp_path, learn_fn=learned.append
    )
    config = {"configurable": {"thread_id": thread}}
    raw_alert = json.loads(ALERTS_PATH.read_text())[0]
    state = {"incident_id": thread, "raw_alert": raw_alert, "audit_log": [], "errors": []}
    return graph, infra, learned, graph.invoke(state, config), config


def choose(option):
    return Command(
        resume={"decision": "approved", "option": option, "reviewer": "tester", "comment": "my call"}
    )


def test_approval_request_lists_the_alternatives(tmp_path):
    _, _, _, result, _ = start(tmp_path, "INC-OPT-1")

    request = result["__interrupt__"][0].value
    assert request["kind"] == "approval"
    assert len(request["alternatives"]) == 2
    assert "option 2" in request["alternatives"][0]
    assert "restart_service" in request["alternatives"][0]
    assert "high risk" in request["alternatives"][0]


def test_choosing_an_alternative_runs_it_instead_of_the_primary(tmp_path):
    graph, infra, learned, _, config = start(tmp_path, "INC-OPT-2")

    result = graph.invoke(choose(2), config)

    service = infra.state["services"]["checkout-api"]
    assert service.get("restarts") == 1
    assert service["version"] == "v2.14.0"  # the primary rollback did not run
    assert result["proposed_action"]["action"] == "restart_service"
    assert result["approval"]["option"] == 2
    assert result["approval"]["original_action"] == "rollback_deployment"
    assert result["status"] == "escalated"
    assert "chose option 2 instead of rollback_deployment" in result["report"]
    assert "Alternatives considered" in result["report"]
    assert learned == []


def test_an_out_of_range_choice_is_a_rejection(tmp_path):
    graph, infra, _, _, config = start(tmp_path, "INC-OPT-3")

    result = graph.invoke(choose(7), config)

    assert result["status"] == "rejected"
    assert infra.state["services"]["checkout-api"]["version"] == "v2.14.0"
    assert "restarts" not in infra.state["services"]["checkout-api"]