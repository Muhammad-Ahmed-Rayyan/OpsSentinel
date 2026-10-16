from collections import Counter
from datetime import timedelta

from opssentinel.audit import audit_entry
from opssentinel.schemas import NormalizedAlert
from opssentinel.state import IncidentState
from opssentinel.tools import telemetry

AGENT_NAME = "correlation"
LOOKBACK_MINUTES = 60
LOOKAHEAD_MINUTES = 5
MAX_LOGS = 20
SOURCES = ("logs", "metrics", "deployments")


def _collect(name: str, fetch, errors: list, unavailable: list) -> list:
    """Run one data-source query; on failure record it and carry on with the rest."""
    try:
        return fetch()
    except (OSError, ValueError, KeyError) as exc:
        errors.append({"agent": AGENT_NAME, "error": f"{name} unavailable: {exc}"})
        unavailable.append(name)
        return []


def _deployment_signals(deployments: list[dict], triggered_at) -> list[str]:
    signals = []
    for d in deployments:
        minutes = int((triggered_at - telemetry.parse_ts(d["timestamp"])).total_seconds() // 60)
        if minutes >= 0:
            signals.append(
                f"Deployment of {d['service']} {d['version']} (from {d['previous_version']}) "
                f"occurred {minutes} min before the alert: {d['change_summary']}"
            )
    return signals


def _metric_signals(metrics: list[dict]) -> list[str]:
    series: dict[str, list[float]] = {}
    for m in sorted(metrics, key=lambda e: e["timestamp"]):
        series.setdefault(m["metric"], []).append(m["value"])
    return [
        f"{name} moved from {values[0]} to {values[-1]} (peak {max(values)})"
        for name, values in series.items()
    ]


def _log_signals(logs: list[dict]) -> list[str]:
    error_logs = [e for e in logs if telemetry.LEVEL_ORDER.get(e["level"], 0) >= 3]
    if not error_logs:
        return []
    message, count = Counter(e["message"] for e in error_logs).most_common(1)[0]
    return [f"{len(error_logs)} error-level log lines; most frequent: '{message}' ({count}x)"]


def correlate_incident(state: IncidentState) -> dict:
    """LangGraph node: build state['context'] from the normalized alert."""
    audit_log = list(state.get("audit_log", []))
    errors = list(state.get("errors", []))

    try:
        alert = NormalizedAlert.model_validate(state["alert"])
    except (KeyError, ValueError, TypeError) as exc:
        errors.append({"agent": AGENT_NAME, "error": f"No valid alert in state: {exc}"})
        audit_log.append(audit_entry(AGENT_NAME, "correlation_failed", str(exc)))
        return {"status": "failed", "errors": errors, "audit_log": audit_log}

    start = alert.triggered_at - timedelta(minutes=LOOKBACK_MINUTES)
    end = alert.triggered_at + timedelta(minutes=LOOKAHEAD_MINUTES)
    unavailable: list[str] = []

    logs = _collect(
        "logs", lambda: telemetry.get_logs(alert.service, alert.host, start, end), errors, unavailable
    )
    metrics = _collect(
        "metrics", lambda: telemetry.get_metrics(alert.service, alert.host, start, end), errors, unavailable
    )
    deployments = _collect(
        "deployments", lambda: telemetry.get_deployments(alert.service, start, end), errors, unavailable
    )

    if len(unavailable) == len(SOURCES):
        audit_log.append(audit_entry(AGENT_NAME, "correlation_failed", "All data sources unavailable"))
        return {"status": "failed", "errors": errors, "audit_log": audit_log}

    signals = (
        _deployment_signals(deployments, alert.triggered_at)
        + _metric_signals(metrics)
        + _log_signals(logs)
    )
    context = {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "deployments": deployments,
        "metrics": metrics,
        "logs": logs[-MAX_LOGS:],
        "signals": signals,
        "unavailable_sources": unavailable,
    }
    audit_log.append(
        audit_entry(
            AGENT_NAME,
            "context_built",
            f"{len(logs)} logs, {len(metrics)} metrics, {len(deployments)} deployments, "
            f"{len(signals)} signals; unavailable: {unavailable or 'none'}",
        )
    )
    return {"context": context, "status": "correlated", "errors": errors, "audit_log": audit_log}