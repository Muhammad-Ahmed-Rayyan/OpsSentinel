from opssentinel.agents.verification import make_verification_agent
from opssentinel.tools.remediation import SimulatedInfrastructure

ROLLBACK_PARAMS = {"service": "checkout-api", "target_version": "v2.13.2"}
CLEANUP_PARAMS = {"host": "log-server-02", "path": "/var/log"}


def state_for(action, parameters):
    return {
        "incident_id": "INC-V",
        "proposed_action": {"action": action, "parameters": parameters},
        "audit_log": [],
        "errors": [],
    }

def test_recovered_metric_resolves_the_incident():
    infra = SimulatedInfrastructure()
    infra.execute("rollback_deployment", ROLLBACK_PARAMS)

    update = make_verification_agent(infra)(state_for("rollback_deployment", ROLLBACK_PARAMS))

    assert update["status"] == "resolved"
    assert update["verification"]["verified"] is True
    assert update["verification"]["value"] == 0.5
    assert update["verification"]["checks"] == 1


def test_disk_cleanup_is_verified_against_disk_usage():
    infra = SimulatedInfrastructure()
    infra.execute("cleanup_old_logs", CLEANUP_PARAMS)

    update = make_verification_agent(infra)(state_for("cleanup_old_logs", CLEANUP_PARAMS))

    assert update["status"] == "resolved"
    assert update["verification"]["metric"] == "disk_usage_percent"


def test_metric_that_stays_bad_escalates_after_retries():
    infra = SimulatedInfrastructure()  # nothing was fixed: error rate is still 38%
    slept = []
    agent = make_verification_agent(infra, attempts=3, interval_seconds=30, sleep=slept.append)

    update = agent(state_for("rollback_deployment", ROLLBACK_PARAMS))

    assert update["status"] == "escalated"
    assert update["verification"]["verified"] is False
    assert update["verification"]["checks"] == 3
    assert slept == [30, 30]
    assert len(update["errors"]) == 1


def test_metric_that_recovers_between_checks_is_accepted():
    infra = SimulatedInfrastructure()

    def settle(seconds):
        infra.state["services"]["checkout-api"]["error_rate_percent"] = 0.5

    agent = make_verification_agent(infra, sleep=settle)
    update = agent(state_for("rollback_deployment", ROLLBACK_PARAMS))

    assert update["status"] == "resolved"
    assert update["verification"]["checks"] == 2


def test_action_without_a_rule_needs_a_human():
    infra = SimulatedInfrastructure()
    update = make_verification_agent(infra)(state_for("clear_cache", {"service": "checkout-api"}))

    assert update["status"] == "escalated"
    assert update["verification"]["verified"] is False
    assert "human" in update["verification"]["message"]


def test_unreadable_metric_escalates_instead_of_crashing():
    infra = SimulatedInfrastructure()
    params = {"service": "ghost-api", "target_version": "v1"}
    update = make_verification_agent(infra)(state_for("rollback_deployment", params))

    assert update["status"] == "escalated"
    assert "cannot read" in update["errors"][0]["error"]