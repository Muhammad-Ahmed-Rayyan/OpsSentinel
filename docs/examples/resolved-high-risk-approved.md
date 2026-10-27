# Incident INC-CLI-0: HighErrorRate

**Outcome:** Resolved: the fix was applied and verified.

## Alert
- Source: prometheus
- Severity: critical
- Summary: 5xx error rate at 38% for 5m
- Service / host: checkout-api / -
- Triggered at: 2026-10-15T09:12:00Z

## Root-cause analysis
1. Null handling bug introduced in checkout-api v2.14.0 causing NullPointerException in PaymentValidator.validate, which returns 5xx responses (confidence 0.95)
   - Deployment of checkout-api v2.14.0 (from v2.13.2) occurred 9 min before the alert
   - http_5xx_rate_percent moved from 0.4 to 38.0 (peak 38.0)
   - 4 error-level log lines; most frequent: 'NullPointerException in PaymentValidator.validate' (4x)
   - ERROR logs at 09:04:10, 09:05:30, 09:07:45, 09:10:05 showing NullPointerException in PaymentValidator.validate
   - Similar past incident PM-INC-CLI-0 identified the same root cause and was resolved by rollback
2. Transient upstream timeout to payment-gateway causing downstream 5xx errors (confidence 0.30)
   - WARN log at 09:09:20: Upstream timeout calling payment-gateway
   - High 5xx error rate coinciding with recent deployment (possible correlation)

## Action
- Proposed: rollback_deployment {'service': 'checkout-api', 'target_version': 'v2.13.2'}
- Risk tier: high
- Rationale: The most likely cause is a null handling bug introduced in v2.14.0 that triggers NullPointerExceptions in PaymentValidator.validate, directly matching the error logs and the pattern of a similar past incident that was resolved by rolling back to the previous stable version.
- Approval: approved by dell
- Result: rolled back checkout-api from v2.14.0 to v2.13.2

## Verification
error_rate_percent for checkout-api is 0.5 (limit 5.0) after 1 check(s)

## Timeline
- 2026-10-27T21:50:40.894873+00:00 [alert_ingestion] alert_normalized: prometheus alert 'HighErrorRate' (critical)
- 2026-10-27T21:50:40.896985+00:00 [correlation] context_built: 5 logs, 6 metrics, 1 deployments, 3 signals; unavailable: none
- 2026-10-27T21:50:42.697677+00:00 [hypothesis] hypotheses_ranked: top: Null handling bug introduced in checkout-api v2.14.0 causing NullPointerException in PaymentValidator.validate, which returns 5xx responses (0.95); proposed rollback_deployment [high risk]
- 2026-10-27T21:50:47.216868+00:00 [approval_gate] action_approved: dell: no comment
- 2026-10-27T21:50:47.216868+00:00 [execution] action_executed: rolled back checkout-api from v2.14.0 to v2.13.2 [high risk, dell]
- 2026-10-27T21:50:47.216868+00:00 [verification] verified: error_rate_percent for checkout-api is 0.5 (limit 5.0) after 1 check(s)

## Issues
- none
