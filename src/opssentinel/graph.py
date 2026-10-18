from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from opssentinel.agents.approval import approval_gate
from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.execution import make_execution_agent
from opssentinel.agents.hypothesis import make_hypothesis_agent
from opssentinel.agents.ingestion import ingest_alert
from opssentinel.agents.reporting import DEFAULT_REPORTS_DIR, make_reporting_agent
from opssentinel.agents.verification import make_verification_agent
from opssentinel.state import IncidentState
from opssentinel.tools.knowledge_base import add_postmortem, search_similar_incidents
from opssentinel.tools.remediation import SimulatedInfrastructure


def _continue_unless_failed(next_node: str):
    def route(state: IncidentState) -> str:
        return "reporting" if state.get("status") == "failed" else next_node

    return route


def route_after_hypothesis(state: IncidentState) -> str:
    # "escalated" (LLM failed) still goes to execution so the human gets paged.
    if state.get("status") not in ("hypothesized", "escalated"):
        return "reporting"
    return "approval_gate" if state.get("risk_tier") == "high" else "execution"


def route_after_approval(state: IncidentState) -> str:
    approved = (state.get("approval") or {}).get("decision") == "approved"
    return "execution" if approved else "reporting"


def route_after_execution(state: IncidentState) -> str:
    return "verifier" if state.get("status") == "verifying" else "reporting"


def build_graph(
    llm,
    infra=None,
    search_fn=search_similar_incidents,
    checkpointer=None,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    learn_fn=add_postmortem,
    verify_attempts: int = 3,
    verify_interval_seconds: float = 0.0,
):
    """Compile the incident-response graph. A checkpointer is required for interrupts."""
    infra = infra if infra is not None else SimulatedInfrastructure()

    builder = StateGraph(IncidentState)
    builder.add_node("ingestion", ingest_alert)
    builder.add_node("correlation", correlate_incident)
    builder.add_node("hypothesis", make_hypothesis_agent(llm, search_fn))
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("execution", make_execution_agent(infra))
    builder.add_node(
        "verifier",
        make_verification_agent(infra, verify_attempts, verify_interval_seconds),
    )
    builder.add_node("reporting", make_reporting_agent(reports_dir, learn_fn))

    builder.add_edge(START, "ingestion")
    builder.add_conditional_edges(
        "ingestion",
        _continue_unless_failed("correlation"),
        {"correlation": "correlation", "reporting": "reporting"},
    )
    builder.add_conditional_edges(
        "correlation",
        _continue_unless_failed("hypothesis"),
        {"hypothesis": "hypothesis", "reporting": "reporting"},
    )
    builder.add_conditional_edges(
        "hypothesis",
        route_after_hypothesis,
        {"approval_gate": "approval_gate", "execution": "execution", "reporting": "reporting"},
    )
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"execution": "execution", "reporting": "reporting"},
    )
    builder.add_conditional_edges(
        "execution",
        route_after_execution,
        {"verifier": "verifier", "reporting": "reporting"},
    )
    builder.add_edge("verifier", "reporting")
    builder.add_edge("reporting", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())