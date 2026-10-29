from opssentinel.agents.approval import build_approval_request
from opssentinel.agents.review import build_review_request
from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState

AGENT_NAME = "notifier"
NEEDS_HUMAN = ("escalated", "failed")


def build_escalation_message(state: IncidentState) -> dict:
    alert = state.get("alert") or {}
    reasons = [e.get("error") for e in state.get("errors", [])] or ["no error recorded"]
    return {
        "kind": "escalation",
        "incident_id": state.get("incident_id"),
        "status": state.get("status"),
        "alert": f"{alert.get('name', 'unknown')}: {alert.get('summary', 'n/a')}",
        "reasons": reasons,
    }


def _send(state: IncidentState, notifier, message: dict, label: str) -> dict:
    audit_log = list(state.get("audit_log", []))
    errors = list(state.get("errors", []))
    try:
        notifier.send(message)
        audit_log.append(audit_entry(AGENT_NAME, "human_notified", f"{label} notification sent"))
    except Exception as exc:  # losing a channel must never freeze incident response
        errors.append({"agent": AGENT_NAME, "error": f"notification failed: {exc}"})
        audit_log.append(audit_entry(AGENT_NAME, "notification_failed", f"{label}: {exc}"))
    return {"errors": errors, "audit_log": audit_log}


def make_notify_approval(notifier):
    def notify_approval(state: IncidentState) -> dict:
        return _send(state, notifier, build_approval_request(state), "approval request")

    return notify_approval


def make_notify_review(notifier):
    def notify_review(state: IncidentState) -> dict:
        return _send(state, notifier, build_review_request(state), "review request")

    return notify_review


def make_notify_outcome(notifier):
    def notify_outcome(state: IncidentState) -> dict:
        if state.get("status") not in NEEDS_HUMAN:
            return {"audit_log": list(state.get("audit_log", []))}  # a node must return an update
        return _send(state, notifier, build_escalation_message(state), "escalation")

    return notify_outcome