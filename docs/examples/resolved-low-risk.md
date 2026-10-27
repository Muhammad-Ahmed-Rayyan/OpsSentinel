# Incident INC-CLI-1: Disk usage above 95% on log-server-02

**Outcome:** Resolved: the fix was applied and verified.

## Alert
- Source: datadog
- Severity: high
- Summary: Disk usage above 95% on log-server-02
- Service / host: - / log-server-02
- Triggered at: 2026-10-15T09:15:00Z

## Root-cause analysis
1. Log rotation job failed to delete/compress old log files, causing accumulation of logs that filled the disk (confidence 0.78)
   - disk_usage_percent moved from 82.0 to 96.8 (peak 96.8)
   - error-level log line: 'Log rotation failed: no space left on device'
   - WARN log at 09:02: Disk usage at 88% on /var/log
   - ERROR log at 09:08: Log rotation failed: no space left on device
   - ERROR log at 09:14: Write failed: no space left on device
   - Similar past incident PM-002 where cleanup_old_logs resolved a disk‑full log server caused by failed rotation
2. Sudden surge in log volume (e.g., application error flood) rapidly consumed available disk space (confidence 0.55)
   - disk_usage_percent jumped from 82% to 96.8% within minutes
   - multiple error logs appearing in a short time window
3. Insufficient disk allocation for /var/log partition relative to retention policy (confidence 0.35)
   - Disk usage already high (82%) before the spike
   - No recent deployments or configuration changes that would explain the jump

## Action
- Proposed: cleanup_old_logs {'host': 'log-server-02', 'path': '/var/log'}
- Risk tier: low
- Rationale: The most likely cause is a failed log rotation job that left old logs on the filesystem, mirroring a known past incident where deleting archived logs on the same host restored disk health. Removing old log files from /var/log should immediately free space and prevent further write failures.
- Approval: not required (low risk)
- Result: removed archived logs under /var/log on log-server-02; disk usage 96.8% -> 55.0%

## Verification
disk_usage_percent for log-server-02 is 55.0 (limit 80.0) after 1 check(s)

## Timeline
- 2026-10-27T21:38:10.581546+00:00 [alert_ingestion] alert_normalized: datadog alert 'Disk usage above 95% on log-server-02' (high)
- 2026-10-27T21:38:10.599334+00:00 [correlation] context_built: 3 logs, 5 metrics, 0 deployments, 2 signals; unavailable: none
- 2026-10-27T21:38:13.229045+00:00 [hypothesis] hypotheses_ranked: top: Log rotation job failed to delete/compress old log files, causing accumulation of logs that filled the disk (0.78); proposed cleanup_old_logs [low risk]
- 2026-10-27T21:38:13.231062+00:00 [execution] action_executed: removed archived logs under /var/log on log-server-02; disk usage 96.8% -> 55.0% [low risk, auto-approved (low risk)]
- 2026-10-27T21:38:13.234080+00:00 [verification] verified: disk_usage_percent for log-server-02 is 55.0 (limit 80.0) after 1 check(s)

## Issues
- none
