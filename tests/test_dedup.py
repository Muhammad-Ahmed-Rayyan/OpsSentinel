import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from opssentinel.agents.ingestion import make_ingestion_agent
from opssentinel.dedup import AlertDeduplicator
from opssentinel.schemas import NormalizedAlert

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"
BASE_TIME = datetime(2026, 10, 15, 9, 12, tzinfo=timezone.utc)

INFO_ALERT = {
    "source": "prometheus",
    "payload": {
        "alertname": "SlowBatchJob",
        "labels": {"service": "batch-api", "severity": "info"},
        "annotations": {"summary": "nightly job took 2 minutes longer than usual"},
        "startsAt": "2026-10-15T09:12:00Z",
    },
}


def make_alert(minutes=0, **overrides):
    fields = dict(
        source="prometheus",
        name="HighErrorRate",
        summary="5xx error rate at 38% for 5m",
        severity="critical",
        service="checkout-api",
        host=None,
        environment="prod",
        triggered_at=BASE_TIME + timedelta(minutes=minutes),
    )
    fields.update(overrides)
    return NormalizedAlert(**fields)


def raw_alert(index):
    return json.loads(ALERTS_PATH.read_text())[index]


def state_for(incident_id, raw):
    return {"incident_id": incident_id, "raw_alert": raw, "audit_log": [], "errors": []}


def test_first_alert_is_new_and_a_repeat_is_a_duplicate():
    dedup = AlertDeduplicator(window_minutes=30)

    assert dedup.check(make_alert(), "INC-1") is None
    assert dedup.check(make_alert(minutes=5), "INC-2") == "INC-1"


def test_repeat_outside_the_window_opens_a_new_incident():
    dedup = AlertDeduplicator(window_minutes=30)

    dedup.check(make_alert(), "INC-1")

    assert dedup.check(make_alert(minutes=45), "INC-2") is None


def test_different_service_is_not_a_duplicate():
    dedup = AlertDeduplicator(window_minutes=30)

    dedup.check(make_alert(), "INC-1")

    assert dedup.check(make_alert(service="inventory-api"), "INC-2") is None


def test_released_incident_no_longer_suppresses_repeats():
    dedup = AlertDeduplicator(window_minutes=30)
    dedup.check(make_alert(), "INC-1")

    dedup.release("INC-1")

    assert dedup.check(make_alert(minutes=5), "INC-2") is None


def test_repeats_keep_the_window_open():
    dedup = AlertDeduplicator(window_minutes=30)

    dedup.check(make_alert(), "INC-1")
    assert dedup.check(make_alert(minutes=20), "INC-2") == "INC-1"
    # 45 minutes after the first alert but only 25 after the last repeat
    assert dedup.check(make_alert(minutes=45), "INC-3") == "INC-1"


def test_low_severity_alert_is_suppressed_as_noise():
    agent = make_ingestion_agent(min_severity="medium")
    update = agent(state_for("INC-N", INFO_ALERT))

    assert update["status"] == "suppressed"
    assert "below the minimum" in update["audit_log"][-1]["detail"]
    assert update["errors"] == []


def test_duplicate_alert_is_suppressed_and_points_at_the_original():
    agent = make_ingestion_agent(AlertDeduplicator(window_minutes=30))

    first = agent(state_for("INC-A", raw_alert(0)))
    second = agent(state_for("INC-B", raw_alert(0)))

    assert first["status"] == "ingested"
    assert second["status"] == "suppressed"
    assert "INC-A" in second["audit_log"][-1]["detail"]


def test_alert_exactly_at_the_severity_threshold_is_not_suppressed():
    agent = make_ingestion_agent(min_severity="high")
    update = agent(state_for("INC-T", raw_alert(1)))  # Datadog P2 is "high"

    assert update["status"] == "ingested"