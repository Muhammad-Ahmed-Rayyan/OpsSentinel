import json
from pathlib import Path

import pytest

from opssentinel.agents.ingestion import (
    UnsupportedAlertSourceError,
    ingest_alert,
    normalize_alert,
)

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


@pytest.fixture
def sample_alerts():
    with open(ALERTS_PATH) as f:
        return json.load(f)


def test_prometheus_alert_is_normalized(sample_alerts):
    alert = normalize_alert(sample_alerts[0])
    assert alert.source == "prometheus"
    assert alert.service == "checkout-api"
    assert alert.severity == "critical"
    assert "38%" in alert.summary
    assert alert.triggered_at.tzinfo is not None


def test_datadog_alert_is_normalized(sample_alerts):
    alert = normalize_alert(sample_alerts[1])
    assert alert.source == "datadog"
    assert alert.host == "log-server-02"
    assert alert.environment == "prod"
    assert alert.severity == "high"


def test_unsupported_source_raises():
    with pytest.raises(UnsupportedAlertSourceError):
        normalize_alert({"source": "nagios", "payload": {}})


def test_agent_updates_state_on_success(sample_alerts):
    state = {
        "incident_id": "INC-001",
        "raw_alert": sample_alerts[0],
        "audit_log": [],
        "errors": [],
    }
    update = ingest_alert(state)
    assert update["status"] == "ingested"
    assert update["alert"]["service"] == "checkout-api"
    assert len(update["audit_log"]) == 1
    assert update["errors"] == []


def test_agent_records_error_instead_of_crashing_on_bad_alert():
    state = {
        "incident_id": "INC-002",
        "raw_alert": {"source": "prometheus", "payload": {"alertname": "X"}},
        "audit_log": [],
        "errors": [],
    }
    update = ingest_alert(state)
    assert update["status"] == "failed"
    assert len(update["errors"]) == 1
    assert update["errors"][0]["agent"] == "alert_ingestion"