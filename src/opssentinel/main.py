import argparse
import getpass
import json
from pathlib import Path

from langgraph.types import Command

from opssentinel.config import settings
from opssentinel.graph import build_graph
from opssentinel.llm import get_llm
from opssentinel.notifier import DEFAULT_OUTBOX_DIR, build_notifier
from opssentinel.tools.knowledge_base import seed_knowledge_base
from opssentinel.tools.remediation import SimulatedInfrastructure
from opssentinel.tools.runbooks import search_runbooks, seed_runbooks

ALERTS_PATH = Path(__file__).resolve().parents[2] / "data" / "alerts" / "sample_alerts.json"


def _show(title: str, request: dict) -> None:
    print("\n" + "=" * 70)
    print(title)
    for key, value in request.items():
        if key == "kind":
            continue
        if isinstance(value, list):
            print(f"  {key}:" + ("" if value else " none"))
            for item in value:
                print(f"    - {item}")
        else:
            print(f"  {key}: {value}")


def ask_approval(request: dict) -> dict:
    _show("HUMAN APPROVAL REQUIRED", request)
    options = 1 + len(request.get("alternatives") or [])
    if options > 1:
        prompt = (
            f"\nApprove? [y = option 1 (proposed), 2-{options} = approve that alternative, "
            "N = reject]: "
        )
    else:
        prompt = "\nApprove this action? [y/N]: "
    answer = input(prompt).strip().lower()
    comment = input("Comment (optional): ").strip()

    option = int(answer) if answer.isdigit() else 1
    approved = answer in ("y", "yes") or (answer.isdigit() and 1 <= option <= options)
    return {
        "decision": "approved" if approved else "rejected",
        "option": option,
        "reviewer": getpass.getuser(),
        "comment": comment,
    }


def ask_review(request: dict) -> dict:
    _show("POST-INCIDENT REVIEW", request)
    answer = input(
        "\nWas the diagnosis correct? [y = yes, n = no, c = correct it, s = skip]: "
    ).strip().lower()
    decision = {"y": "confirmed", "n": "rejected", "c": "corrected"}.get(answer, "skipped")
    corrected = input("Correct root cause: ").strip() if decision == "corrected" else ""
    comment = input("Comment (optional): ").strip()
    return {
        "decision": decision,
        "reviewer": getpass.getuser(),
        "comment": comment,
        "corrected_root_cause": corrected,
    }


def ask_human(request: dict) -> dict:
    return ask_review(request) if request.get("kind") == "review" else ask_approval(request)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simulated incident through OpsSentinel")
    parser.add_argument(
        "--alert", type=int, default=0, choices=[0, 1],
        help="0 = checkout 5xx spike (high risk), 1 = disk full (low risk)",
    )
    args = parser.parse_args()

    print(f"LLM: {settings.llm_provider} / {settings.active_model}")
    seed_knowledge_base()
    seed_runbooks()
    infra = SimulatedInfrastructure()
    notifier = build_notifier(DEFAULT_OUTBOX_DIR, settings.slack_webhook_url)
    graph = build_graph(get_llm(), infra, runbook_fn=search_runbooks, notifier=notifier)

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
    print("Execution:   ", json.dumps(result.get("execution_result")))
    print("Verification:", json.dumps(result.get("verification")))
    print("Review:      ", json.dumps(result.get("review")))
    print("Errors:      ", result["errors"])
    print("Report saved:", result.get("report_path", "(could not be saved)"))
    print("Notifications:", DEFAULT_OUTBOX_DIR)
    print("\n" + result["report"])
    print("Infrastructure after:", json.dumps(infra.state))


if __name__ == "__main__":
    main()