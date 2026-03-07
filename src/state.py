"""Shared state schema for the equity research graph."""

from typing import Annotated, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


def _message_reducer(left: list, right: list | None) -> list:
    """Append new messages to the list (for follow-up Q&A)."""
    if right is None:
        return left
    return left + right


class ResearchState(TypedDict, total=False):
    """State passed through the research graph.

    All fields are optional so nodes can do partial updates.
    """

    # Set by user / resolve_company
    symbol: str
    exchange: str
    company_name: str
    sector: str
    industry: NotRequired[str]

    # Set by resolve_company (raw data for nodes)
    meta: NotRequired[dict]
    quote: NotRequired[dict]
    shareholding: NotRequired[list]
    financial_ratios: NotRequired[list[dict]]

    # Set by qoq_financials node (yearly + TTM trends, LLM highlights from TTM)
    yearly_metrics: NotRequired[list[dict]]
    qoq_highlights: NotRequired[dict]  # {"good": [...], "bad": [...]}

    # Research outputs (one per node)
    company_overview: str
    management_research: str
    financial_risk: str
    concall_evaluation: str
    concall_section_title: NotRequired[str]  # "Concall Evaluation" or "Company Updates" (SME/no-concall)
    auditor_flags: NotRequired[str]
    sectoral_analysis: str
    sectoral_headwinds: NotRequired[list[str]]
    sectoral_tailwinds: NotRequired[list[str]]
    executive_summary: NotRequired[str]

    # Structured concall (schema-aligned object for report payload)
    concall_structured: NotRequired[dict]

    # Q&A and report
    messages: Annotated[list[dict], _message_reducer]
    report_path: NotRequired[str]
    report_payload: NotRequired[dict]
