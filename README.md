<div align="center">

# 🚨 OpsSentinel

*Multi-Agent Incident Response & On-Call Triage with LangGraph*

![Last Commit](https://img.shields.io/github/last-commit/Muhammad-Ahmed-Rayyan/OpsSentinel)
![Python](https://img.shields.io/badge/Python-100%25-blue?logo=python)
![languages](https://img.shields.io/github/languages/count/Muhammad-Ahmed-Rayyan/OpsSentinel)

<br>

Built with the tools and technologies:  
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6446?style=for-the-badge&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-6467F2?style=for-the-badge&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-4A154B?style=for-the-badge&logo=slack&logoColor=white)
![Pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)

</div>

---

## 🧠 Project Summary

**OpsSentinel** is a multi-agent incident response and on-call triage system built with **LangGraph**. It ingests monitoring alerts, correlates logs, metrics and deployments, proposes a root cause with ranked fixes, asks a human before any high-risk action, executes, verifies the result, asks a human to review the diagnosis, writes a postmortem, and learns only from fixes that worked and were confirmed.

It is a backend workflow, not a chatbot. Infrastructure is simulated, so everything runs safely on a laptop.

---

## 🚀 Features

Eight stages share one typed incident state:

- 📥 **Ingestion**  
  Normalizes alerts from different monitoring tools and drops noise and duplicates of an open incident.

- 🔗 **Correlation**  
  Gathers related logs, metrics and recent deployments.

- 🧠 **Hypothesis**  
  Retrieves similar past incidents and runbooks, then uses an LLM to rank causes and propose a best action plus up to two alternatives from a fixed catalog.

- 🛑 **Approval Gate**  
  Pauses the graph until a human approves the proposal, chooses an alternative, or rejects, for high-risk actions.

- ⚙️ **Execution**  
  Applies the action under policy. Low-risk actions run automatically.

- ✅ **Verification**  
  Re-reads metrics to confirm the fix worked.

- 🧑‍💻 **Review Gate**  
  Asks a human to confirm, correct or skip the diagnosis of a verified fix.

- 📝 **Reporting**  
  Writes a postmortem and feeds confirmed or corrected outcomes back into the knowledge base.

- 🔔 **Notifications & Escalation**  
  Notification nodes tell a human when an approval or review is waiting and when an incident is escalated. Anything that fails, is rejected or cannot be verified is escalated, and every incident that opens ends with a report.

- 🧪 **Safe, Cost-Free Testing**  
  Agent and graph tests use a fake LLM and a recording notifier, so the suite costs no API quota.

### 📚 Documentation

- [Architecture and diagrams](docs/ARCHITECTURE.md)
- [Design rationale](docs/DESIGN_RATIONALE.md)
- [Failure handling](docs/FAILURE_HANDLING.md)
- [Alignment with the approved proposal](docs/PROPOSAL_ALIGNMENT.md)
- [Example incident reports and notifications](docs/examples)

---

## 🗃️ Project Structure

```bash
OpsSentinel/
├── data/                               # Sample telemetry, alerts, and seed data for local simulation
│   ├── alerts/
│   │   └── sample_alerts.json          # Example monitoring alerts (5xx error spikes, high disk usage)
│   ├── postmortems/
│   │   └── postmortems.json            # Seed postmortem records for knowledge base vector store
│   ├── runbooks/
│   │   └── runbooks.json               # Seed operational runbooks detailing diagnostic and remediation procedures
│   └── telemetry/
│       ├── deployments.json            # Mock deployment history and commit metadata
│       ├── logs.json                   # Mock application and service log streams
│       └── metrics.json                # Mock service metrics (latency, error rates, CPU, disk utilization)
├── docs/                               # System design, architecture specifications, and documentation
│   ├── examples/                       # Example incident triage reports and notification outputs
│   │   ├── escalated-llm-failure.md    # Walkthrough of escalation due to LLM failure/retry exhaustion
│   │   ├── human-chose-alternative.md  # Walkthrough of human operator selecting an alternative fix
│   │   ├── rejected-by-human.md        # Walkthrough of human operator rejecting a proposed remediation
│   │   ├── resolved-high-risk-approved.md # Walkthrough of approved high-risk action with successful verification
│   │   └── resolved-low-risk.md        # Walkthrough of automated low-risk remediation execution
│   ├── architecture.md                 # System architecture, data flow, state machine, and node interaction diagrams
│   ├── design_rationale.md             # Key engineering decisions, architecture trade-offs, and design choices
│   ├── failure_handling.md             # Error handling, retries, escalation policies, and graceful fallbacks
│   └── proposal_alignment.md           # Alignment matrix mapping implementation to project requirements       
├── scripts/                            # Operational and demonstration utility scripts
│   ├── check_llm.py                    # Connectivity and authentication verification for LLM providers
│   └── demo_filtering.py               # Demonstration of alert deduplication and noise filtering without LLM usage
├── src/                                # Source code root
│   └── opssentinel/                    # Core OpsSentinel package
│       ├── agents/                     # LangGraph workflow agent nodes for incident response lifecycle
│       │   ├── __init__.py             # Agent module exports
│       │   ├── approval.py             # Human-in-the-loop gate for authorizing high-risk remediation actions
│       │   ├── correlation.py          # Correlates alerts with related logs, metrics, and deployment events
│       │   ├── execution.py            # Executes approved or low-risk remediation actions under policy
│       │   ├── hypothesis.py           # RAG-based root cause analysis and action proposal generation
│       │   ├── ingestion.py            # Alert ingestion, normalization, and duplicate suppression
│       │   ├── notify.py               # Generates and dispatches notification payloads for workflow gates
│       │   ├── reporting.py            # Generates postmortem reports and commits verified learnings to knowledge base
│       │   ├── review.py               # Human-in-the-loop review gate for diagnosis confirmation or correction
│       │   └── verification.py         # Re-checks telemetry to verify remediation effectiveness
│       ├── tools/                      # Tool integrations and simulated infrastructure backends
│       │   ├── knowledge_base.py       # ChromaDB vector store integration for past incident postmortems
│       │   ├── monitoring.py           # Telemetry and metric inspection utilities
│       │   ├── remediation.py          # Simulated infrastructure actions (service restart, rollback, cache clear)
│       │   ├── runbooks.py             # ChromaDB vector store integration for operational runbooks
│       │   └── telemetry.py            # Query interfaces for application logs and deployment history
│       ├── __init__.py                 # Package initialization and version definition
│       ├── actions.py                  # Remediation action catalog with assigned risk tiers and parameter definitions
│       ├── audit.py                    # Incident audit logging and execution trail recorder
│       ├── config.py                   # Configuration loader and environment variable schema validation
│       ├── dedup.py                    # Alert fingerprinting, deduplication tracker, and flapping detection
│       ├── graph.py                    # LangGraph StateGraph construction, conditional edges, and routing logic
│       ├── llm.py                      # Multi-provider LLM client factory (OpenRouter, Groq)
│       ├── main.py                     # Interactive CLI entrypoint for running incident response workflows
│       ├── notifier.py                 # Outbox and webhook dispatching for incident notifications
│       ├── schemas.py                  # Pydantic data schemas for alerts, hypotheses, actions, and postmortems
│       └── state.py                    # TypedDict defining the shared incident state across all graph nodes
├── tests/                              # Automated test suite
│   ├── helpers.py                      # Test fixtures, mock LLMs, and dummy state factories
│   ├── test_actions.py                 # Tests for action catalog definitions, parameters, and risk tiers
│   ├── test_alternatives.py            # Tests for alternative action generation and selection handling
│   ├── test_approval_options.py        # Tests for approval gate choices (approve, reject, alternative selection)
│   ├── test_correlation.py             # Tests for telemetry, log, and deployment correlation logic
│   ├── test_dedup.py                   # Tests for alert deduplication, fingerprinting, and window suppression
│   ├── test_execution.py               # Tests for action execution policies and simulation handling
│   ├── test_graph.py                   # End-to-end integration tests for LangGraph state machine execution
│   ├── test_graph_filtering.py         # Tests for graph-level duplicate and noise alert filtering
│   ├── test_graph_notifications.py     # Tests for notification triggers across approval, review, and escalation nodes
│   ├── test_graph_options.py           # Tests for graph branching based on human decision choices
│   ├── test_hypothesis.py              # Tests for root cause hypothesis ranking and structured output parsing
│   ├── test_hypothesis_runbooks.py     # Tests for runbook retrieval and prompt augmentation in hypothesis generation
│   ├── test_ingestion.py               # Tests for alert ingestion, payload parsing, and validation
│   ├── test_knowledge_base.py          # Tests for vector store postmortem retrieval and query formatting
│   ├── test_learning.py                # Tests for learning from verified fixes and updating knowledge base
│   ├── test_notifier.py                # Tests for file outbox writing and webhook delivery
│   ├── test_reporting.py               # Tests for postmortem markdown formatting and summary generation
│   ├── test_review.py                  # Tests for human review gate behavior and diagnosis confirmation/correction
│   ├── test_runbooks.py                # Tests for runbook ingestion and semantic search retrieval
│   ├── test_state.py                   # Tests for incident state initialization and schema updates
│   └── test_verification.py            # Tests for post-remediation health check and verification evaluation
├── .env.example                        # Template for environment variables (LLM provider keys, webhook URLs)
├── .gitignore                          # Git ignore rules for virtual environments, caches, and local outputs
├── pyproject.toml                      # Package build configuration, project metadata, and dependency definitions
├── README.md                           # Main project overview, architecture summary, and quickstart guide
└── requirements.txt                    # Project runtime and development dependencies
```

---

## 🔧 Setup & Installation

> Make sure Python and Git are installed on your system.

```bash
# Clone the repo
git clone https://github.com/Muhammad-Ahmed-Rayyan/OpsSentinel.git
cd OpsSentinel

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# Install the project with dev dependencies
pip install -e ".[dev]"

# Create your environment file
copy .env.example .env
```

> The first run downloads a local embedding model (about 80 MB).

---

## 🔑 API Configuration

Edit the `.env` file you just created:

```.env
LLM_PROVIDER="groq"                      # groq or openrouter
YOUR-PROVIDER-API-KEY="YOUR-API-KEY"     # API key for the chosen provider (see .env.example for the exact variable name)
YOUR-PROVIDER-MODEL="YOUR-MODEL-NAME"    # Model name for the chosen provider (see .env.example for the exact variable name)
SLACK_WEBHOOK_URL=""                     # Optional: leave empty to write notifications to the notifications folder only
```

> Model names change over time. If you get a "model not found" error, check the provider's current model list.

---

## ⚙️ Run the Project

Check the LLM connection first:

```bash
python scripts\check_llm.py
```

Then run an incident:

```bash
# Checkout 5xx spike after a deployment (high risk: approval + diagnosis review)
python -m opssentinel.main --alert 0

# Disk almost full (low risk: auto-fixed, then diagnosis review)
python -m opssentinel.main --alert 1
```

- 🔴 **`--alert 0`:** High risk, so you are asked to approve (or choose an alternative), then asked to review the diagnosis.
- 🟢 **`--alert 1`:** Low risk, so it is fixed automatically, then you review the diagnosis.

Reports are written to `reports/` and notifications to `notifications/`.

To see duplicate and noise filtering without spending any LLM quota:

```bash
python scripts\demo_filtering.py
```

---

## 🧪 Tests

```bash
# Run the full suite
pytest

# Skip tests that need the embedding model
pytest -m "not integration"
```

---

## ⚠️ Known Limitations

- 🧩 Infrastructure and telemetry are simulated. Real use needs adapters for the monitoring, deployment and infrastructure APIs behind the tool layer.
- 💾 The checkpointer and duplicate tracker are in memory, so pending approvals/reviews and open incidents are lost if the process exits. A persistent checkpointer (SQLite or Postgres) fixes this.
- ⏳ There is no approval timeout or re-paging if nobody responds.
- 1️⃣ It handles one incident per command-line run. Duplicate filtering is shown by tests and a demo script, not by the CLI.
- 📖 Learning trusts verified outcomes that a human confirmed or corrected, with no pruning of old entries. Runbooks are static and do not learn.
- ✏️ The review lets the engineer confirm, correct the root cause or comment, but not edit the full report text.
- 💬 The Slack-compatible webhook is tested with a stand-in, not against a live workspace.
- 📊 Risk tiers are static. They do not yet consider time of day, blast radius or recent incident history.
- 🤖 Free-tier LLMs can be unreliable at strict JSON. The agent retries once and then escalates, and a stronger model is more dependable.
- 🔌 REST wrappers around the tools and MCP integration are not implemented.

---

<div align="center">

⭐ Found this project useful? Give it a star on GitHub!

</div>