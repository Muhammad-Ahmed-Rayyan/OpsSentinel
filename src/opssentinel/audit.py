from datetime import datetime, timezone


def audit_entry(agent: str, action: str, detail: str) -> dict:
    """Build one timestamped audit-log record."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": action,
        "detail": detail,
    }