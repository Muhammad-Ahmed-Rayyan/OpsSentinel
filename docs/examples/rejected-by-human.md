# Incident INC-CLI-0: HighErrorRate

**Outcome:** Not fixed: a human reviewer rejected the proposed action.

## Alert
- Source: prometheus
- Severity: critical
- Summary: 5xx error rate at 38% for 5m
- Service / host: checkout-api / -
- Triggered at: 2026-10-15T09:12:00Z

## Root-cause analysis
1. Null handling bug introduced in checkout-api v2.14.0 causing NullPointerException in PaymentValidator.validate, which returns 5xx responses (confidence 0.85)
   - Deployment of checkout-api v2.14.0 (from v2.13.2) occurred 9 min before the alert
   - http_5xx_rate_percent jumped from 0.4% to 38.0%
   - 4 error-level log lines with 'NullPointerException in PaymentValidator.validate'
   - Recent logs show repeated NPEs on web-01 and web-02 after the deployment
2. Intermittent upstream timeout to payment-gateway causing downstream 5xx errors (confidence 0.30)
   - WARN log at 09:09:20Z: Upstream timeout calling payment-gateway
   - Potential correlation between external provider latency and error responses
3. Sudden traffic spike overwhelming checkout-api instances (confidence 0.10)
   - High 5xx error rate observed for 5 minutes
   - No explicit traffic metrics provided, but a spike could contribute

## Action
- Proposed: rollback_deployment {'service': 'checkout-api', 'target_version': 'v2.13.2'}
- Risk tier: high
- Rationale: The most supported hypothesis is a bug in the newly released v2.14.0 that triggers NullPointerExceptions in PaymentValidator.validate, directly matching the error logs and 5xx surge. Rolling back to the last known good version (v2.13.2) is the remediation that resolved identical incidents in the past.
- Approval: rejected by dell

## Verification
No verification was performed.

## Timeline
- 2026-10-27T21:50:54.054704+00:00 [alert_ingestion] alert_normalized: prometheus alert 'HighErrorRate' (critical)
- 2026-10-27T21:50:54.058347+00:00 [correlation] context_built: 5 logs, 6 metrics, 1 deployments, 3 signals; unavailable: none
- 2026-10-27T21:50:56.217614+00:00 [hypothesis] hypotheses_ranked: top: Null handling bug introduced in checkout-api v2.14.0 causing NullPointerException in PaymentValidator.validate, which returns 5xx responses (0.85); proposed rollback_deployment [high risk]
- 2026-10-27T21:50:59.882759+00:00 [approval_gate] action_rejected: dell: no comment

## Issues
- none
