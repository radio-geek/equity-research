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
    screener_quote: NotRequired[dict]  # { current_price, market_cap, last_price_updated } from Screener company page
    qoq_highlights: NotRequired[dict]  # {"good": [...], "bad": [...]}
    # Financial evaluation (scorecard, 5-year trend, trend insight)
    financial_scorecard: NotRequired[dict]  # { score, total, verdict, verdict_tier, letter_grade, metrics }
    five_year_trend: NotRequired[dict]  # { headers, rows }
    trend_insight_summary: NotRequired[str]

    # Research outputs (one per node)
    company_overview: str
    company_overview_structured: NotRequired[dict]  # opening, value_chain, business_model_table, key_products, recent_developments
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

    # Links to the actual NSE transcript PDFs used for concall analysis
    concall_transcript_links: NotRequired[list[dict]]  # [{date, link, description}]

    # Q&A and report
    messages: Annotated[list[dict], _message_reducer]
    report_path: NotRequired[str]
    report_payload: NotRequired[dict]
