import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "telemetry"
LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "CRITICAL": 4}


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load(filename: str) -> list[dict]:
    # DATA_DIR is read at call time so tests can point it elsewhere.
    with open(DATA_DIR / filename) as f:
        return json.load(f)


def _matches(entry: dict, service: str | None, host: str | None) -> bool:
    return (service is not None and entry.get("service") == service) or (
        host is not None and entry.get("host") == host
    )


def get_logs(
    service: str | None,
    host: str | None,
    start: datetime,
    end: datetime,
    min_level: str = "WARN",
) -> list[dict]:
    threshold = LEVEL_ORDER[min_level]
    entries = [
        e
        for e in _load("logs.json")
        if _matches(e, service, host)
        and start <= parse_ts(e["timestamp"]) <= end
        and LEVEL_ORDER.get(e["level"], 0) >= threshold
    ]
    return sorted(entries, key=lambda e: e["timestamp"])


def get_metrics(
    service: str | None, host: str | None, start: datetime, end: datetime
) -> list[dict]:
    entries = [
        e
        for e in _load("metrics.json")
        if _matches(e, service, host) and start <= parse_ts(e["timestamp"]) <= end
    ]
    return sorted(entries, key=lambda e: e["timestamp"])


def get_deployments(service: str | None, start: datetime, end: datetime) -> list[dict]:
    if service is None:
        return []
    entries = [
        e
        for e in _load("deployments.json")
        if e["service"] == service and start <= parse_ts(e["timestamp"]) <= end
    ]
    return sorted(entries, key=lambda e: e["timestamp"])