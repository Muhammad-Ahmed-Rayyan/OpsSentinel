# Incident INC-CLI-0: HighErrorRate

**Outcome:** Handed to a human: automated handling could not safely finish.

## Alert
- Source: prometheus
- Severity: critical
- Summary: 5xx error rate at 38% for 5m
- Service / host: checkout-api / -
- Triggered at: 2026-10-15T09:12:00Z

## Root-cause analysis
1. The checkout-api v2.14.0 deployment introduced a NullPointerException in PaymentValidator.validate, causing the 5xx error spike. (confidence 0.92)
   - Deployment of checkout-api v2.14.0 occurred 9 minutes before the alert
   - http_5xx_rate_percent jumped from 0.4% to 38.0% after the deployment
   - Four error-level log lines with 'NullPointerException in PaymentValidator.validate'
   - Similar past incident PM-INC-CLI-0 where the same bug was fixed by rolling back
2. An intermittent upstream timeout to the payment-gateway generated request failures that contributed to the 5xx rate. (confidence 0.35)
   - WARN log at 09:09:20Z: Upstream timeout calling payment-gateway
   - Temporal proximity to the error spike
3. A stale in‑memory cache of payment‑validation data caused validation logic to fail, leading to 5xx responses. (confidence 0.12)
   - No direct evidence, but cache‑related issues are a known secondary cause of validation failures

## Action
- Proposed: restart_service {'service': 'checkout-api'}
- Risk tier: high
- Rationale: If a rollback cannot be performed immediately, restarting all checkout‑api instances may clear transient state and reduce error rates, though it is unlikely to fix the underlying code bug.
- Approval: approved by dell (chose option 2 instead of rollback_deployment)
- Alternatives considered:
  - rollback_deployment {'service': 'checkout-api', 'target_version': 'v2.13.2'} [high risk]: Runbook RB-001 authorizes a rollback when a recent deployment correlates with a critical error spike and no backward‑incompatible DB migration is present. The deployment introduced a NullPointerException that matches the error logs and mirrors a previously resolved incident. Rolling back to v2.13.2 should restore normal operation.
  - clear_cache {'service': 'checkout-api'} [low risk]: If cache corruption is suspected, flushing the checkout‑api cache could resolve validation errors. Caution: flushing during peak load may increase database pressure, so this should be considered only if the rollback is not feasible.
- Result: restarted all instances of checkout-api

## Verification
error_rate_percent for checkout-api is still 38.0 (limit 5.0) after 3 checks

## Post-incident review
No human review was performed.

## Timeline
- 2026-10-29T09:30:59.389141+00:00 [alert_ingestion] alert_normalized: prometheus alert 'HighErrorRate' (critical)
- 2026-10-29T09:30:59.389141+00:00 [correlation] context_built: 5 logs, 6 metrics, 1 deployments, 3 signals; unavailable: none
- 2026-10-29T09:30:59.875839+00:00 [hypothesis] knowledge_retrieved: 3 past incidents, 2 runbooks (RB-001, RB-005)
- 2026-10-29T09:31:02.786752+00:00 [hypothesis] hypotheses_ranked: top: The checkout-api v2.14.0 deployment introduced a NullPointerException in PaymentValidator.validate, causing the 5xx error spike. (0.92); proposed rollback_deployment [high risk]; 2 alternative(s)
- 2026-10-29T09:31:02.786752+00:00 [notifier] human_notified: approval request notification sent
- 2026-10-29T09:31:06.199241+00:00 [approval_gate] action_approved: dell: no comment (chose option 2: restart_service)
- 2026-10-29T09:31:06.199241+00:00 [execution] action_executed: restarted all instances of checkout-api [high risk, dell]
- 2026-10-29T09:31:06.199241+00:00 [verification] verification_failed: error_rate_percent for checkout-api is still 38.0 (limit 5.0) after 3 checks
- 2026-10-29T09:31:06.199241+00:00 [notifier] human_notified: escalation notification sent

## Issues
- [verification] error_rate_percent for checkout-api is still 38.0 (limit 5.0) after 3 checks
