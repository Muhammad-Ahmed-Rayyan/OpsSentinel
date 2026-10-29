# Design Rationale

## Why multiple agents, and why not one

An incident passes through stages that differ in what data they need, how much risk they carry, and how they fail. One agent holding every tool would mix those concerns. Splitting them gives four concrete benefits.

1. **Reasoning is separated from authority.** Only the Execution Agent can change infrastructure, and it can only run actions from a fixed catalog. The LLM sees raw log text, which an attacker or a bug could influence, but it can only propose actions by name. It cannot execute anything, and it cannot choose any option's risk tier.
2. **Code does what code does best.** Parsing alerts, filtering duplicates, querying telemetry, calling remediation tools, checking metrics, writing reports and sending notifications are deterministic, so they are plain code: free, instant and exactly repeatable. Only the Hypothesis Agent uses an LLM, because ranking causes and options from messy evidence is the one step that needs reasoning.
3. **Each stage fails and is tested on its own.** A telemetry outage, a bad LLM answer, a failed rollback and a dead notification channel each have a different correct response (see FAILURE_HANDLING.md). Separate agents let each response be written and unit-tested in isolation.
4. **Every step is auditable.** Each agent appends to a shared audit log, which becomes the report timeline.

## Agents and their responsibilities

| Agent | Responsibility | Uses LLM | Can change infrastructure |
|---|---|---|---|
| Ingestion | Normalize Prometheus and Datadog alerts, drop noise and duplicates of an open incident | No | No |
| Correlation | Gather logs, metrics and deployments from the incident window and summarize them as signals | No | No |
| Hypothesis | Retrieve similar past incidents and runbooks, rank root causes, propose a best action and up to two alternatives | Yes | No |
| Approval Gate | Pause for a human decision on a high-risk action; the human can approve the proposal, choose an alternative or reject | No | No |
| Execution | Apply the approved or low-risk action under policy | No | Yes |
| Verification | Re-read the relevant metric and confirm recovery | No | No |
| Review Gate | Pause for a human to confirm, correct or skip the diagnosis of a fixed incident | No | No |
| Reporting | Write the postmortem and learn from confirmed or corrected fixes | No | No |
| Notification nodes | Tell a human when an approval, a review or an escalation needs them | No | No |

The Reporting Agent has no LLM on purpose: every statement in a postmortem comes from the audit log and state, so nothing can be invented.

## Why each tool and data source

- **Alert JSON (two formats):** shows why normalization is a separate responsibility. Real monitoring stacks emit different shapes.
- **Telemetry (logs, metrics, deployments):** the evidence humans gather by hand. The deployment history is what lets the system link an error spike to a release.
- **ChromaDB with a local embedding model, two collections:** past postmortems say what happened before, and runbooks say how to act safely. Retrieval finds both by meaning, not keywords, at no API cost. They are shown to the LLM as different kinds of evidence: past incidents are hints, runbooks are procedures whose cautions must be respected. Runbooks guide the analysis; they do not authorize anything, and a human approval or the catalog's low-risk tier still decides.
- **Action catalog:** the single source of truth for which actions exist, which parameters they need and how risky they are. A test enforces that every action has exactly one runbook.
- **Simulated infrastructure:** lets the full loop, including verification, run safely. Each tool would be replaced by a real adapter in production.
- **Notifier (outbox folder and optional Slack-compatible webhook):** an approval is useless if nobody knows it is waiting. The outbox folder stands in for email and needs no account; the webhook is only used if configured.
- **LLM provider switch:** the model and provider come from environment settings, so the system is not tied to one vendor and survives free-tier model changes.

## How agents communicate

Through a shared, typed incident state managed by LangGraph. Each node reads the state and returns a partial update. Conditional edges choose the next node from the state (for example, high risk goes to the approval gate and a suppressed alert ends the run). There is no free-form agent-to-agent conversation, which keeps behaviour predictable and testable.

## Where humans are involved

- **Before any high-risk action.** The graph pauses with an interrupt. The human sees the alert, likely cause, confidence, the proposed action and its alternatives with their risk tiers, and the rationale. The human can approve the proposal, approve an alternative, or reject. An unclear answer, including an invalid option number, is treated as a rejection.
- **After a verified fix.** A second pause asks the human to confirm the diagnosis, correct the root cause, add a comment, or skip. The review appears in the report, and only confirmed or corrected outcomes are learned.
- **When automation cannot finish.** Failed actions, unverified fixes, unverifiable action types and LLM failures all escalate, and the engineer is notified.
- **Defense in depth.** The Execution Agent independently refuses a high-risk action without a recorded approval, so a routing bug cannot cause an unapproved change.
- **Accountability.** The approver's name, their choice, and the reviewer's decision are recorded in the audit log and in the postmortem.

## Why notifications are separate nodes

When LangGraph resumes a paused node, it runs that node again from its start. A notification sent from inside the approval gate would therefore be sent twice, once on pause and once on resume. Each notification is its own node in front of the gate, and a test proves each message is sent exactly once. A failed notification is recorded but never blocks the incident.

## How feedback improves the system

When an incident ends resolved, meaning the Verification Agent proved recovery and a human confirmed or corrected the diagnosis, the Reporting Agent writes it back to the knowledge base with the approver and reviewer. Future incidents with similar symptoms retrieve it as a hint. Outcomes that were rejected, escalated, unverified or unreviewed are never learned, so a fix that did not work, or a diagnosis nobody checked, cannot be recommended later.

A caveat worth stating: in the demo runs the same simulated incident is replayed, so the system partly retrieves its own earlier run. That demonstrates the mechanism, not an improvement in diagnostic accuracy.