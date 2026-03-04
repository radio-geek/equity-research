"""Shared prompt fragments and LLM invocation helper."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.config import get_llm, get_openai_api_key, get_openai_model, get_tavily_api_key

logger = logging.getLogger(__name__)


def _invoke_openai_responses_web_search(system: str, user_content: str) -> str | None:
    """Use OpenAI Responses API with built-in web_search_preview. Returns text or None on failure."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=get_openai_api_key())
        response = client.responses.create(
            model=get_openai_model(),
            instructions=system,
            input=user_content,
            tools=[{"type": "web_search_preview", "search_context_size": "high"}],
            max_output_tokens=16000,
        )
        return getattr(response, "output_text", None) or ""
    except Exception as e:
        logger.debug("OpenAI Responses API web search failed: %s", e)
        return None


def _get_web_search_tools() -> list:
    """Return Tavily search tool list if TAVILY_API_KEY is set; else empty."""
    api_key = get_tavily_api_key()
    if not api_key:
        return []
    try:
        from langchain_tavily import TavilySearch
        return [
            TavilySearch(
                max_results=5,
                search_depth="advanced",
                topic="finance",
                include_answer=True,
                tavily_api_key=api_key,
            )
        ]
    except ImportError:
        return []


def _run_tool_calls(tools: list, tool_calls: list) -> list[ToolMessage]:
    """Execute tool calls and return ToolMessage list."""
    name_to_tool = {t.name: t for t in tools}
    out = []
    for tc in tool_calls:
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
        tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
        tool = name_to_tool.get(name)
        if not tool:
            out.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tid))
            continue
        try:
            result = tool.invoke(args)
            content = result if isinstance(result, str) else json.dumps(result, default=str)
        except Exception as e:
            content = f"Error: {e}"
        out.append(ToolMessage(content=content, tool_call_id=tid))
    return out


def invoke_llm(system: str, user_content: str, use_web_search: bool = True) -> str:
    """Call OpenAI; use built-in web search (Responses API) or Tavily when enabled. Returns assistant text."""
    if use_web_search:
        text = _invoke_openai_responses_web_search(system, user_content)
        if text is not None:
            return text
        tools = _get_web_search_tools()
        if tools:
            llm = get_llm(tools=tools)
            messages = [SystemMessage(content=system), HumanMessage(content=user_content)]
            for _ in range(5):
                msg = llm.invoke(messages)
                if not getattr(msg, "tool_calls", None):
                    return msg.content if hasattr(msg, "content") else str(msg)
                messages.append(msg)
                messages.extend(_run_tool_calls(tools, msg.tool_calls))
            return getattr(messages[-1], "content", "") or ""
    llm = get_llm(tools=None)
    msg = llm.invoke([SystemMessage(content=system), HumanMessage(content=user_content)])
    return msg.content if hasattr(msg, "content") else str(msg)


def _serialize(data: Any) -> str:
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, default=str)
    return str(data)


_WEB_SEARCH_INSTRUCTION = " When useful, use the web search tool to fetch the latest news and data to enrich your answer."


def company_overview_prompt(company_name: str, symbol: str, meta: dict, quote: dict) -> tuple[str, str]:
    system = "You are an equity research analyst. Write a concise company overview (2–4 short paragraphs). Focus on business description, listed exchange, sector, key products/services, and recent context from the data. Be factual and neutral." + _WEB_SEARCH_INSTRUCTION
    user = f"Company: {company_name} (symbol: {symbol}).\n\nMeta: {_serialize(meta)}\n\nQuote/trade info: {_serialize(quote)}\n\nWrite the company overview."
    return system, user


def management_prompt(company_name: str, symbol: str, meta: dict, shareholding: list) -> tuple[str, str]:
    system = "You are an equity research analyst. Summarize management and governance: quality of management, promoter/shareholding pattern, any governance or related-party concerns visible from the data. Keep it to 2–3 short paragraphs. If data is thin, say so." + _WEB_SEARCH_INSTRUCTION
    user = f"Company: {company_name} (symbol: {symbol}).\n\nMeta: {_serialize(meta)}\n\nShareholding pattern (quarterly): {_serialize(shareholding)}\n\nWrite the management research summary."
    return system, user


