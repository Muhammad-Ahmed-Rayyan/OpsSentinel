import json
from pathlib import Path

import pytest

from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.ingestion import ingest_alert
from opssentinel.tools import telemetry

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


def ingested_state(index: int) -> dict:
    with open(ALERTS_PATH) as f:
        raw = json.load(f)[index]
    state = {"incident_id": "INC-TEST", "raw_alert": raw, "audit_log": [], "errors": []}
    return {**state, **ingest_alert(state)}


def test_checkout_incident_finds_deployment_and_filters_noise():
    update = correlate_incident(ingested_state(0))
    ctx = update["context"]

    assert update["status"] == "correlated"
    assert [d["version"] for d in ctx["deployments"]] == ["v2.14.0"]
    assert ctx["logs"] and ctx["metrics"]
    assert all(log["service"] == "checkout-api" for log in ctx["logs"])
    assert all(m["service"] == "checkout-api" for m in ctx["metrics"])

    signals = " | ".join(ctx["signals"])
    assert "9 min before the alert" in signals
    assert "http_5xx_rate_percent moved from 0.4 to 38.0" in signals
    assert "PaymentValidator" in signals


def test_disk_incident_matches_by_host_and_has_no_deployment():
    update = correlate_incident(ingested_state(1))
    ctx = update["context"]

    assert update["status"] == "correlated"
    assert ctx["deployments"] == []
    assert ctx["logs"] and ctx["metrics"]
    assert all(log["host"] == "log-server-02" for log in ctx["logs"])
    assert any("disk_usage_percent" in s for s in ctx["signals"])
    assert not any("Deployment" in s for s in ctx["signals"])


def test_one_missing_source_degrades_gracefully(tmp_path, monkeypatch):
    (tmp_path / "logs.json").write_text("[]")
    (tmp_path / "metrics.json").write_text("[]")
    monkeypatch.setattr(telemetry, "DATA_DIR", tmp_path)

    update = correlate_incident(ingested_state(0))

    assert update["status"] == "correlated"
    assert update["context"]["unavailable_sources"] == ["deployments"]
    assert len(update["errors"]) == 1


def test_all_sources_missing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "DATA_DIR", tmp_path)

    update = correlate_incident(ingested_state(0))

    assert update["status"] == "failed"
    assert len(update["errors"]) == 3


def test_missing_alert_fails_without_crashing():
    update = correlate_incident({"incident_id": "INC-X", "audit_log": [], "errors": []})

    assert update["status"] == "failed"
    assert update["errors"][0]["agent"] == "correlation"