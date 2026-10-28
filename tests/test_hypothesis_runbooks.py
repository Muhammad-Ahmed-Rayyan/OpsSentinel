from helpers import FakeLLM, correlated_state, rollback_response

from opssentinel.agents.hypothesis import make_hypothesis_agent

RUNBOOK = {
    "id": "RB-001",
    "title": "Roll back a bad deployment",
    "action": "rollback_deployment",
    "steps": "Confirm a recent deployment | Roll back | Re-check the error rate",
    "cautions": "Do not roll back after an incompatible database migration",
}


def no_history(query):
    return []


def runbooks_found(query):
    return [RUNBOOK]


def runbooks_down(query):
    raise RuntimeError("chroma down")


def test_runbooks_are_included_in_the_prompt():
    llm = FakeLLM(rollback_response())

    update = make_hypothesis_agent(llm, no_history, runbook_fn=runbooks_found)(correlated_state(0))

    prompt = llm.calls[0][1].content
    assert update["status"] == "hypothesized"
    assert "RB-001" in prompt
    assert "incompatible database migration" in prompt


def test_runbook_failure_does_not_stop_the_analysis():
    llm = FakeLLM(rollback_response())

    update = make_hypothesis_agent(llm, no_history, runbook_fn=runbooks_down)(correlated_state(0))

    assert update["status"] == "hypothesized"
    assert len(update["errors"]) == 1
    assert "runbooks unavailable" in update["errors"][0]["error"]


def test_retrieval_is_recorded_in_the_audit_log():
    llm = FakeLLM(rollback_response())

    update = make_hypothesis_agent(llm, no_history, runbook_fn=runbooks_found)(correlated_state(0))

    entry = next(e for e in update["audit_log"] if e["action"] == "knowledge_retrieved")
    assert "RB-001" in entry["detail"]
    assert "1 runbooks" in entry["detail"]


def test_agent_without_a_runbook_function_still_works():
    llm = FakeLLM(rollback_response())

    update = make_hypothesis_agent(llm, no_history)(correlated_state(0))

    assert update["status"] == "hypothesized"
    assert "RB-" not in llm.calls[0][1].content