"""Pydantic schemas for structured LLM outputs.

Used with OpenAI structured outputs (response_format / text format) or for
parsing and validating JSON from the LLM. See:
- https://developers.openai.com/api/docs/guides/structured-outputs/
- LangChain: llm.with_structured_output(PydanticModel, method="json_schema")
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


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
    """Structured management output."""

    people: list[ManagementPerson] = Field(
        ...,
        description="Promoters, key executives, board members (typically 5-12)",
    )
    governance_news: list[GovernanceNewsItem] = Field(
        default_factory=list,
        description="Deprecated; governance analysis moved to auditor_flags node",
    )
    management_narrative: str = Field(
        default="",
        validation_alias=AliasChoices("management_narrative", "rpt_and_gaps"),
        description=(
            "Short markdown: management track record, strategy, board effectiveness; "
            "data gaps. Do not include related party transactions (RPT)."
        ),
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


class SectoralFromTranscripts(BaseModel):
    """Headwinds/tailwinds extracted directly from concall transcript text."""
    headwinds: list[str] = Field(
        default_factory=list,
        description="Challenges/risks management explicitly mentioned",
    )
    tailwinds: list[str] = Field(
        default_factory=list,
        description="Opportunities/growth drivers management explicitly mentioned",
    )


# --- Auditor flags ---


class AuditorEvent(BaseModel):
    """One governance / auditor finding card (max 5 per report)."""

    date: str | None = Field(None, description="YYYY-MM or YYYY")
    fy: str | None = Field(None, description="e.g. FY24")
    category: str | None = Field(
        None,
        description=(
            "One of: Board remuneration, Related party, Auditor report, "
            "Receivables & working capital, Contingent liabilities, Other"
        ),
    )
    type: str = Field(
        "Other",
        description=(
            "Specific label e.g. Qualified Opinion, Emphasis of Matter, CARO, "
            "Related Party Disclosure, Contingent liability, Inventory build-up, "
            "Receivable ageing, Loans & advances, Remuneration spike, Other"
        ),
    )
    signal: str = Field(
        "yellow",
        description="Exactly one of: red (material risk), yellow (moderate / monitor), green (clean / positive)",
    )
    issue: str = Field("", description="What was found and why it matters (1–3 sentences)")
    evidence: str | None = Field(
        None, description="Exact AR note, section, or short quoted language when possible"
    )
    status: str | None = Field(
        None, description="Resolved, Recurring, or Pending when applicable"
    )

    @model_validator(mode="before")
    @classmethod
    def _coalesce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        issue = (out.get("issue") or "").strip()
        desc = (out.get("description") or "").strip()
        if not issue and desc:
            out["issue"] = desc
        out.pop("description", None)
        if not (out.get("type") or "").strip():
            out["type"] = "Other"
        cl = (out.get("concern_level") or "").lower()
        if "signal" not in out or not out.get("signal"):
            if out.get("is_red_flag") or "hard" in cl:
                out["signal"] = "red"
            elif "soft" in cl:
                out["signal"] = "yellow"
            elif "follow" in cl:
                out["signal"] = "yellow"
            else:
                out["signal"] = "yellow"
        out.pop("concern_level", None)
        out.pop("is_red_flag", None)
        out.pop("management_response", None)
        out.pop("follow_up_question", None)
        return out


class AuditorFlagsStructured(BaseModel):
    """Single governance verdict + top findings (cap 5)."""

    verdict: str = Field(
        "OK",
        description="Overall governance verdict: exactly one of RISK, OK, GOOD",
    )
    summary: str = Field(
        "",
        description="2–4 sentence plain text explanation supporting the verdict",
    )
    events: list[AuditorEvent] = Field(
        default_factory=list,
        description="At most 5 findings, most material first. Use signal red/yellow/green.",
    )


# --- Concall per-transcript extraction ---


class ConcallEventItem(BaseModel):
    """One major event announced in a concall."""
    type: str = Field(
        ...,
        description="acquisition|fundraise|stake_sale|capex|order_win|mgmt_change|guidance_change",
    )
    headline: str = Field(..., description="Short headline ≤12 words")
    details: list[str] = Field(default_factory=list)


class ConcallQAItem(BaseModel):
    """One Q&A highlight from a concall."""
    q: str
    a: str


class ConcallCapexItem(BaseModel):
    """One capex project mentioned in a concall."""
    project: str
    amount: str
    funding: str = ""


class ConcallCardExtraction(BaseModel):
    """Content extracted from a single concall transcript."""

    bullets: list[str] = Field(
        default_factory=list,
        description="6-9 highlights: financial first, then operational",
    )
    events: list[ConcallEventItem] = Field(default_factory=list)
    qaHighlights: list[ConcallQAItem] = Field(default_factory=list)
    guidance: Optional[str] = None
    capex: list[ConcallCapexItem] = Field(default_factory=list)


class GuidanceCell(BaseModel):
    """One cell in the guidance table."""
    value: str
    trend: Literal["raised", "cut", "maintained", "neutral"] = "neutral"


class GuidanceRow(BaseModel):
    """One row in the guidance table (one metric across quarters)."""
    metric: str
    cells: list[GuidanceCell]


class ConcallSummaryExtraction(BaseModel):
    """Summary and guidance table assembled from all extracted cards."""

    summary: str = Field(..., description="One sentence overall summary of recent concall trends")
    guidance_table_rows: list[GuidanceRow] = Field(default_factory=list)
