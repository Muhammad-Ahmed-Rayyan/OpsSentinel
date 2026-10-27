# Design Rationale

## Why multiple agents, and why not one

An incident passes through stages that differ in what data they need, how much risk they carry, and how they fail. One agent holding every tool would mix those concerns. Splitting them gives four concrete benefits.

1. **Reasoning is separated from authority.** Only the Execution Agent can change infrastructure, and it can only run actions from a fixed catalog. The LLM sees raw log text, which an attacker or a bug could influence, but it can only propose an action by name. It cannot execute anything, and it cannot choose its own risk tier.
2. **Code does what code does best.** Parsing alerts, querying telemetry, calling remediation tools and checking metrics are deterministic, so they are plain code: free, instant and exactly repeatable. Only the Hypothesis Agent uses an LLM, because ranking causes from messy evidence is the one step that needs reasoning.
3. **Each stage fails and is tested on its own.** A telemetry outage, a bad LLM answer and a failed rollback each have a different correct response (see FAILURE_HANDLING.md). Separate agents let each response be written and unit-tested in isolation.
4. **Every step is auditable.** Each agent appends to a shared audit log, which becomes the report timeline.

## Agents and their responsibilities

| Agent | Responsibility | Uses LLM | Can change infrastructure |
|---|---|---|---|
| Ingestion | Normalize Prometheus and Datadog alerts into one format | No | No |
| Correlation | Gather logs, metrics and deployments from the incident window and summarize them as signals | No | No |
| Hypothesis | Retrieve similar past incidents, rank root causes, propose one catalog action | Yes | No |
| Approval Gate | Pause for a human decision on high-risk actions | No | No |
| Execution | Apply the approved or low-risk action under policy | No | Yes |
| Verification | Re-read the relevant metric and confirm recovery | No | No |
| Reporting | Write the postmortem and learn from verified fixes | No | No |

The Reporting Agent has no LLM on purpose: every statement in a postmortem comes from the audit log and state, so nothing can be invented.

## Why each tool and data source

- **Alert JSON (two formats):** shows why normalization is a separate responsibility. Real monitoring stacks emit different shapes.
- **Telemetry (logs, metrics, deployments):** the evidence humans gather by hand. The deployment history is what lets the system link an error spike to a release.
- **ChromaDB with a local embedding model:** retrieval finds past incidents by meaning, not keywords, at no API cost. Past incidents are given to the LLM as hints.
- **Action catalog:** the single source of truth for which actions exist, which parameters they need and how risky they are.
- **Simulated infrastructure:** lets the full loop, including verification, run safely. Each tool would be replaced by a real adapter in production.
- **LLM provider switch:** the model and provider come from environment settings, so the system is not tied to one vendor and survives free-tier model changes.

## How agents communicate

Through a shared, typed incident state managed by LangGraph. Each node reads the state and returns a partial update. Conditional edges choose the next node from the state (for example, high risk goes to the approval gate). There is no free-form agent-to-agent conversation, which keeps behaviour predictable and testable.

## Where humans are involved

- **Before any high-risk action.** The graph pauses with an interrupt. The human sees the alert, likely cause, confidence, proposed action, parameters and rationale. Only an explicit approval proceeds; a rejection or an unclear answer is treated as a rejection.
- **When automation cannot finish.** Failed actions, unverified fixes, unverifiable action types and LLM failures all escalate to a human.
- **Defense in depth.** The Execution Agent independently refuses a high-risk action without a recorded approval, so a routing bug cannot cause an unapproved change.
- **Accountability.** The approver's name and comment are recorded in the audit log and in the postmortem.

## How feedback improves the system

When an incident ends resolved, meaning the Verification Agent proved recovery, the Reporting Agent writes it back to the knowledge base with its approver. Future incidents with similar symptoms retrieve it as a hint. Outcomes that were rejected, escalated or unverified are never learned, so a fix that did not work cannot be recommended later.

In a demo run, approving the checkout rollback made that incident appear among the top results for a later query about 5xx errors after a deployment.