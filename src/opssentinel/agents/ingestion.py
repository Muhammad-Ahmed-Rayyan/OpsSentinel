from datetime import datetime, timezone

from pydantic import ValidationError

from opssentinel.audit import audit_entry
from opssentinel.dedup import AlertDeduplicator
from opssentinel.schemas import NormalizedAlert
from opssentinel.state import IncidentState

AGENT_NAME = "alert_ingestion"
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

PROMETHEUS_SEVERITY = {
    "critical": "critical",
    "error": "high",
    "warning": "medium",
    "info": "low",
}
DATADOG_PRIORITY = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low", "P5": "low"}


class UnsupportedAlertSourceError(ValueError):
    """Raised when an alert comes from a monitoring tool we have no parser for."""


def _parse_prometheus(payload: dict) -> NormalizedAlert:
    labels = payload["labels"]
    return NormalizedAlert(
        source="prometheus",
        name=payload["alertname"],
        summary=payload["annotations"]["summary"],
        severity=PROMETHEUS_SEVERITY.get(labels["severity"].lower(), "high"),
        service=labels.get("service"),
        host=labels.get("instance"),
        environment=labels.get("env"),
        triggered_at=datetime.fromisoformat(payload["startsAt"].replace("Z", "+00:00")),
    )


def _parse_datadog(payload: dict) -> NormalizedAlert:
    tags = dict(tag.split(":", 1) for tag in payload.get("tags", []) if ":" in tag)
    return NormalizedAlert(
        source="datadog",
        name=payload["title"],
        summary=payload["title"],
        severity=DATADOG_PRIORITY.get(payload["priority"].upper(), "high"),
        service=tags.get("service"),
        host=tags.get("host"),
        environment=tags.get("env"),
        triggered_at=datetime.fromtimestamp(payload["last_triggered_ts"], tz=timezone.utc),
    )


PARSERS = {
    "prometheus": _parse_prometheus,
    "datadog": _parse_datadog,
}


def normalize_alert(raw_alert: dict) -> NormalizedAlert:
    """Convert a raw alert from any supported source into a NormalizedAlert."""
    source = str(raw_alert.get("source", "")).lower()
    parser = PARSERS.get(source)
    if parser is None:
        raise UnsupportedAlertSourceError(f"Unsupported alert source: '{source}'")
    return parser(raw_alert["payload"])


def make_ingestion_agent(
    deduplicator: AlertDeduplicator | None = None, min_severity: str = "low"
):
    """Build the LangGraph node.

    min_severity: alerts below this severity are suppressed as noise.
    deduplicator: suppresses repeats of an alert whose incident is still open.
    """
    if min_severity not in SEVERITY_ORDER:
        raise ValueError(
            f"min_severity must be one of {sorted(SEVERITY_ORDER)}, got '{min_severity}'"
        )

    def ingest(state: IncidentState) -> dict:
        """Fill state['alert'] from state['raw_alert'].

        Malformed input is recorded in state['errors'] instead of raising, so the
        graph can route to reporting rather than crash.
        """
        audit_log = list(state.get("audit_log", []))
        errors = list(state.get("errors", []))

        try:
            alert = normalize_alert(state["raw_alert"])
        except (KeyError, ValueError, TypeError, ValidationError) as exc:
            errors.append({"agent": AGENT_NAME, "error": f"{type(exc).__name__}: {exc}"})
            audit_log.append(audit_entry(AGENT_NAME, "ingestion_failed", str(exc)))
            return {"status": "failed", "errors": errors, "audit_log": audit_log}

        def suppress(reason: str) -> dict:
            audit_log.append(audit_entry(AGENT_NAME, "alert_suppressed", reason))
            return {
                "alert": alert.model_dump(mode="json"),
                "status": "suppressed",
                "errors": errors,
                "audit_log": audit_log,
            }

        if SEVERITY_ORDER[alert.severity] < SEVERITY_ORDER[min_severity]:
            return suppress(
                f"noise: severity '{alert.severity}' is below the minimum '{min_severity}'"
            )
        if deduplicator is not None:
            original = deduplicator.check(alert, str(state.get("incident_id", "unknown")))
            if original is not None:
                return suppress(f"duplicate of open incident {original}")

        audit_log.append(
            audit_entry(
                AGENT_NAME,
                "alert_normalized",
                f"{alert.source} alert '{alert.name}' ({alert.severity})",
            )
        )
        return {
            "alert": alert.model_dump(mode="json"),
            "status": "ingested",
            "errors": errors,
            "audit_log": audit_log,
        }

    return ingest

ingest_alert = make_ingestion_agent()