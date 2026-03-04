"""LangGraph definition: parallel research, aggregate, follow-up loop, report on 'I am Done'."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.state import ResearchState
from src.nodes.aggregate import aggregate
from src.nodes.auditor_flags import auditor_flags
from src.nodes.company_overview import company_overview
from src.nodes.concall_evaluator import concall_evaluator
from src.nodes.financial_risk import financial_risk
from src.nodes.follow_up import follow_up, should_generate_report
from src.nodes.management import management
from src.nodes.report_generator import report_generator
from src.nodes.resolve_company import resolve_company
from src.nodes.sectoral import sectoral


def _fan_out_research(_state: ResearchState) -> list[str]:
    """After resolve_company, run all six research nodes in parallel."""
    return [
        "company_overview",
        "management",
        "financial_risk",
        "auditor_flags",
        "concall_evaluator",
        "sectoral",
    ]


def _route_after_follow_up(state: ResearchState) -> str:
    """If user said 'I am Done', go to report_generator; else loop to follow_up."""
    if should_generate_report(state):
        return "report_generator"
    return "follow_up"


def build_graph():
    """Build and compile the research graph with checkpointer."""
    graph = StateGraph(ResearchState)

    graph.add_node("resolve_company", resolve_company)
    graph.add_node("company_overview", company_overview)
    graph.add_node("management", management)
    graph.add_node("financial_risk", financial_risk)
    graph.add_node("auditor_flags", auditor_flags)
    graph.add_node("concall_evaluator", concall_evaluator)
    graph.add_node("sectoral", sectoral)
    graph.add_node("aggregate", aggregate)
    graph.add_node("follow_up", follow_up)
    graph.add_node("report_generator", report_generator)

    graph.add_edge(START, "resolve_company")
    graph.add_conditional_edges("resolve_company", _fan_out_research)

    graph.add_edge("company_overview", "aggregate")
    graph.add_edge("management", "aggregate")
    graph.add_edge("financial_risk", "aggregate")
    graph.add_edge("auditor_flags", "aggregate")
    graph.add_edge("concall_evaluator", "aggregate")
    graph.add_edge("sectoral", "aggregate")

    graph.add_edge("aggregate", "follow_up")
    graph.add_conditional_edges("follow_up", _route_after_follow_up)
    graph.add_edge("report_generator", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)
