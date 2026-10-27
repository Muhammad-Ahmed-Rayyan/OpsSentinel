# Failure Handling

Every failure below is handled without crashing the pipeline, and every incident still ends with a report. The last column names the test that proves the behaviour.

| Failure | System response | Proving test |
|---|---|---|
| Unsupported or malformed alert | Ingestion records the error, status `failed`, the LLM is never called, a report is still written | `test_ingestion.py::test_agent_records_error_instead_of_crashing_on_bad_alert`, `test_graph.py::test_ingestion_failure_is_reported_without_calling_the_llm` |
| One telemetry source is down | Correlation continues with the others and lists the missing source | `test_correlation.py::test_one_missing_source_degrades_gracefully` |
| All telemetry sources are down | Status `failed`, reported | `test_correlation.py::test_all_sources_missing_fails` |
| Knowledge base is down | Hypothesis continues without past incidents and records the error | `test_hypothesis.py::test_knowledge_base_failure_does_not_stop_analysis` |
| LLM returns non-JSON, an unknown action, missing parameters or out-of-range confidence | One retry with the validation error fed back to the model | `test_hypothesis.py::test_invalid_output_is_retried_with_feedback` |
| LLM stays invalid after the retry | Escalated: a `escalate_to_human` action pages a person | `test_hypothesis.py::test_two_invalid_outputs_escalate_to_human` |
| LLM API error (rate limit, network) | Escalated immediately with no retry, to protect the free quota | `test_hypothesis.py::test_llm_failure_escalates_without_retry`, `test_graph.py::test_llm_failure_pages_a_human_and_is_reported` |
| LLM claims a lower risk than the catalog says | Ignored: the risk tier always comes from the catalog | `test_hypothesis.py::test_risk_tier_comes_from_catalog_not_llm` |
| Human rejects, or gives an unclear answer | Nothing executes, status `rejected`, reported, not learned | `test_graph.py::test_rejected_action_is_reported_but_not_executed_or_learned`, `test_unclear_human_response_counts_as_rejection` |
| High-risk action reaches Execution without approval | Refused, status `failed` | `test_execution.py::test_high_risk_action_is_refused_without_approval` |
| Remediation tool fails (wrong version, unsafe path) | No change, escalated to a human | `test_execution.py::test_failed_remediation_escalates_to_human`, `test_unsafe_log_path_is_refused` |
| LLM adds parameters the action does not declare | Extra parameters are ignored | `test_execution.py::test_extra_parameters_from_llm_are_ignored` |
| Fix applied but the metric does not recover | Retries the check, then escalates, and the incident is not learned | `test_verification.py::test_metric_that_stays_bad_escalates_after_retries`, `test_graph.py::test_fix_that_does_not_work_is_escalated_and_not_learned` |
| Action has no automated verification (for example cache flush) | Escalated for human confirmation rather than claimed as resolved | `test_verification.py::test_action_without_a_rule_needs_a_human` |
| Metric cannot be read | Escalated, no crash | `test_verification.py::test_unreadable_metric_escalates_instead_of_crashing` |
| Report folder is not writable | Report kept in state, error recorded | `test_reporting.py::test_unwritable_reports_folder_does_not_crash` |
| Learning into the knowledge base fails | Report is still written, error recorded | `test_reporting.py::test_knowledge_base_failure_does_not_lose_the_report` |
| Incident id tries to escape the reports folder | Id is sanitized | `test_reporting.py::test_incident_id_cannot_escape_the_reports_folder` |