import json
from pathlib import Path

from opssentinel.agents.ingestion import make_ingestion_agent
from opssentinel.dedup import AlertDeduplicator

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"

INFO_ALERT = {
    "source": "prometheus",
    "payload": {
        "alertname": "SlowBatchJob",
        "labels": {"service": "batch-api", "severity": "info"},
        "annotations": {"summary": "nightly job took 2 minutes longer than usual"},
        "startsAt": "2026-10-15T09:12:00Z",
    },
}

alerts = json.loads(ALERTS_PATH.read_text())
agent = make_ingestion_agent(AlertDeduplicator(window_minutes=30), min_severity="medium")

steps = [
    ("checkout alert", "INC-A", alerts[0]),
    ("same alert again", "INC-B", alerts[0]),
    ("informational alert", "INC-C", INFO_ALERT),
    ("disk alert", "INC-D", alerts[1]),
]
for label, incident_id, raw in steps:
    update = agent({"incident_id": incident_id, "raw_alert": raw, "audit_log": [], "errors": []})
    print(f"{label:22} -> {update['status']:10} {update['audit_log'][-1]['detail']}")