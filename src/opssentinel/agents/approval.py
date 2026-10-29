from langgraph.types import interrupt

from opssentinel.actions import ACTION_CATALOG
from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState

AGENT_NAME = "approval_gate"


def build_approval_request(state: IncidentState) -> dict:
    """The summary a human sees: the problem, the proposed action, the alternatives, and why."""
    alert = state.get("alert", {})
    hypotheses = state.get("hypotheses", [])
    top = hypotheses[0] if hypotheses else {}
    proposal = state.get("proposed_action", {})
    alternatives = [
        f"option {number}: {alt.get('action')} {alt.get('parameters', {})} "
        f"[{alt.get('risk_tier', '?')} risk] - {alt.get('rationale', '')}"
        for number, alt in enumerate(state.get("alternatives") or [], start=2)
    ]
    return {
        "kind": "approval",
        "incident_id": state.get("incident_id"),
        "alert": f"{alert.get('name')}: {alert.get('summary')}",
        "likely_cause": top.get("cause"),
        "confidence": top.get("confidence"),
        "proposed_action": proposal.get("action"),
        "parameters": proposal.get("parameters", {}),
        "rationale": proposal.get("rationale"),
        "risk_tier": state.get("risk_tier"),
        "alternatives": alternatives,
    }


def normalize_approval(state: IncidentState, response) -> dict:
    """Turn the human's answer into a safe approval record.

    Option 1 is the proposed action and options 2 and up are the alternatives.
    Fail safe: anything other than an explicit "approved" with a valid option
    number counts as a rejection.
    """
    response = response if isinstance(response, dict) else {}
    option_count = 1 + len(state.get("alternatives") or [])
    decision = "approved" if response.get("decision") == "approved" else "rejected"
    option = response.get("option", 1)
    valid = isinstance(option, int) and not isinstance(option, bool) and 1 <= option <= option_count
    if decision == "approved" and not valid:
        decision = "rejected"
    return {
        "decision": decision,
        "reviewer": str(response.get("reviewer") or "unknown"),
        "comment": str(response.get("comment") or ""),
        "option": option if decision == "approved" else None,
    }


def approval_gate(state: IncidentState) -> dict:
    """LangGraph node. interrupt() pauses the graph; whatever the caller passes to
    Command(resume=...) is returned here and the node continues."""
    approval = normalize_approval(state, interrupt(build_approval_request(state)))
    update: dict = {}
    detail = f"{approval['reviewer']}: {approval['comment'] or 'no comment'}"

    if approval["decision"] == "approved" and approval["option"] > 1:
        alternatives = list(state.get("alternatives") or [])
        chosen = alternatives.pop(approval["option"] - 2)
        original = {**(state.get("proposed_action") or {}), "risk_tier": state.get("risk_tier")}
        approval["original_action"] = original.get("action")
        update["proposed_action"] = {key: chosen[key] for key in ("action", "parameters", "rationale")}
        update["risk_tier"] = ACTION_CATALOG[chosen["action"]].risk_tier
        update["alternatives"] = [original, *alternatives]
        detail += f" (chose option {approval['option']}: {chosen['action']})"

    audit_log = [
        *state.get("audit_log", []),
        audit_entry(AGENT_NAME, f"action_{approval['decision']}", detail),
    ]
    return {
        **update,
        "approval": approval,
        "status": "executing" if approval["decision"] == "approved" else "rejected",
        "audit_log": audit_log,
    }