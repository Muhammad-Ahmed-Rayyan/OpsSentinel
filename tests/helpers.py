import json
from pathlib import Path
from types import SimpleNamespace

from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.ingestion import ingest_alert

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


class FakeLLM:
    """Returns canned responses in order and records the prompts it receives."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


def correlated_state(index: int) -> dict:
    raw = json.loads(ALERTS_PATH.read_text())[index]
    state = {"incident_id": "INC-TEST", "raw_alert": raw, "audit_log": [], "errors": []}
    for node in (ingest_alert, correlate_incident):
        state = {**state, **node(state)}
    return state


def rollback_response() -> str:
    return json.dumps(
        {
            "hypotheses": [
                {
                    "cause": "Bad release",
                    "confidence": 0.9,
                    "evidence": ["deployment 9 min before alert"],
                }
            ],
            "proposed_action": {
                "action": "rollback_deployment",
                "parameters": {"service": "checkout-api", "target_version": "v2.13.2"},
                "rationale": "Matches past incident",
            },
        }
    )