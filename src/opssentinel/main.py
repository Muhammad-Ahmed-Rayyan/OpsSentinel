import argparse
import getpass
import json
from pathlib import Path

from langgraph.types import Command

from opssentinel.config import settings
from opssentinel.graph import build_graph
from opssentinel.llm import get_llm
from opssentinel.tools.knowledge_base import seed_knowledge_base
from opssentinel.tools.remediation import SimulatedInfrastructure

ALERTS_PATH = Path(__file__).resolve().parents[2] / "data" / "alerts" / "sample_alerts.json"


def ask_human(request: dict) -> dict:
    print("\n" + "=" * 70)
    print("HUMAN APPROVAL REQUIRED")
    for key, value in request.items():
        print(f"  {key}: {value}")
    answer = input("\nApprove this action? [y/N]: ").strip().lower()
    comment = input("Comment (optional): ").strip()
    return {
        "decision": "approved" if answer in ("y", "yes") else "rejected",
        "reviewer": getpass.getuser(),
        "comment": comment,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simulated incident through OpsSentinel")
    parser.add_argument(
        "--alert", type=int, default=0, choices=[0, 1],
        help="0 = checkout 5xx spike (high risk), 1 = disk full (low risk)",
    )
    args = parser.parse_args()

    print(f"LLM: {settings.llm_provider} / {settings.active_model}")
    seed_knowledge_base()
    infra = SimulatedInfrastructure()
    graph = build_graph(get_llm(), infra)

    incident_id = f"INC-CLI-{args.alert}"
    config = {"configurable": {"thread_id": incident_id}}
    initial_state = {
        "incident_id": incident_id,
        "raw_alert": json.loads(ALERTS_PATH.read_text())[args.alert],
        "audit_log": [],
        "errors": [],
    }

    print("\nInfrastructure before:", json.dumps(infra.state))
    result = graph.invoke(initial_state, config)
    while "__interrupt__" in result:
        decision = ask_human(result["__interrupt__"][0].value)
        result = graph.invoke(Command(resume=decision), config)

    print("\n" + "=" * 70)
    print(f"{incident_id} finished with status: {result['status']}")
    print("Execution result:", json.dumps(result.get("execution_result")))
    print("Errors:", result["errors"])
    print("\nAudit trail:")
    for entry in result["audit_log"]:
        print(f"  {entry['timestamp']} [{entry['agent']}] {entry['action']}: {entry['detail']}")
    print("\nInfrastructure after: ", json.dumps(infra.state))


if __name__ == "__main__":
    main()