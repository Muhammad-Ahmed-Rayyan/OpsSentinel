import json

from helpers import FakeLLM, correlated_state

from opssentinel.agents.hypothesis import make_hypothesis_agent

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
ESCALATE = {"action": "escalate_to_human", "parameters": {}, "rationale": "Low confidence"}


def response(alternatives=None):
    body = {
        "hypotheses": [{"cause": "Bad release", "confidence": 0.9, "evidence": ["e"]}],
        "proposed_action": PRIMARY,
    }
    if alternatives is not None:
        body["alternatives"] = alternatives
    return json.dumps(body)


def no_history(query):
    return []


def run(llm_response):
    return make_hypothesis_agent(FakeLLM(llm_response), no_history)(correlated_state(0))


def ranking_detail(update):
    return next(e for e in update["audit_log"] if e["action"] == "hypotheses_ranked")["detail"]


def test_alternatives_are_kept_in_order_with_catalog_risk_tiers():
    update = run(response([RESTART, CACHE]))

    assert update["status"] == "hypothesized"
    assert [a["action"] for a in update["alternatives"]] == ["restart_service", "clear_cache"]
    assert [a["risk_tier"] for a in update["alternatives"]] == ["high", "low"]


def test_llm_cannot_lower_an_alternatives_risk_tier():
    update = run(response([{**RESTART, "risk_tier": "low"}]))

    assert update["alternatives"][0]["risk_tier"] == "high"


def test_invalid_alternatives_are_dropped_without_failing_the_analysis():
    bad = [
        {"action": "delete_database", "parameters": {}, "rationale": "x"},  # not in the catalog
        {"action": "restart_service", "parameters": {}, "rationale": "x"},  # missing parameter
        "restart the thing",  # not an object
        RESTART,
    ]
    update = run(response(bad))

    assert update["status"] == "hypothesized"
    assert update["errors"] == []
    assert [a["action"] for a in update["alternatives"]] == ["restart_service"]
    assert "dropped 3" in ranking_detail(update)


def test_alternative_that_repeats_the_primary_is_dropped():
    update = run(response([PRIMARY, RESTART]))

    assert [a["action"] for a in update["alternatives"]] == ["restart_service"]
    assert "dropped 1" in ranking_detail(update)


def test_at_most_two_alternatives_are_kept():
    update = run(response([RESTART, CACHE, ESCALATE]))

    assert len(update["alternatives"]) == 2
    assert "dropped 1" in ranking_detail(update)


def test_response_without_alternatives_is_still_valid():
    update = run(response())

    assert update["status"] == "hypothesized"
    assert update["alternatives"] == []