def financial_risk_prompt(company_name: str, symbol: str, ratios: list[dict], quote: dict) -> tuple[str, str]:
    system = "You are an equity research analyst. Summarize financial risk: comment on ROE, ROCE, debt/equity, interest coverage, liquidity if present. Highlight strengths and risks in 2–3 short paragraphs." + _WEB_SEARCH_INSTRUCTION
    user = f"Company: {company_name} (symbol: {symbol}).\n\nFinancial ratios: {_serialize(ratios)}\n\nQuote/trade info: {_serialize(quote)}\n\nWrite the financial risk summary."
    return system, user


def balance_sheet_highlights_prompt(
    company_name: str,
    symbol: str,
    period_label: str,
    income_statement_text: str,
    balance_sheet_text: str,
) -> tuple[str, str]:
    """Prompt for good/bad highlights from TTM income statement and latest balance sheet."""
    system = """You are an equity research analyst. You will be given TTM (trailing twelve months) income statement and the latest balance sheet (values in Crores where applicable).

Your task: List 3–6 short, specific GOOD points and 3–6 short, specific BAD (or concerning) points from the balance sheet. You may use the TTM income statement for context (e.g. profitability vs debt). Focus on the balance sheet: liquidity, leverage, asset quality, working capital, contingent liabilities, and any red or green flags.

Output format exactly as below. Use only "GOOD:" and "BAD:" as section headers. Each point must be one line starting with "- ".

GOOD:
- point one
- point two

BAD:
- point one
- point two"""

    user = (
        f"Company: {company_name} (symbol: {symbol}). Period: {period_label}.\n\n"
        "TTM Income statement (Crores):\n" + (income_statement_text or "(not available)") + "\n\n"
        "Balance sheet (Crores):\n" + (balance_sheet_text or "(not available)") + "\n\n"
        "List GOOD and BAD points from the balance sheet in the exact format requested."
    )
    return system, user


