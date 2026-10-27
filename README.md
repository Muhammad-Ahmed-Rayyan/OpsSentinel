# OpsSentinel

A multi-agent incident response and on-call triage system built with LangGraph. It ingests monitoring alerts, correlates logs, metrics and deployments, proposes a root cause and a fix, asks a human before any high-risk action, executes, verifies the result, writes a postmortem, and learns from fixes that worked.

It is a backend workflow, not a chatbot. Infrastructure is simulated, so everything runs safely on a laptop.

## How it works

Seven agents share one typed incident state:

1. **Ingestion** normalizes alerts from different monitoring tools
2. **Correlation** gathers related logs, metrics and recent deployments
3. **Hypothesis** retrieves similar past incidents and uses an LLM to rank causes and propose one action from a fixed catalog
4. **Approval Gate** pauses the graph until a human approves high-risk actions
5. **Execution** applies the action under policy
6. **Verification** re-reads metrics to confirm the fix worked
7. **Reporting** writes a postmortem and feeds verified outcomes back into the knowledge base

Low-risk actions run automatically. High-risk ones wait for a human. Anything that fails, is rejected or cannot be verified is escalated, and every incident ends with a report.

Documentation:
- [Architecture and diagrams](docs/ARCHITECTURE.md)
- [Design rationale](docs/DESIGN_RATIONALE.md)
- [Failure handling](docs/FAILURE_HANDLING.md)

## Quick start (Windows)

```
git clone <repo-url>
cd OpsSentinel
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Edit `.env`: choose `LLM_PROVIDER` (`groq` or `openrouter`), set that provider's API key, and set its model name. Model names change over time, so check the provider's current list if you get a "model not found" error.

Check the connection, then run an incident:

```
python scripts\check_llm.py
python -m opssentinel.main --alert 0
python -m opssentinel.main --alert 1
```

- `--alert 0`: checkout 5xx spike after a deployment. High risk, so you are asked to approve a rollback.
- `--alert 1`: disk almost full. Low risk, so it is cleaned up automatically.

The first run downloads a local embedding model (about 80 MB). Reports are written to `reports/`.

## Tests

```
pytest
pytest -m "not integration"
```

The second command skips tests that need the embedding model. Agent tests use a fake LLM, so the suite costs no API quota.

## Project structure

```
src/opssentinel/
  agents/        ingestion, correlation, hypothesis, approval, execution, verification, reporting
  tools/         telemetry, monitoring, remediation (simulated), knowledge_base (ChromaDB)
  actions.py     action catalog with fixed risk tiers
  graph.py       LangGraph wiring and routing
  llm.py         provider switch (OpenRouter or Groq) driven by .env
  main.py        command-line runner with human approval prompt
data/            sample alerts, mock telemetry, seed postmortems
docs/            architecture, rationale, failure handling
tests/           one test module per component
```

## Known limitations

- Infrastructure and telemetry are simulated. Real use needs adapters for the monitoring, deployment and infrastructure APIs behind the tool layer.
- The checkpointer is in memory, so a pending approval is lost if the process exits. A persistent checkpointer (SQLite or Postgres) fixes this.
- There is no approval timeout or re-paging if nobody responds.
- It handles one incident at a time, with no alert deduplication or storm handling.
- Learning trusts verified outcomes only, but low-risk fixes are learned without human review, and there is no pruning of old entries.
- Risk tiers are static. They do not yet consider time of day, blast radius or recent incident history.
- Free-tier LLMs can be unreliable at strict JSON. The agent retries once and then escalates, and a stronger model is more dependable.
- MCP is not implemented. Exposing the telemetry and remediation tools as an MCP server is a natural next step.