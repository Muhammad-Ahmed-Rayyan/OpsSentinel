from copy import deepcopy

from opssentinel.agents.execution import make_execution_agent
from opssentinel.tools.remediation import SimulatedInfrastructure

ROLLBACK_PARAMS = {"service": "checkout-api", "target_version": "v2.13.2"}
CLEANUP_PARAMS = {"host": "log-server-02", "path": "/var/log"}
APPROVED = {"decision": "approved", "reviewer": "tester", "comment": ""}
REJECTED = {"decision": "rejected", "reviewer": "tester", "comment": "too risky"}


def state_for(action, parameters, approval=None):
    state = {
        "incident_id": "INC-T",
        "proposed_action": {"action": action, "parameters": parameters},
        "audit_log": [],
        "errors": [],
    }
    if approval:
        state["approval"] = approval
    return state


def checkout(infra):
    return infra.state["services"]["checkout-api"]


def test_low_risk_action_runs_without_approval():
    infra = SimulatedInfrastructure()
    update = make_execution_agent(infra)(state_for("cleanup_old_logs", CLEANUP_PARAMS))

    assert update["status"] == "verifying"
    assert update["execution_result"]["success"] is True
    assert infra.state["hosts"]["log-server-02"]["disk_usage_percent"] < 60
    assert "auto-approved" in update["audit_log"][-1]["detail"]


def test_high_risk_action_is_refused_without_approval():
    infra = SimulatedInfrastructure()
    update = make_execution_agent(infra)(state_for("rollback_deployment", ROLLBACK_PARAMS))

    assert update["status"] == "failed"
    assert checkout(infra)["version"] == "v2.14.0"
    assert len(update["errors"]) == 1


def test_high_risk_action_runs_after_approval():
    infra = SimulatedInfrastructure()
    update = make_execution_agent(infra)(
        state_for("rollback_deployment", ROLLBACK_PARAMS, APPROVED)
    )

    assert update["status"] == "verifying"
    assert checkout(infra)["version"] == "v2.13.2"
    assert checkout(infra)["error_rate_percent"] < 1
    assert "tester" in update["audit_log"][-1]["detail"]


def test_rejected_action_is_not_executed():
    infra = SimulatedInfrastructure()
    update = make_execution_agent(infra)(
        state_for("rollback_deployment", ROLLBACK_PARAMS, REJECTED)
    )

    assert update["status"] == "rejected"
    assert checkout(infra)["version"] == "v2.14.0"


def test_extra_parameters_from_llm_are_ignored():
    infra = SimulatedInfrastructure()
    params = {**ROLLBACK_PARAMS, "reason": "bad release", "force": True}
    update = make_execution_agent(infra)(state_for("rollback_deployment", params, APPROVED))

    assert update["status"] == "verifying"


def test_failed_remediation_escalates_to_human():
    infra = SimulatedInfrastructure()
    params = {"service": "checkout-api", "target_version": "v9.9.9"}
    update = make_execution_agent(infra)(state_for("rollback_deployment", params, APPROVED))

    assert update["status"] == "escalated"
    assert update["execution_result"]["success"] is False
    assert len(update["errors"]) == 1
    assert checkout(infra)["version"] == "v2.14.0"


def test_unsafe_log_path_is_refused():
    infra = SimulatedInfrastructure()
    params = {"host": "log-server-02", "path": "/etc"}
    update = make_execution_agent(infra)(state_for("cleanup_old_logs", params))

    assert update["status"] == "escalated"
    assert infra.state["hosts"]["log-server-02"]["disk_usage_percent"] > 90


def test_escalation_makes_no_infrastructure_change():
    infra = SimulatedInfrastructure()
    before = deepcopy(infra.state)
    update = make_execution_agent(infra)(state_for("escalate_to_human", {}))

    assert update["status"] == "escalated"
    assert infra.state == before


def test_unknown_action_fails_without_crashing():
    infra = SimulatedInfrastructure()
    update = make_execution_agent(infra)(state_for("format_disk", {}))

    assert update["status"] == "failed"
    assert update["errors"][0]["agent"] == "execution"