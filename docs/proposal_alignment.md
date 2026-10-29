# Alignment with the Approved Case Study Proposal

Status: Done, Partly, Simulated or Not done. "Simulated" means the behaviour exists but runs against sample data instead of live systems.

| Proposal item | Status | What was built or what differs |
|---|---|---|
| 1-2. Problem statement and existing workflow | Done | Existing-process diagram and README |
| 3. Alert normalization across tools | Done | Prometheus and Datadog formats normalized into one schema |
| 3. Log and metric correlation | Done | Correlation Agent, simulated sources |
| 3. Search past incidents and runbooks | Done | Postmortems and runbooks in separate ChromaDB collections, both retrieved |
| 3. Draft the postmortem | Done | Reporting Agent |
| 3. Update the knowledge base | Done | Only verified, human-confirmed or corrected outcomes are learned |
| 5. Six agents | Done, with changes | Verification split into its own agent, and a post-incident Review Gate and notification nodes added |
| 6. Ingestion: normalize alerts | Done | |
| 6. Ingestion: filter noise or duplicates | Done | Severity threshold plus suppression of repeats while an incident is open. Open incidents are held in memory |
| 6. Correlation: group related signals into one context | Done | Context plus summarized signals |
| 6. Hypothesis: retrieve similar incidents, propose a cause | Done | |
| 6. Hypothesis: ranked list of remediation options | Done | Best action plus up to two alternatives; the approver can choose any of them |
| 6. Execution: low-risk auto, high-risk to a human | Done | Catalog-defined risk tiers; remediation tools are simulated |
| 6. Approval gate presents action and reasoning | Done | LangGraph interrupt with options, risk tiers and rationale |
| 6. Reporting: timeline, cause, resolution, write-back | Done | |
| 7. Monitoring and alerting APIs | Simulated | Sample JSON in Prometheus and Datadog formats, no live calls |
| 7. Log and metrics query APIs | Simulated | JSON files behind a tool layer |
| 7. Infrastructure or remediation APIs | Simulated | In-memory infrastructure model |
| 7. Slack or email for the approval gate | Done in simulation | An outbox folder stands in for email, and a Slack-compatible webhook is supported. The webhook is tested with a stand-in, not against a live Slack workspace |
| 8. Live alert and monitoring streams | Simulated | Static sample data |
| 8. Vector database of postmortems and runbooks | Done | Two ChromaDB collections |
| 8. Deployment and change history | Done | Simulated |
| 9. Human approval before high-risk actions | Done | Enforced in the graph and again in the Execution Agent |
| 9. Human review of the postmortem before it is finalized | Partly | The engineer confirms, corrects the root cause, adds a comment or skips. The full report text is not editable |
| 9. Human-reviewed outcome fed back | Done | Only confirmed or corrected outcomes are learned |
| 10. Expected outcome | Done | Every listed capability runs end to end (see docs/examples) |
| 11. LangGraph, LLM, ChromaDB, Python | Done | |
| 11. REST APIs for tool calls | Not done | Tools are Python functions |
| 11. MCP "where applicable" | Not done | Not integrated; explored separately in Task 6 Part B |

## What was deliberately left out, and why

Live monitoring streams and real infrastructure APIs cannot be tested or demonstrated honestly without real systems, and the approved expected outcome describes a simulated alert. REST wrappers around the tools would add network failure modes without adding a capability, because the tools run in the same process. MCP integration would require an asynchronous refactor and new dependencies on a working, tested system, and the Task 6 brief said it was not required for the case study. Each is a clean next step behind the existing tool layer.