def auditor_flags_prompt(company_name: str, symbol: str, exchange: str) -> tuple[str, str]:
    system = """You are an expert equity research analyst and forensic accountant specializing in audit quality assessment for Indian listed companies.

Your task: Research and identify ALL auditor qualifications, emphasis of matter, going concern doubts, and CARO/secretarial audit observations for the company across the last 5 annual reports.

SEARCH STRATEGY:
1. Search "{company} {symbol} annual report auditor qualification" and "{company} auditor report emphasis of matter"
2. Search "{company} CARO qualification" and "{company} secretarial audit observations"
3. Search "{company} going concern" and "{company} audit qualified opinion"
4. Check BSE/NSE filings, company website, Screener.in, Trendlyne, MoneyControl
5. Look for auditor changes — a sudden change of auditor is itself a red flag

IDENTIFY AND DOCUMENT:
For each finding:
- Financial year (e.g. FY24, FY25)
- Type: Qualified Opinion / Emphasis of Matter / Going Concern / CARO Qualification / Secretarial Audit / Auditor Resignation / Other
- Exact nature of the qualification (what was the issue)
- Management's explanation or response
- Status: RESOLVED (issue fixed in later year) / RECURRING (appeared in multiple years) / PENDING (latest year, unresolved)
- Impact on financials if quantifiable

Also flag:
- Auditor changes (especially Big-4 → small firm, or voluntary resignation)
- Delays in annual report filing
- Restatement of financials
- Related-party transaction concerns raised by auditor

CRITICAL OUTPUT FORMAT:
Return ONLY valid HTML. Start with <div class="audit-section"> and end with </div>.
NO markdown, NO code blocks, NO text outside the HTML tags.

Use EXACTLY these CSS classes (they are pre-styled):
- audit-section — outer wrapper
- audit-clean — green box if NO qualifications found (clean opinion)
- audit-summary-bar — 1-line summary bar at top (red if issues, green if clean)
- audit-flag-card — individual qualification card
- audit-flag-header — card header with FY and qualification type
- audit-flag-badge — badge for type; add one of: badge-qualified / badge-emphasis / badge-going-concern / badge-caro / badge-secretarial / badge-auditor-change
- audit-flag-status — status chip; add one of: status-resolved / status-recurring / status-pending
- audit-flag-body — card body with details
- audit-flag-mgmt — management response paragraph
- audit-flag-impact — financial impact line (if any)
- audit-overview — bottom summary paragraph

HTML STRUCTURE TO FOLLOW EXACTLY:
<div class="audit-section">
  <div class="audit-summary-bar audit-has-flags">⚠ 3 Auditor Qualifications Found (FY22–FY25) — 1 Recurring, 1 Pending</div>
  <div class="audit-flag-card">
    <div class="audit-flag-header">
      FY25
      <span class="audit-flag-badge badge-qualified">Qualified Opinion</span>
      <span class="audit-flag-status status-pending">Pending</span>
    </div>
    <div class="audit-flag-body">
      <p><strong>Issue:</strong> Auditors qualified the standalone financial statements regarding non-provision of ₹XX Cr disputed liability related to...</p>
      <p class="audit-flag-mgmt"><strong>Management response:</strong> Management believes the likelihood of outflow is remote and has obtained a legal opinion.</p>
      <p class="audit-flag-impact"><strong>Financial impact:</strong> Potential liability of ₹XX Cr not recognized in books.</p>
    </div>
  </div>
  <div class="audit-flag-card">
    <div class="audit-flag-header">FY24–FY22 (Recurring)<span class="audit-flag-badge badge-emphasis">Emphasis of Matter</span><span class="audit-flag-status status-recurring">Recurring</span></div>
    <div class="audit-flag-body">
      <p><strong>Issue:</strong> ...</p>
      <p class="audit-flag-mgmt"><strong>Management response:</strong> ...</p>
    </div>
  </div>
  <div class="audit-overview">
    <p>Overall audit quality assessment: ...</p>
  </div>
</div>

If NO qualifications found across all years:
<div class="audit-section">
  <div class="audit-summary-bar audit-clean-bar">✓ Clean Audit Opinions — No Qualifications in Last 5 Years</div>
  <div class="audit-clean">
    <p>The company has received unqualified (clean) audit opinions for all available annual reports. No emphasis of matter, CARO qualifications, or secretarial audit concerns were identified.</p>
  </div>
</div>"""

    user = (
        f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange})\n\n"
        "Search for all auditor qualifications, emphasis of matter, going concern opinions, "
        "CARO qualifications, secretarial audit observations, and auditor changes for the last 5 years.\n"
        "Document each finding with: FY, type, exact issue, management response, status (resolved/recurring/pending).\n"
        "Flag recurring issues especially prominently — these are the most concerning for investors.\n"
        "Return the complete structured HTML only."
    )
    return system, user


def _last_8_quarters() -> list[str]:
    """Compute the 8 most recently completed Indian fiscal quarters, latest first.

    Indian FY runs 1 Apr – 31 Mar.
    Q1 = Apr–Jun, Q2 = Jul–Sep, Q3 = Oct–Dec, Q4 = Jan–Mar.
    Returns labels like ['Q3 FY26 (Oct–Dec 2025)', 'Q2 FY26 (Jul–Sep 2025)', ...]
    """
    today = date.today()
    m, y = today.month, today.year

    # Determine currently ongoing quarter
    if 4 <= m <= 6:
        cur_q, cur_fy = 1, y + 1
    elif 7 <= m <= 9:
        cur_q, cur_fy = 2, y + 1
    elif 10 <= m <= 12:
        cur_q, cur_fy = 3, y + 1
    else:  # Jan–Mar
        cur_q, cur_fy = 4, y

    def prev_q(q, fy):
        return (4, fy - 1) if q == 1 else (q - 1, fy)

    def label(q, fy):
        month_ranges = {1: "Apr–Jun", 2: "Jul–Sep", 3: "Oct–Dec", 4: "Jan–Mar"}
        cal_year = fy if q == 4 else fy - 1
        return f"Q{q} FY{str(fy)[2:]} ({month_ranges[q]} {cal_year})"

    # Start from the last completed quarter (one before current)
    q, fy = prev_q(cur_q, cur_fy)
    quarters = []
    for _ in range(8):
        quarters.append(label(q, fy))
        q, fy = prev_q(q, fy)
    return quarters


