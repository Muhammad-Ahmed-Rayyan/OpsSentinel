import json
from pathlib import Path

from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.hypothesis import make_hypothesis_agent
from opssentinel.agents.ingestion import ingest_alert
from opssentinel.config import settings
from opssentinel.llm import get_llm
from opssentinel.tools.knowledge_base import seed_knowledge_base

ALERTS_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts" / "sample_alerts.json"


def main() -> None:
    print(f"LLM: {settings.llm_provider} / {settings.active_model}")
    print(f"Postmortems in knowledge base: {seed_knowledge_base()}")
    hypothesize = make_hypothesis_agent(get_llm())

    for number, raw in enumerate(json.loads(ALERTS_PATH.read_text()), start=1):
        state = {"incident_id": f"INC-DEMO-{number}", "raw_alert": raw, "audit_log": [], "errors": []}
        for node in (ingest_alert, correlate_incident, hypothesize):
            state = {**state, **node(state)}

        print("\n" + "=" * 70)
        print(f"{state['incident_id']}: {state['alert']['name']} -> status: {state['status']}")
        print("Hypotheses:", json.dumps(state.get("hypotheses"), indent=2))
        print("Proposed action:", json.dumps(state.get("proposed_action"), indent=2))
        print("Risk tier:", state.get("risk_tier"))
        print("Errors:", state["errors"])


if __name__ == "__main__":
    main()