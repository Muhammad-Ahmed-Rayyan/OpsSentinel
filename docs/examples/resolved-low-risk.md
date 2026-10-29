# Incident INC-CLI-1: Disk usage above 95% on log-server-02

**Outcome:** Resolved: the fix was applied and verified.

## Alert
- Source: datadog
- Severity: high
- Summary: Disk usage above 95% on log-server-02
- Service / host: - / log-server-02
- Triggered at: 2026-10-15T09:15:00Z

## Root-cause analysis
1. Log rotation job failure caused old and archived logs to accumulate, filling the /var/log volume on log-server-02. (confidence 0.75)
   - disk_usage_percent moved from 82.0 to 96.8 (peak 96.8)
   - error-level log line: 'Log rotation failed: no space left on device'
   - WARN log at 09:02: Disk usage at 88% on /var/log
   - ERROR log at 09:08: Log rotation failed: no space left on device
   - ERROR log at 09:14: Write failed: no space left on device
   - Similar past incident PM-002 where failed log rotation filled the volume and cleanup_old_logs resolved it
2. A sudden increase in application logging volume (e.g., due to a bug or higher log level) rapidly consumed disk space. (confidence 0.20)
   - Rapid rise in disk usage from 82% to 96.8% within minutes
   - Error messages about write failures indicating writes were attempted until the disk filled
3. Non‑log files (e.g., backup archives, core dumps) were written to the same filesystem and consumed space. (confidence 0.05)
   - No direct evidence in the provided logs, but disk filling can also be caused by unrelated large files

## Action
- Proposed: cleanup_old_logs {'host': 'log-server-02', 'path': '/var/log'}
- Risk tier: low
- Rationale: Runbook RB-002 prescribes cleaning up archived logs under /var/log when disk usage exceeds 95% and log rotation has failed. The evidence points to log rotation failure as the primary cause, and no recent deployment rules out a rollback. Performing cleanup follows the approved procedure and may reduce usage below the 80% threshold; if it does not, escalation is required.
- Approval: not required (low risk)
- Alternatives considered:
  - restart_service {'service': 'logrotate'} [high risk]: Restarting the log rotation daemon could allow it to resume normal operation after space is freed, but the root cause is likely accumulation of old logs, so cleanup is the preferred first step.
- Result: removed archived logs under /var/log on log-server-02; disk usage 96.8% -> 55.0%

## Verification
disk_usage_percent for log-server-02 is 55.0 (limit 80.0) after 1 check(s)

## Post-incident review
- Decision: confirmed by dell

## Timeline
- 2026-10-29T09:30:03.050354+00:00 [alert_ingestion] alert_normalized: datadog alert 'Disk usage above 95% on log-server-02' (high)
- 2026-10-29T09:30:03.050354+00:00 [correlation] context_built: 3 logs, 5 metrics, 0 deployments, 2 signals; unavailable: none
- 2026-10-29T09:30:03.540673+00:00 [hypothesis] knowledge_retrieved: 3 past incidents, 2 runbooks (RB-002, RB-001)
- 2026-10-29T09:30:06.372447+00:00 [hypothesis] hypotheses_ranked: top: Log rotation job failure caused old and archived logs to accumulate, filling the /var/log volume on log-server-02. (0.75); proposed cleanup_old_logs [low risk]; 1 alternative(s)
- 2026-10-29T09:30:06.372447+00:00 [execution] action_executed: removed archived logs under /var/log on log-server-02; disk usage 96.8% -> 55.0% [low risk, auto-approved (low risk)]
- 2026-10-29T09:30:06.372447+00:00 [verification] verified: disk_usage_percent for log-server-02 is 55.0 (limit 80.0) after 1 check(s)
- 2026-10-29T09:30:06.372447+00:00 [notifier] human_notified: review request notification sent
- 2026-10-29T09:30:08.686031+00:00 [review_gate] review_confirmed: dell: no comment

## Issues
- none
