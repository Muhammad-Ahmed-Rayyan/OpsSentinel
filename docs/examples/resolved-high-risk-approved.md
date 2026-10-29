# Incident INC-CLI-0: HighErrorRate

**Outcome:** Resolved: the fix was applied and verified.

## Alert
- Source: prometheus
- Severity: critical
- Summary: 5xx error rate at 38% for 5m
- Service / host: checkout-api / -
- Triggered at: 2026-10-15T09:12:00Z

## Root-cause analysis
1. NullPointerException in PaymentValidator.validate introduced by the recent checkout-api v2.14.0 deployment, causing the 5xx error spike. (confidence 0.85)
   - Deployment of checkout-api v2.14.0 (from v2.13.2) occurred 9 min before the alert
   - http_5xx_rate_percent jumped from 0.4% to 38% after the deployment
   - Four error-level log lines all reporting 'NullPointerException in PaymentValidator.validate'
   - Similar past incident PM-001 where a null‑handling bug after a payment refactor was fixed by rolling back
2. Intermittent upstream timeout to the payment‑gateway causing occasional 5xx responses. (confidence 0.30)
   - WARN log at 09:09:20: Upstream timeout calling payment-gateway
   - Elevated 5xx rate coinciding with the timeout warning
3. Sudden traffic surge that exceeded the provisioned capacity of checkout‑api. (confidence 0.10)
   - Critical HighErrorRate alert showing 38% 5xx rate
   - No direct evidence of traffic metrics, but a spike could explain high error rate

## Action
- Proposed: rollback_deployment {'service': 'checkout-api', 'target_version': 'v2.13.2'}
- Risk tier: high
- Rationale: The NPE errors and 5xx spike appear immediately after the v2.14.0 release, matching a known null‑handling bug pattern. RB-001 authorizes a rollback when a recent deployment is the likely cause and no backward‑incompatible DB migration is indicated. Rolling back to v2.13.2 should restore normal behavior.
- Approval: approved by dell
- Alternatives considered:
  - restart_service {'service': 'checkout-api'} [high risk]: If a rollback is blocked (e.g., due to an undocumented DB migration), restarting the service may clear transient error states, though it is unlikely to fix the underlying code bug.
  - escalate_to_human {} [low risk]: If there is uncertainty about migration compatibility or the impact of a rollback, human judgment is required to assess and coordinate the remediation.
- Result: rolled back checkout-api from v2.14.0 to v2.13.2

## Verification
error_rate_percent for checkout-api is 0.5 (limit 5.0) after 1 check(s)

## Post-incident review
- Decision: confirmed by dell

## Timeline
- 2026-10-29T09:29:16.830628+00:00 [alert_ingestion] alert_normalized: prometheus alert 'HighErrorRate' (critical)
- 2026-10-29T09:29:16.830628+00:00 [correlation] context_built: 5 logs, 6 metrics, 1 deployments, 3 signals; unavailable: none
- 2026-10-29T09:29:17.303512+00:00 [hypothesis] knowledge_retrieved: 3 past incidents, 2 runbooks (RB-001, RB-005)
- 2026-10-29T09:29:20.496847+00:00 [hypothesis] hypotheses_ranked: top: NullPointerException in PaymentValidator.validate introduced by the recent checkout-api v2.14.0 deployment, causing the 5xx error spike. (0.85); proposed rollback_deployment [high risk]; 2 alternative(s)
- 2026-10-29T09:29:20.496847+00:00 [notifier] human_notified: approval request notification sent
- 2026-10-29T09:29:27.770055+00:00 [approval_gate] action_approved: dell: no comment
- 2026-10-29T09:29:27.770055+00:00 [execution] action_executed: rolled back checkout-api from v2.14.0 to v2.13.2 [high risk, dell]
- 2026-10-29T09:29:27.770055+00:00 [verification] verified: error_rate_percent for checkout-api is 0.5 (limit 5.0) after 1 check(s)
- 2026-10-29T09:29:27.778948+00:00 [notifier] human_notified: review request notification sent
- 2026-10-29T09:29:30.211370+00:00 [review_gate] review_confirmed: dell: no comment

## Issues
- none
