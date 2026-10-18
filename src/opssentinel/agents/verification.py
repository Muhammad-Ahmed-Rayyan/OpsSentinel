import time
from dataclasses import dataclass

from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState
from opssentinel.tools.monitoring import MetricError, read_metric
from opssentinel.tools.remediation import SimulatedInfrastructure

AGENT_NAME = "verification"


@dataclass(frozen=True)
class VerificationRule:
    metric: str
    entity_kind: str
    entity_param: str
    max_value: float

VERIFICATION_RULES = {
    "rollback_deployment": VerificationRule("error_rate_percent", "service", "service", 5.0),
    "restart_service": VerificationRule("error_rate_percent", "service", "service", 5.0),
    "scale_up_service": VerificationRule("error_rate_percent", "service", "service", 5.0),
    "cleanup_old_logs": VerificationRule("disk_usage_percent", "host", "host", 80.0),
}


def make_verification_agent(
    infra: SimulatedInfrastructure,
    attempts: int = 3,
    interval_seconds: float = 0.0,
    sleep=time.sleep,
):
    """Build the LangGraph node. Real systems need a settle time between checks
    (interval_seconds); the simulation changes instantly, so it defaults to 0."""

    def verify(state: IncidentState) -> dict:
        audit_log = list(state.get("audit_log", []))
        errors = list(state.get("errors", []))

        def finish(verified: bool, message: str, **details) -> dict:
            if not verified:
                errors.append({"agent": AGENT_NAME, "error": message})
            audit_log.append(
                audit_entry(AGENT_NAME, "verified" if verified else "verification_failed", message)
            )
            return {
                "verification": {"verified": verified, "message": message, **details},
                "status": "resolved" if verified else "escalated",
                "errors": errors,
                "audit_log": audit_log,
            }

        proposal = state.get("proposed_action") or {}
        action = proposal.get("action")
        rule = VERIFICATION_RULES.get(action)
        if rule is None:
            return finish(
                False, f"no automated verification for '{action}'; a human must confirm the outcome"
            )

        entity = (proposal.get("parameters") or {}).get(rule.entity_param)
        details = {"metric": rule.metric, "entity": entity, "threshold": rule.max_value}
        value = None
        for check in range(1, attempts + 1):
            try:
                value = read_metric(infra, rule.entity_kind, entity, rule.metric)
            except MetricError as exc:
                return finish(False, f"cannot read {rule.metric} for {entity}: {exc}", **details)
            if value <= rule.max_value:
                return finish(
                    True,
                    f"{rule.metric} for {entity} is {value} (limit {rule.max_value}) "
                    f"after {check} check(s)",
                    value=value, checks=check, **details,
                )
            if check < attempts:
                sleep(interval_seconds)

        return finish(
            False,
            f"{rule.metric} for {entity} is still {value} (limit {rule.max_value}) "
            f"after {attempts} checks",
            value=value, checks=attempts, **details,
        )

    return verify