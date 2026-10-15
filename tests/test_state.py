import json
from pathlib import Path

from opssentinel.state import IncidentState

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


def load_alerts():
    with open(ALERTS_PATH) as f:
        return json.load(f)


def test_sample_alerts_cover_two_sources():
    alerts = load_alerts()
    assert len(alerts) == 2
    assert {a["source"] for a in alerts} == {"prometheus", "datadog"}


def test_state_can_be_initialized_from_alert():
    alert = load_alerts()[0]
    state: IncidentState = {
        "incident_id": "INC-001",
        "raw_alert": alert,
        "status": "ingested",
        "audit_log": [],
        "errors": [],
    }
    assert state["raw_alert"]["source"] == "prometheus"
    assert state["status"] == "ingested"