from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from opssentinel.agents.approval import approval_gate
from opssentinel.agents.correlation import correlate_incident
from opssentinel.agents.execution import make_execution_agent
from opssentinel.agents.hypothesis import make_hypothesis_agent
from opssentinel.agents.ingestion import ingest_alert
from opssentinel.state import IncidentState
from opssentinel.tools.knowledge_base import search_similar_incidents
from opssentinel.tools.remediation import SimulatedInfrastructure


def _continue_unless_failed(next_node: str):
    def route(state: IncidentState) -> str:
        return END if state.get("status") == "failed" else next_node

    return route


def route_after_hypothesis(state: IncidentState) -> str:
    if state.get("status") not in ("hypothesized", "escalated"):
        return END
    return "approval_gate" if state.get("risk_tier") == "high" else "execution"


def route_after_approval(state: IncidentState) -> str:
    approved = (state.get("approval") or {}).get("decision") == "approved"
    return "execution" if approved else END


def build_graph(llm, infra=None, search_fn=search_similar_incidents, checkpointer=None):
    """Compile the incident-response graph. A checkpointer is required for interrupts."""
    infra = infra if infra is not None else SimulatedInfrastructure()

    builder = StateGraph(IncidentState)
    builder.add_node("ingestion", ingest_alert)
    builder.add_node("correlation", correlate_incident)
    builder.add_node("hypothesis", make_hypothesis_agent(llm, search_fn))
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("execution", make_execution_agent(infra))

    builder.add_edge(START, "ingestion")
    builder.add_conditional_edges(
        "ingestion", _continue_unless_failed("correlation"), {"correlation": "correlation", END: END}
    )
    builder.add_conditional_edges(
        "correlation", _continue_unless_failed("hypothesis"), {"hypothesis": "hypothesis", END: END}
    )
    builder.add_conditional_edges(
        "hypothesis",
        route_after_hypothesis,
        {"approval_gate": "approval_gate", "execution": "execution", END: END},
    )
    builder.add_conditional_edges(
        "approval_gate", route_after_approval, {"execution": "execution", END: END}
    )
    builder.add_edge("execution", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())