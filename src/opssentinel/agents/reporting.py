import re
from pathlib import Path

from opssentinel.audit import audit_entry
from opssentinel.state import IncidentState
from opssentinel.tools.knowledge_base import add_postmortem

AGENT_NAME = "reporting"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"

OUTCOME_TEXT = {
    "resolved": "Resolved: the fix was applied and verified.",
    "rejected": "Not fixed: a human reviewer rejected the proposed action.",
    "escalated": "Handed to a human: automated handling could not safely finish.",
    "failed": "Failed: the pipeline stopped before an action could be taken.",
}


def _approval_text(state: IncidentState) -> str:
    approval = state.get("approval") or {}
    if approval:
        text = f"{approval.get('decision')} by {approval.get('reviewer', 'unknown')}"
        return text + (f" ({approval['comment']})" if approval.get("comment") else "")
    if state.get("risk_tier") == "low":
        return "not required (low risk)"
    return "none recorded"


def build_report(state: IncidentState) -> str:
    alert = state.get("alert") or {}
    status = state.get("status", "unknown")
    proposal = state.get("proposed_action") or {}
    result = state.get("execution_result") or {}
    verification = state.get("verification") or {}
    hypotheses = state.get("hypotheses") or []

    lines = [
        f"# Incident {state.get('incident_id', 'unknown')}: {alert.get('name') or 'Unclassified'}",
        "",
        f"**Outcome:** {OUTCOME_TEXT.get(status, f'Ended with status {status}.')}",
        "",
        "## Alert",
        f"- Source: {alert.get('source', 'unknown')}",
        f"- Severity: {alert.get('severity', 'unknown')}",
        f"- Summary: {alert.get('summary', 'n/a')}",
        f"- Service / host: {alert.get('service') or '-'} / {alert.get('host') or '-'}",
        f"- Triggered at: {alert.get('triggered_at', 'n/a')}",
        "",
        "## Root-cause analysis",
    ]
    if hypotheses:
        for number, hypothesis in enumerate(hypotheses, start=1):
            confidence = hypothesis.get("confidence")
            suffix = f" (confidence {confidence:.2f})" if isinstance(confidence, (int, float)) else ""
            lines.append(f"{number}. {hypothesis.get('cause', 'unknown')}{suffix}")
            lines += [f"   - {item}" for item in hypothesis.get("evidence", [])]
    else:
        lines.append("No hypothesis was produced.")

    lines += ["", "## Action"]
    if proposal:
        lines += [
            f"- Proposed: {proposal.get('action')} {proposal.get('parameters', {})}",
            f"- Risk tier: {state.get('risk_tier', 'unknown')}",
            f"- Rationale: {proposal.get('rationale', 'n/a')}",
            f"- Approval: {_approval_text(state)}",
        ]
        if result:
            lines.append(f"- Result: {result.get('message')}")
    else:
        lines.append("No action was proposed.")

    lines += ["", "## Verification", verification.get("message") or "No verification was performed."]

    lines += ["", "## Timeline"]
    lines += [
        f"- {e.get('timestamp')} [{e.get('agent')}] {e.get('action')}: {e.get('detail')}"
        for e in state.get("audit_log", [])
    ] or ["- no events recorded"]

    lines += ["", "## Issues"]
    lines += [f"- [{e.get('agent')}] {e.get('error')}" for e in state.get("errors", [])] or ["- none"]
    return "\n".join(lines) + "\n"


def build_postmortem_record(state: IncidentState) -> dict | None:
    """Turn a verified, resolved incident into a knowledge-base entry.

    Anything not resolved is never learned, so a fix that did not work cannot
    be recommended to the next incident.
    """
    if state.get("status") != "resolved":
        return None
    alert = state.get("alert") or {}
    hypotheses = state.get("hypotheses") or []
    proposal = state.get("proposed_action") or {}
    if not (alert and hypotheses and proposal.get("action")):
        return None

    approval = state.get("approval") or {}
    approver = approval.get("reviewer", "unknown") if approval.get("decision") == "approved" else "auto (low risk)"
    signals = (state.get("context") or {}).get("signals", [])
    return {
        "id": f"PM-{state.get('incident_id', 'unknown')}",
        "title": f"{alert.get('name')}: {alert.get('summary')}",
        "service": alert.get("service") or alert.get("host") or "unknown",
        "symptoms": "; ".join(signals) or str(alert.get("summary")),
        "root_cause": hypotheses[0].get("cause", "unknown"),
        "remediation_action": proposal["action"],
        "resolution": f"{(state.get('execution_result') or {}).get('message')}. "
        f"Verified: {(state.get('verification') or {}).get('message')}.",
        "source": "incident",
        "approved_by": approver,
    }


def make_reporting_agent(reports_dir: Path = DEFAULT_REPORTS_DIR, learn_fn=add_postmortem):
    """Build the LangGraph node. The report folder and learning function are injected for tests."""

    def write_report(state: IncidentState) -> dict:
        audit_log = list(state.get("audit_log", []))
        errors = list(state.get("errors", []))
        report = build_report(state)
        update: dict = {"report": report}

        try:
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(state.get("incident_id", "unknown")))
            path = Path(reports_dir) / f"{safe_id}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report, encoding="utf-8")
            update["report_path"] = str(path)
            audit_log.append(audit_entry(AGENT_NAME, "report_written", str(path)))
        except OSError as exc:
            errors.append({"agent": AGENT_NAME, "error": f"could not write report: {exc}"})
            audit_log.append(audit_entry(AGENT_NAME, "report_failed", str(exc)))

        record = build_postmortem_record(state)
        if record is not None:
            try:
                learn_fn(record)
                audit_log.append(
                    audit_entry(AGENT_NAME, "knowledge_updated", f"{record['id']} added to the knowledge base")
                )
            except Exception as exc:  # knowledge-base trouble must never lose the report
                errors.append({"agent": AGENT_NAME, "error": f"could not update knowledge base: {exc}"})
                audit_log.append(audit_entry(AGENT_NAME, "knowledge_update_failed", str(exc)))

        return {**update, "errors": errors, "audit_log": audit_log}

    return write_report