# Incident INC-CLI-0: HighErrorRate

**Outcome:** Handed to a human: automated handling could not safely finish.

## Alert
- Source: prometheus
- Severity: critical
- Summary: 5xx error rate at 38% for 5m
- Service / host: checkout-api / -
- Triggered at: 2026-10-15T09:12:00Z

## Root-cause analysis
No hypothesis was produced.

## Action
- Proposed: escalate_to_human {}
- Risk tier: low
- Rationale: Automated analysis failed: LLM call failed: AuthenticationError: Error code: 401 - {'error': {'message': 'Invalid API Key', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}
- Approval: not required (low risk)
- Result: escalation recorded for the on-call engineer

## Verification
No verification was performed.

## Post-incident review
No human review was performed.

## Timeline
- 2026-10-29T09:31:40.399980+00:00 [alert_ingestion] alert_normalized: prometheus alert 'HighErrorRate' (critical)
- 2026-10-29T09:31:40.399980+00:00 [correlation] context_built: 5 logs, 6 metrics, 1 deployments, 3 signals; unavailable: none
- 2026-10-29T09:31:40.942274+00:00 [hypothesis] knowledge_retrieved: 3 past incidents, 2 runbooks (RB-001, RB-005)
- 2026-10-29T09:31:41.057430+00:00 [hypothesis] escalated: LLM call failed: AuthenticationError: Error code: 401 - {'error': {'message': 'Invalid API Key', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}
- 2026-10-29T09:31:41.057430+00:00 [execution] escalated: escalation recorded for the on-call engineer
- 2026-10-29T09:31:41.057430+00:00 [notifier] human_notified: escalation notification sent

## Issues
- [hypothesis] LLM call failed: AuthenticationError: Error code: 401 - {'error': {'message': 'Invalid API Key', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}
