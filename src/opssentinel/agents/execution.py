from opssentinel.actions import ACTION_CATALOG
from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState
from opssentinel.tools.remediation import RemediationError, SimulatedInfrastructure

AGENT_NAME = "execution"
ESCALATE = "escalate_to_human"
AUTO_APPROVED = "auto-approved (low risk)"


def make_execution_agent(infra: SimulatedInfrastructure):
    """Build the LangGraph node. The infrastructure is injected so tests use a throwaway copy."""

    def execute_action(state: IncidentState) -> dict:
        audit_log = list(state.get("audit_log", []))
        errors = list(state.get("errors", []))

        def finish(status, log_action, message, action=None, success=False, error=False) -> dict:
            if error:
                errors.append({"agent": AGENT_NAME, "error": message})
            audit_log.append(audit_entry(AGENT_NAME, log_action, message))
            return {
                "execution_result": {"action": action, "success": success, "message": message},
                "status": status,
                "errors": errors,
                "audit_log": audit_log,
            }

        proposal = state.get("proposed_action") or {}
        action = proposal.get("action")
        spec = ACTION_CATALOG.get(action)
        if spec is None:
            return finish("failed", "execution_failed", "no valid proposed action in state", error=True)

        approval = state.get("approval") or {}
        if spec.risk_tier == "high" and approval.get("decision") != "approved":
            if approval.get("decision") == "rejected":
                reviewer = approval.get("reviewer", "reviewer")
                return finish("rejected", "execution_skipped", f"{action} rejected by {reviewer}", action)
            return finish(
                "failed", "execution_blocked",
                f"{action} is high risk and has no human approval", action, error=True,
            )

        if action == ESCALATE:
            return finish(
                "escalated", "escalated",
                "on-call engineer paged with the incident summary", action, success=True,
            )

        raw_parameters = proposal.get("parameters") or {}
        missing = [p for p in spec.required_params if p not in raw_parameters]
        if missing:
            return finish(
                "failed", "execution_failed",
                f"{action} is missing parameters: {missing}", action, error=True,
            )
        parameters = {name: raw_parameters[name] for name in spec.required_params}

        try:
            result = infra.execute(action, parameters)
        except RemediationError as exc:
            return finish("escalated", "execution_failed", f"{action} failed: {exc}", action, error=True)

        approver = approval.get("reviewer", "unknown") if spec.risk_tier == "high" else AUTO_APPROVED
        audit_log.append(
            audit_entry(
                AGENT_NAME,
                "action_executed",
                f"{result['message']} [{spec.risk_tier} risk, {approver}]",
            )
        )
        return {
            "execution_result": result,
            "status": "verifying",
            "errors": errors,
            "audit_log": audit_log,
        }

    return execute_action