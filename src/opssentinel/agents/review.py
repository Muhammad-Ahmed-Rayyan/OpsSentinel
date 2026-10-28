from langgraph.types import interrupt

from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState

AGENT_NAME = "review_gate"
DECISIONS = ("confirmed", "corrected", "rejected", "skipped")


def build_review_request(state: IncidentState) -> dict:
    """What the reviewer sees: the diagnosis, the action taken and the proof it worked."""
    hypotheses = state.get("hypotheses") or []
    top = hypotheses[0] if hypotheses else {}
    proposal = state.get("proposed_action") or {}
    return {
        "kind": "review",
        "incident_id": state.get("incident_id"),
        "likely_cause": top.get("cause"),
        "confidence": top.get("confidence"),
        "action_taken": f"{proposal.get('action')} {proposal.get('parameters', {})}",
        "verification": (state.get("verification") or {}).get("message"),
    }


def normalize_review(response) -> dict:
    """Turn the human's answer into a safe review record.

    Fail safe: an unknown decision, a malformed answer, or a correction with no
    text all become "skipped", so nothing is learned from an unclear answer.
    """
    response = response if isinstance(response, dict) else {}
    decision = response.get("decision")
    corrected = str(response.get("corrected_root_cause") or "").strip()
    if decision not in DECISIONS or (decision == "corrected" and not corrected):
        decision = "skipped"
    return {
        "decision": decision,
        "reviewer": str(response.get("reviewer") or "unknown"),
        "comment": str(response.get("comment") or "").strip(),
        "corrected_root_cause": corrected if decision == "corrected" else "",
    }


def review_gate(state: IncidentState) -> dict:
    """LangGraph node. Pauses until a human reviews the finished incident."""
    review = normalize_review(interrupt(build_review_request(state)))
    audit_log = [
        *state.get("audit_log", []),
        audit_entry(
            AGENT_NAME,
            f"review_{review['decision']}",
            f"{review['reviewer']}: {review['comment'] or 'no comment'}",
        ),
    ]
    return {"review": review, "audit_log": audit_log}