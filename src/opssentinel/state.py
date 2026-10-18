from typing import Literal, TypedDict

Status = Literal[
    "ingested",
    "correlated",
    "hypothesized",
    "awaiting_approval",
    "executing",
    "verifying",
    "resolved",
    "rejected",
    "escalated",
    "failed",
]


class IncidentState(TypedDict, total=False):
    incident_id: str
    raw_alert: dict          # alert exactly as the monitoring tool sent it
    alert: dict              # normalized alert (Ingestion Agent output)
    context: dict            # correlated logs, metrics, deployments (Correlation Agent)
    hypotheses: list         # ranked root causes (Hypothesis Agent)
    proposed_action: dict    # chosen remediation + parameters
    risk_tier: str           # "low" or "high"
    approval: dict           # human decision: approved / rejected / comment
    execution_result: dict   # output of the remediation tool
    verification: dict       # did the fix work?
    report: str              # final postmortem (Markdown)
    report_path: str         # where the postmortem was saved
    status: str
    errors: list             # failures recorded for handling/escalation
    audit_log: list          # every agent action, timestamped