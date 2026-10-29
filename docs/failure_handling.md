# Failure Handling

Every failure below is handled without crashing the pipeline, and every incident that opens still ends with a report. The last column names the test that proves the behaviour.

| Failure | System response | Proving test |
|---|---|---|
| Unsupported or malformed alert | Ingestion records the error, status `failed`, the LLM is never called, a report is still written | `test_ingestion.py::test_agent_records_error_instead_of_crashing_on_bad_alert`, `test_graph.py::test_ingestion_failure_is_reported_without_calling_the_llm` |
| Informational alert below the severity threshold | Suppressed as noise, no incident opens | `test_dedup.py::test_low_severity_alert_is_suppressed_as_noise` |
| Repeat of an alert while its incident is open | Suppressed with a pointer to the original, no LLM call, no second report | `test_graph_filtering.py::test_duplicate_alert_during_an_open_incident_is_suppressed_without_calling_the_llm` |
| Same alert after the incident was closed | Opens a new incident, because the fix may not have held | `test_graph_filtering.py::test_same_alert_after_the_incident_closed_opens_a_new_incident` |
| One telemetry source is down | Correlation continues with the others and lists the missing source | `test_correlation.py::test_one_missing_source_degrades_gracefully` |
| All telemetry sources are down | Status `failed`, reported | `test_correlation.py::test_all_sources_missing_fails` |
| Knowledge base is down | Hypothesis continues without past incidents and records the error | `test_hypothesis.py::test_knowledge_base_failure_does_not_stop_analysis` |
| Runbook search is down | Hypothesis continues without runbooks and records the error | `test_hypothesis_runbooks.py::test_runbook_failure_does_not_stop_the_analysis` |
| LLM returns non-JSON, an unknown action, missing parameters or out-of-range confidence | One retry with the validation error fed back to the model | `test_hypothesis.py::test_invalid_output_is_retried_with_feedback` |
| LLM stays invalid after the retry | Escalated: the proposed action becomes `escalate_to_human` | `test_hypothesis.py::test_two_invalid_outputs_escalate_to_human` |
| LLM API error (rate limit, network) | Escalated immediately with no retry, to protect the free quota | `test_hypothesis.py::test_llm_failure_escalates_without_retry`, `test_graph.py::test_llm_failure_pages_a_human_and_is_reported` |
| LLM claims a lower risk than the catalog says | Ignored: risk tiers always come from the catalog | `test_hypothesis.py::test_risk_tier_comes_from_catalog_not_llm`, `test_alternatives.py::test_llm_cannot_lower_an_alternatives_risk_tier` |
| LLM proposes an invalid, duplicate or free-text alternative | The alternative is dropped and counted; the analysis continues | `test_alternatives.py::test_invalid_alternatives_are_dropped_without_failing_the_analysis` |
| Human rejects, or gives an unclear answer | Nothing executes, status `rejected`, reported, not learned | `test_graph.py::test_rejected_action_is_reported_but_not_executed_reviewed_or_learned`, `test_graph.py::test_unclear_human_response_counts_as_rejection` |
| Approver names an option that does not exist | Treated as a rejection, never as a default approval | `test_approval_options.py::test_an_unclear_option_is_a_rejection_not_a_default_approval`, `test_graph_options.py::test_an_out_of_range_choice_is_a_rejection` |
| High-risk action reaches Execution without approval | Refused, status `failed` | `test_execution.py::test_high_risk_action_is_refused_without_approval` |
| Remediation tool fails (wrong version, unsafe path) | No change, escalated to a human | `test_execution.py::test_failed_remediation_escalates_to_human`, `test_execution.py::test_unsafe_log_path_is_refused` |
| LLM adds parameters the action does not declare | Extra parameters are ignored | `test_execution.py::test_extra_parameters_from_llm_are_ignored` |
| Fix applied but the metric does not recover | Retries the check, then escalates; not reviewed and not learned | `test_verification.py::test_metric_that_stays_bad_escalates_after_retries`, `test_graph.py::test_fix_that_does_not_work_is_escalated_and_not_reviewed_or_learned` |
| Action has no automated verification (for example cache flush) | Escalated for human confirmation rather than claimed as resolved | `test_verification.py::test_action_without_a_rule_needs_a_human` |
| Metric cannot be read | Escalated, no crash | `test_verification.py::test_unreadable_metric_escalates_instead_of_crashing` |
| Reviewer skips, or gives an unclear answer | Incident is reported, nothing is learned | `test_review.py::test_unclear_answers_are_treated_as_skipped`, `test_graph.py::test_unknown_review_answer_counts_as_skipped`, `test_reporting.py::test_unconfirmed_review_is_reported_but_not_learned` |
| Approval message would be sent again when the gate resumes | It is sent exactly once, because notification is a separate node | `test_graph_notifications.py::test_approval_request_is_notified_once_even_though_the_gate_resumes` |
| Escalated or failed incident | The on-call engineer is notified | `test_graph_notifications.py::test_escalated_incident_notifies_the_on_call_engineer` |
| A notification channel is down | The incident carries on, the failure is recorded, working channels still deliver | `test_graph_notifications.py::test_notification_failure_does_not_stop_the_incident`, `test_notifier.py::test_composite_delivers_to_working_channels_and_reports_the_broken_one` |
| Webhook URL is not https | Refused at startup | `test_notifier.py::test_webhook_refuses_a_non_https_url` |
| Report folder is not writable | Report kept in state, error recorded | `test_reporting.py::test_unwritable_reports_folder_does_not_crash` |
| Learning into the knowledge base fails | Report is still written, error recorded | `test_reporting.py::test_knowledge_base_failure_does_not_lose_the_report` |
| Incident id tries to escape a report or outbox folder | Id is sanitized | `test_reporting.py::test_incident_id_cannot_escape_the_reports_folder`, `test_notifier.py::test_outbox_file_names_cannot_escape_the_folder` |