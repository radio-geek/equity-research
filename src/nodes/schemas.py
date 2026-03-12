"""Pydantic schemas for structured LLM outputs.

Used with OpenAI structured outputs (response_format / text format) or for
parsing and validating JSON from the LLM. See:
- https://developers.openai.com/api/docs/guides/structured-outputs/
- LangChain: llm.with_structured_output(PydanticModel, method="json_schema")
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Company overview ---


class ValueChain(BaseModel):
    """Value chain: stages, company position, description."""
    stages: list[str] = Field(..., description="Ordered list of industry stages")
    company_stage_indices: list[int] = Field(
        default_factory=list,
        description="0-based indices of stages where company operates",
    )
    company_position_description: str = Field(
        "",
        description="2-3 lines describing what the company does in these nodes",
    )
    company_position: str | None = Field(
        None,
        description="Optional short label e.g. Tier-1 supplier",
    )


class BusinessModelRow(BaseModel):
    """One row of the business model table."""
    segment: str = Field(..., description="Segment name")
    importance: Literal["Primary", "Secondary", "Emerging"] = Field(
        ..., description="Importance of segment"
    )
    description: str = Field(..., description="Brief description")


class BusinessModelTable(BaseModel):
    """Business model table with rows."""
    rows: list[BusinessModelRow] = Field(..., description="At least one row")


class RecentDevelopment(BaseModel):
    """One recent development or milestone."""
    year: str = Field(..., description="Year e.g. YYYY")
    event: str = Field(..., description="Short description")


class CompanyOverviewStructured(BaseModel):
    """Structured company overview for report (opening, value chain, table, products, timeline)."""

    opening: str = Field(
        ...,
        description="3-4 lines: what the company does, who it serves, how it makes money",
    )
    value_chain: ValueChain = Field(..., description="Industry value chain and company position")
    business_model_table: BusinessModelTable = Field(..., description="Segment table")
    key_products: list[str] = Field(..., description="5-8 product or service names")
    recent_developments: list[RecentDevelopment] = Field(
        ...,
        description="Chronological milestones with year and event",
    )


# --- Management ---


class ManagementPerson(BaseModel):
    """One promoter/executive/board member."""
    name: str = Field(..., description="Full name")
    designation: str = Field(..., description="e.g. Promoter, MD, Independent Director")
    description: str = Field(..., description="1-3 sentences: background, expertise, tenure")


class GovernanceNewsItem(BaseModel):
    """One governance news item (last 12 months only)."""
    text: str = Field(..., description="Short headline or 1-sentence summary")
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        ..., description="Sentiment of the item"
    )


class ManagementStructured(BaseModel):
    """Structured management and governance output."""

    people: list[ManagementPerson] = Field(
        ...,
        description="Promoters, key executives, board members (typically 5-12)",
    )
    governance_news: list[GovernanceNewsItem] = Field(
        ...,
        description="Governance-only news from last 1 year",
    )
    rpt_and_gaps: str = Field(
        "",
        description="Related party transactions summary and gaps/assumptions",
    )


# --- Sectoral ---


class SectoralStructured(BaseModel):
    """Sectoral analysis: headwinds and tailwinds."""

    analysis: str = Field(
        ...,
        description="1-3 short paragraphs summarising the sector view for this company",
    )
    headwinds: list[str] = Field(
        ...,
        description="2-6 bullets: factors that could destroy revenue or compress margins",
    )
    tailwinds: list[str] = Field(
        ...,
        description="2-6 bullets: factors that could drive revenue growth or margin expansion",
    )


# --- Auditor flags ---


class AuditorEvent(BaseModel):
    """One auditor-related event (qualification, EOM, etc.)."""
    date: str | None = Field(None, description="YYYY-MM or YYYY")
    fy: str | None = Field(None, description="e.g. FY24")
    description: str = Field("", description="Short description of the event")


class AuditorFlagsStructured(BaseModel):
    """Structured auditor flags: summary and timeline of events."""

    summary: str = Field(..., description="Summary of auditor qualifications and events")
    events: list[AuditorEvent] = Field(
        default_factory=list,
        description="Chronological list of audit-related events",
    )
