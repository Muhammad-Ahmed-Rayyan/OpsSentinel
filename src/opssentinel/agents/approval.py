from langgraph.types import interrupt

from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState

AGENT_NAME = "approval_gate"


def build_approval_request(state: IncidentState) -> dict:
    """The summary a human sees: the problem, the proposed action, and why."""
    alert = state.get("alert", {})
    hypotheses = state.get("hypotheses", [])
    top = hypotheses[0] if hypotheses else {}
    proposal = state.get("proposed_action", {})
    return {
        "incident_id": state.get("incident_id"),
        "alert": f"{alert.get('name')}: {alert.get('summary')}",
        "likely_cause": top.get("cause"),
        "confidence": top.get("confidence"),
        "proposed_action": proposal.get("action"),
        "parameters": proposal.get("parameters", {}),
        "rationale": proposal.get("rationale"),
        "risk_tier": state.get("risk_tier"),
    }


def approval_gate(state: IncidentState) -> dict:
    """LangGraph node. interrupt() pauses the graph; whatever the caller passes to
    Command(resume=...) is returned here and the node continues."""
    response = interrupt(build_approval_request(state))

    response = response if isinstance(response, dict) else {}
    decision = "approved" if response.get("decision") == "approved" else "rejected"
    approval = {
        "decision": decision,
        "reviewer": response.get("reviewer", "unknown"),
        "comment": response.get("comment", ""),
    }
    audit_log = [
        *state.get("audit_log", []),
        audit_entry(
            AGENT_NAME,
            f"action_{decision}",
            f"{approval['reviewer']}: {approval['comment'] or 'no comment'}",
        ),
    ]
    return {
        "approval": approval,
        "status": "executing" if decision == "approved" else "rejected",
        "audit_log": audit_log,
    }