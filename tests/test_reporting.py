from pathlib import Path

import pytest

from opssentinel.agents.reporting import make_reporting_agent


def resolved_state():
    return {
        "incident_id": "INC-R1",
        "status": "resolved",
        "alert": {
            "source": "prometheus",
            "name": "HighErrorRate",
            "summary": "5xx error rate at 38% for 5m",
            "severity": "critical",
            "service": "checkout-api",
            "host": None,
            "triggered_at": "2026-10-15T09:12:00+00:00",
        },
        "context": {
            "signals": [
                "Deployment of checkout-api v2.14.0 occurred 9 min before the alert",
                "http_5xx_rate_percent moved from 0.4 to 38.0",
            ]
        },
        "hypotheses": [
            {
                "cause": "Null handling bug in v2.14.0",
                "confidence": 0.9,
                "evidence": ["deployment 9 min before alert"],
            }
        ],
        "proposed_action": {
            "action": "rollback_deployment",
            "parameters": {"service": "checkout-api", "target_version": "v2.13.2"},
            "rationale": "Matches PM-001",
        },
        "risk_tier": "high",
        "approval": {"decision": "approved", "reviewer": "tester", "comment": "go ahead"},
        "execution_result": {
            "action": "rollback_deployment",
            "success": True,
            "message": "rolled back checkout-api from v2.14.0 to v2.13.2",
        },
        "verification": {
            "verified": True,
            "message": "error_rate_percent for checkout-api is 0.5 (limit 5.0) after 1 check(s)",
        },
        "audit_log": [
            {
                "timestamp": "2026-10-15T09:13:00+00:00",
                "agent": "hypothesis",
                "action": "hypotheses_ranked",
                "detail": "top: Null handling bug",
            }
        ],
        "errors": [],
    }


def test_report_contains_the_key_facts_and_is_saved(tmp_path):
    update = make_reporting_agent(tmp_path, learn_fn=lambda record: None)(resolved_state())

    report = update["report"]
    for expected in [
        "INC-R1", "HighErrorRate", "Null handling bug", "rollback_deployment",
        "approved by tester", "0.5", "hypotheses_ranked",
    ]:
        assert expected in report
    saved = Path(update["report_path"])
    assert saved == tmp_path / "INC-R1.md"
    assert saved.read_text(encoding="utf-8") == report


def test_resolved_incident_is_learned(tmp_path):
    learned = []
    make_reporting_agent(tmp_path, learn_fn=learned.append)(resolved_state())

    assert len(learned) == 1
    record = learned[0]
    assert record["id"] == "PM-INC-R1"
    assert record["remediation_action"] == "rollback_deployment"
    assert record["root_cause"] == "Null handling bug in v2.14.0"
    assert record["approved_by"] == "tester"
    assert record["source"] == "incident"
    assert "http_5xx_rate_percent" in record["symptoms"]


@pytest.mark.parametrize("status", ["rejected", "escalated", "failed"])
def test_unresolved_incidents_are_never_learned(tmp_path, status):
    learned = []
    state = {**resolved_state(), "status": status}
    make_reporting_agent(tmp_path, learn_fn=learned.append)(state)

    assert learned == []


def test_report_is_written_even_when_the_pipeline_failed_early(tmp_path):
    state = {
        "incident_id": "INC-BAD",
        "status": "failed",
        "raw_alert": {"source": "nagios"},
        "errors": [{"agent": "alert_ingestion", "error": "Unsupported alert source: 'nagios'"}],
        "audit_log": [],
    }
    update = make_reporting_agent(tmp_path, learn_fn=lambda record: None)(state)

    assert "Failed" in update["report"]
    assert "Unsupported alert source" in update["report"]
    assert (tmp_path / "INC-BAD.md").exists()


def test_knowledge_base_failure_does_not_lose_the_report(tmp_path):
    def broken(record):
        raise RuntimeError("chroma down")

    update = make_reporting_agent(tmp_path, learn_fn=broken)(resolved_state())

    assert update["report"]
    assert (tmp_path / "INC-R1.md").exists()
    assert "knowledge base" in update["errors"][0]["error"]


def test_unwritable_reports_folder_does_not_crash(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("this is a file, not a folder")

    update = make_reporting_agent(blocker / "reports", learn_fn=lambda record: None)(resolved_state())

    assert update["report"]
    assert "report_path" not in update
    assert "could not write report" in update["errors"][0]["error"]


def test_incident_id_cannot_escape_the_reports_folder(tmp_path):
    state = {**resolved_state(), "incident_id": "../evil"}
    update = make_reporting_agent(tmp_path, learn_fn=lambda record: None)(state)

    assert Path(update["report_path"]).parent == tmp_path