def concall_prompt(company_name: str, symbol: str, exchange: str) -> tuple[str, str]:
    quarters = _last_8_quarters()  # e.g. ['Q3 FY26 (Oct–Dec 2025)', ..., 'Q4 FY24 (Jan–Mar 2024)']
    quarters_numbered = "\n".join(f"  Card-{i+1}: {q}" for i, q in enumerate(quarters))
    guidance_header_cols = " | ".join(f"<th>{q.split(' (')[0]}</th>" for q in reversed(quarters))

    system = f"""You are an expert equity research analyst specializing in management quality and earnings call analysis for Indian listed companies.

INDIAN FISCAL YEAR: April 1 – March 31.
  Q1 = Apr–Jun | Q2 = Jul–Sep | Q3 = Oct–Dec | Q4 = Jan–Mar

THE EXACT 8 QUARTERS YOU MUST COVER (latest first):
{quarters_numbered}

RULE — CONCALL vs PRESS RELEASE:
  ★ ALWAYS search for the earnings conference call (concall) FIRST for every quarter.
  ★ Use badge "concall-badge" if a concall was held — even if you only find a summary.
  ★ Use "press-release-badge" ONLY if you confirm NO concall was held and only a BSE/NSE press release exists.
  ★ Use "ppt-badge" ONLY if only an investor presentation exists and no concall was held.
  ★ Use "missing-badge" if nothing was found for that quarter.
  ★ NEVER substitute a press release for a concall when the company did hold one.

SEARCH STRATEGY (for EACH quarter in the list above):
1. Search: "{company_name} {symbol} concall Q3 FY26" — replace with each quarter
2. Sources: Trendlyne, Screener.in, company IR page, BSE filings, Moneycontrol, Economic Times, LiveMint
3. If no concall found after searching: look for BSE press release / investor PPT as fallback only

ANALYSIS REQUIRED per quarter (keep each card to MAX 3–4 bullet points for brevity):
- Revenue, EBITDA/NIM, PAT vs any prior guidance (1 line)
- 1–2 key management highlights
- Guidance given for next quarter/year (specific numbers)
- Red flags if any: guidance cuts, margin pressure, management changes

CAPEX & MAJOR DEVELOPMENTS (MANDATORY — generate this section BEFORE the guidance table):
- List ALL capex announcements, factory/plant expansions, acquisitions, fundraising (QIP/NCD/rights)
  across all 8 quarters with amounts and funding source
- This section MUST always be present even if content is minimal

GUIDANCE TRACKING:
- Track guidance across all 8 quarters
- Classification: RAISED (number moved up or "will exceed") / CUT (number moved down) / MAINTAINED (same range)
- Use class="guidance-raised" / "guidance-cut" / "guidance-maintained" on table cells

MISSING CONCALL:
- If a quarter genuinely had NO concall, show a .no-concall-alert with what was found (press release/PPT/nothing)

CRITICAL OUTPUT FORMAT:
Return ONLY valid HTML. Start with <div class="concall-section"> and end with </div>.
NO markdown, NO code blocks, NO text outside HTML tags.
Close every opened <div> tag — the HTML MUST be balanced.

CSS classes to use (pre-styled):
concall-section | concall-section-header | concall-cards-grid
concall-card concall-card-N (N=1 most recent → N=8 oldest)
concall-card-header | concall-type-badge
concall-badge | press-release-badge | ppt-badge | missing-badge
capex-section | capex-item | capex-amount | capex-funding
guidance-section | guidance-table | guidance-raised | guidance-cut | guidance-maintained
no-concall-alerts | no-concall-alert | no-concall-reason

HTML STRUCTURE (follow this ORDER exactly — capex comes BEFORE guidance table):
<div class="concall-section">
  <div class="concall-section-header">Summary sentence.</div>
  <div class="concall-cards-grid">
    <div class="concall-card concall-card-1">
      <div class="concall-card-header">{quarters[0]}<span class="concall-type-badge concall-badge">Concall</span></div>
      <ul><li><strong>Revenue:</strong> ₹X Cr (+X% YoY)</li><li>Key highlight</li><li>Key highlight 2</li></ul>
      <p><em>Guidance: ...</em></p>
    </div>
    <!-- concall-card-2 through concall-card-8 — same structure, max 3–4 bullets each -->
  </div>
  <div class="capex-section">
    <h3>Capital Expenditure &amp; Major Developments</h3>
    <div class="capex-item"><strong>Project name</strong> — <span class="capex-amount">₹X,XXX Cr</span> announced Q2 FY25<br><span class="capex-funding">Funding: internal accruals + term loan</span></div>
  </div>
  <div class="guidance-section">
    <h3>Guidance Tracker</h3>
    <table class="guidance-table">
      <thead><tr><th>Metric</th>{guidance_header_cols}<th>Trend</th></tr></thead>
      <tbody><tr><td><strong>Metric name</strong></td><td>value</td><td class="guidance-maintained">value</td><td class="guidance-cut">value</td><td class="guidance-cut">CUT ▼</td></tr></tbody>
    </table>
    <p style="font-size:9pt;color:#555;">Green=Raised | Red=Cut | Yellow=Maintained</p>
  </div>
  <div class="no-concall-alerts">
    <!-- only include if at least one quarter had no concall; omit entire div otherwise -->
  </div>
</div>"""

    quarters_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(quarters))
    user = (
        f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange})\n\n"
        f"Search for earnings conference calls for each of these 8 quarters (latest first):\n{quarters_list}\n\n"
        "For EACH quarter: first search for a concall; only fall back to press release/PPT if you confirm no concall was held.\n"
        "Cover actuals (Revenue, EBITDA, PAT), guidance given, key highlights, and capex/developments.\n"
        "Track guidance changes across quarters — flag cuts with management's stated reasoning.\n"
        "Return the complete structured HTML only."
    )
    return system, user


def sectoral_prompt(company_name: str, sector: str) -> tuple[str, str]:
    system = "You are an equity research analyst. List sectoral headwinds and tailwinds for the near future. Consider regulation, macro, competition, and industry trends. Keep it to 2–3 short paragraphs." + _WEB_SEARCH_INSTRUCTION
    user = f"Company: {company_name}. Sector/industry: {sector or 'Not specified'}.\n\nWrite the sectoral headwinds and tailwinds."
    return system, user


def aggregate_prompt(
    company_overview: str,
    management_research: str,
    financial_risk: str,
    concall_evaluation: str,
    sectoral_analysis: str,
) -> tuple[str, str]:
    system = "You are an equity research analyst. Write a short executive summary (1–2 paragraphs) that ties together the company overview, management, financial risk, concall evaluation, and sectoral view. Highlight key takeaways and risks."
    user = (
        f"Company overview:\n{company_overview}\n\nManagement:\n{management_research}\n\n"
        f"Financial risk:\n{financial_risk}\n\nConcall evaluation:\n{concall_evaluation}\n\n"
        f"Sectoral:\n{sectoral_analysis}\n\nWrite the executive summary."
    )
    return system, user
