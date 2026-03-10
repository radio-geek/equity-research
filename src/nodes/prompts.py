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


def invoke_llm(
    system: str,
    user_content: str,
    use_web_search: bool = True,
    use_tavily_only: bool = False,
) -> str:
    """Call OpenAI; use built-in web search (Responses API) or Tavily when enabled. Returns assistant text.

    When use_tavily_only=True, skip OpenAI web search and use Tavily search only (if TAVILY_API_KEY is set).
    """
    tools = _get_web_search_tools() if (use_web_search or use_tavily_only) else []
    if use_web_search and not use_tavily_only:
        text = _invoke_openai_responses_web_search(system, user_content)
        if text is not None:
            return text
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


def _reference_date_context() -> str:
    """Return a line telling the model today's date so 'latest' / 'current' are unambiguous."""
    return (
        f"\n\nReference date (today): {date.today().isoformat()}. "
        "When the task or any data refers to 'latest', 'current', or 'recent', interpret it relative to this date."
    )


def company_overview_prompt(company_name: str, symbol: str, meta: dict, quote: dict) -> tuple[str, str]:
    system = (
        "Role: Act as a Senior Equity Research Analyst specializing in the Industrials and Manufacturing sector.\n\n"
        "Task: Conduct a deep-dive web search and write a comprehensive business overview for the company provided in the user message.\n\n"
        "Output Format: Strictly Markdown. No HTML. Use ## for section headings and **bold** text for emphasis.\n\n"
        "Requirements:\n\n"
        "**What the company does:** Start with one clear, plain-language sentence: \"[Company name] is a [sector] company that [how it makes money].\" "
        "Follow with 1–2 paragraphs detailing their day-to-day operations, target customers, and market positioning.\n\n"
        "**Segment Mix & Revenue:** Create a Markdown table with columns: Segment / Business Line, Revenue Share or Role, and Description. "
        "If exact percentages aren't available, use \"Primary,\" \"Secondary,\" or \"Emerging\" based on recent annual reports. "
        "Add a paragraph explaining the **Revenue Model**: Who pays them, what are the main cost drivers, and what is the geographic split (Domestic vs. Export).\n\n"
        "**Key Products/Services:** Provide a bulleted list of 5–8 specific, high-value offerings. Avoid generic filler; use technical product names found in their catalog.\n\n"
        "**Timeline:** Provide a bulleted list of up to 8 major milestones (Listing year, M&A, capacity expansions, or regulatory shifts) in the format \"YYYY – Event.\"\n\n"
        "**Evidence-Based:** Use inline citations for all financial data and key facts. End with a **Sources** section listing the URLs used (Annual Reports, Exchange Filings, and Financial Portals). Use markdown links [text](url).\n\n"
        "Goal: The reader must finish this section knowing exactly how the company functions as a business unit, without any \"fluff\" or generic industry descriptions."
    ) + _reference_date_context() + _WEB_SEARCH_INSTRUCTION
    user = (
        f"Company: {company_name} (symbol: {symbol}).\n\n"
        f"Meta: {_serialize(meta)}\n\nQuote/trade info: {_serialize(quote)}\n\n"
        "Write the comprehensive business overview in Markdown following the required structure. "
        "Prefer: concall PPT, company website, annual reports, BSE/NSE filings, and ValuePickr forum for evidence."
    )
    return system, user


def management_prompt(company_name: str, symbol: str, meta: dict, shareholding: list) -> tuple[str, str]:
    system = "You are an equity research analyst. Summarize management and governance: quality of management, promoter/shareholding pattern, any governance or related-party concerns visible from the data. Keep it to 2–3 short paragraphs. If data is thin, say so." + _reference_date_context() + _WEB_SEARCH_INSTRUCTION
    user = f"Company: {company_name} (symbol: {symbol}).\n\nMeta: {_serialize(meta)}\n\nShareholding pattern (quarterly): {_serialize(shareholding)}\n\nWrite the management research summary."
    return system, user


def financial_risk_prompt(company_name: str, symbol: str, ratios: list[dict], quote: dict) -> tuple[str, str]:
    system = "You are an equity research analyst. Summarize financial risk: comment on ROE, ROCE, debt/equity, interest coverage, liquidity if present. Highlight strengths and risks in 2–3 short paragraphs." + _reference_date_context() + _WEB_SEARCH_INSTRUCTION
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
- point two""" + _reference_date_context()

    user = (
        f"Company: {company_name} (symbol: {symbol}). Period: {period_label}.\n\n"
        "TTM Income statement (Crores):\n" + (income_statement_text or "(not available)") + "\n\n"
        "Balance sheet (Crores):\n" + (balance_sheet_text or "(not available)") + "\n\n"
        "List GOOD and BAD points from the balance sheet in the exact format requested."
    )
    return system, user


def trend_insight_prompt(company_name: str, symbol: str, five_year_table_text: str) -> tuple[str, str]:
    """Prompt for 2-3 line interpretation of 5-year financial trend."""
    system = (
        "You are an equity research analyst. Given a 5-year financial trend table (Revenue, PAT, margins, ROE, debt, cash flow), "
        "write a short interpretation in 2–3 sentences. Cover: revenue and profit trend, margin trajectory, debt trend, and cash flow. "
        "Be factual and concise. No bullet points; plain prose only."
    ) + _reference_date_context()
    user = (
        f"Company: {company_name} (symbol: {symbol}).\n\n5-Year Financial Trend:\n{five_year_table_text}\n\n"
        "Write 2–3 sentences summarising the trend."
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
</div>""" + _reference_date_context()

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

═══════════════════════════════════════════════════════════
STEP 1 — DETECT COMPANY TYPE (do this FIRST via web search)
═══════════════════════════════════════════════════════════
Search: "{company_name} {symbol} SME IPO NSE SME BSE SME"
Also check: company market cap, listing board, whether results are quarterly or half-yearly.

Classify the company as one of:
  A) MAINBOARD_WITH_CONCALLS   — Listed on NSE/BSE mainboard AND holds quarterly concalls
  B) MAINBOARD_NO_CONCALLS     — Mainboard listed but never/rarely holds concalls
  C) SME_COMPANY               — Listed on NSE Emerge or BSE SME platform

SME indicators: "NSE Emerge", "BSE SME", market cap typically < ₹500 Cr, half-yearly results filing,
no regular concall history, results published as BSE filings without management call.

═══════════════════════════════════════════════════════════
STEP 2A — IF MAINBOARD_WITH_CONCALLS: use CONCALL FORMAT
═══════════════════════════════════════════════════════════
THE EXACT 8 QUARTERS YOU MUST COVER (latest first):
{quarters_numbered}

RULE — CONCALL vs PRESS RELEASE:
  ★ ALWAYS search for the earnings conference call FIRST for every quarter.
  ★ Use badge "concall-badge" if a concall was held.
  ★ Use "press-release-badge" ONLY if NO concall was held and only a BSE/NSE press release exists.
  ★ Use "ppt-badge" ONLY if only an investor presentation exists and no concall was held.
  ★ Use "missing-badge" if nothing was found for that quarter.
  ★ NEVER substitute a press release for a concall when the company did hold one.

ANALYSIS per quarter (MAX 3–4 bullets per card):
- Revenue, EBITDA/NIM, PAT vs prior guidance (1 line)
- 1–2 key management highlights
- Guidance given for next quarter/year (specific numbers)
- Red flags: guidance cuts, margin pressure, management changes

CAPEX & MAJOR DEVELOPMENTS (MANDATORY — generate BEFORE guidance table):
- List ALL capex, expansions, acquisitions, fundraising with amounts and funding source
- Always present even if minimal

GUIDANCE TRACKING:
- RAISED / CUT / MAINTAINED classification across all 8 quarters
- Use class="guidance-raised" / "guidance-cut" / "guidance-maintained"

OUTPUT for MAINBOARD_WITH_CONCALLS:
<div class="concall-section" data-section-title="Concall Evaluation">
  <div class="concall-section-header">Summary sentence.</div>
  <div class="concall-cards-grid">
    <div class="concall-card concall-card-1">
      <div class="concall-card-header">{quarters[0]}<span class="concall-type-badge concall-badge">Concall</span></div>
      <ul><li><strong>Revenue:</strong> ₹X Cr (+X% YoY)</li><li>Key highlight</li><li>Guidance</li></ul>
      <p><em>Guidance: ...</em></p>
    </div>
    <!-- concall-card-2 through concall-card-8 -->
  </div>
  <div class="capex-section">
    <h3>Capital Expenditure &amp; Major Developments</h3>
    <div class="capex-item"><strong>Project</strong> — <span class="capex-amount">₹X Cr</span><br><span class="capex-funding">Funding: ...</span></div>
  </div>
  <div class="guidance-section">
    <h3>Guidance Tracker</h3>
    <table class="guidance-table">
      <thead><tr><th>Metric</th>{guidance_header_cols}<th>Trend</th></tr></thead>
      <tbody><tr><td><strong>Metric</strong></td><td class="guidance-raised">value</td><td class="guidance-maintained">value</td><td class="guidance-cut">CUT ▼</td></tr></tbody>
    </table>
    <p style="font-size:9pt;color:#555;">Green=Raised | Red=Cut | Yellow=Maintained</p>
  </div>
  <div class="no-concall-alerts"><!-- only if quarters had no concall --></div>
</div>

═══════════════════════════════════════════════════════════
STEP 2B — IF SME_COMPANY or MAINBOARD_NO_CONCALLS: use COMPANY UPDATES FORMAT
═══════════════════════════════════════════════════════════
SME companies typically:
  • Report half-yearly (H1 = Apr–Sep, H2 = Oct–Mar) instead of quarterly
  • May hold occasional concalls — ALWAYS check for these first!
  • Board meeting outcome letters on BSE are the primary disclosure method

HALF-YEARLY vs ANNUAL RESULTS — CRITICAL DISTINCTION:
  ★ H1 results (Apr–Sep) = covers only the first 6 months of the fiscal year
  ★ H2 results (Oct–Mar) = covers only the second 6 months of the fiscal year
  ★ Annual/Full-year results (Apr–Mar) = covers the FULL 12 months — DO NOT use this for H2 card
  ★ If BSE filing title says "Half Yearly Results" or "Six Months Ended September" → H1
  ★ If BSE filing title says "Half Yearly Results" or "Six Months Ended March" → H2
  ★ If BSE filing title says "Annual Results" or "Year Ended March" → this is FULL YEAR, show it
    as a separate "Full Year FY25" card, NOT as H2
  ★ Use H2-specific revenue/PAT from the H2-only filing, not from the annual report

WHAT TO SEARCH FOR per period (in priority order):
1. Concall/earnings call — search "<company> <period> concall", "<company> earnings call <year>"
   → use badge sme-concall-badge if found; extract management commentary
2. Board meeting outcome letter (BSE filing after results) — use badge sme-board-badge
3. Investor presentation / PPT — search "<company> investor presentation <period>", "<company> PPT BSE"
   → use badge sme-ppt-badge if found
4. Half-yearly results filing (standalone H1 or H2 filing, NOT annual) — use badge sme-results-badge
5. Management interview (news/YouTube) — use badge sme-interview-badge
6. Nothing found — use badge sme-missing-badge

PERIODS TO COVER (latest first, adapt to half-yearly if that's what the company reports):
- Show up to 6 most recent reporting periods (H1/H2 or quarterly where available)
- Label cards as "H1 FY26 (Apr–Sep 2025)", "H2 FY25 (Oct 2024–Mar 2025)", etc. for half-yearly
- Or "Q3 FY26 (Oct–Dec 2025)" etc. if the company does file quarterly
- If both a concall AND results filing exist for the same period, show BOTH badges on one card

ANALYSIS per period card (MAX 3–4 bullets):
- Revenue and PAT — use HALF-YEARLY figures (6-month period), not full-year figures
- Key business highlight from concall transcript, board letter, or PPT
- Any guidance or outlook statement
- Red flag if any (auditor note, revenue decline, promoter pledge etc.)

CAPEX & DEVELOPMENTS:
- List any capex, expansion, acquisition noted in any filing, PPT, or concall
- Mark "No significant capex announced" if nothing found

SOURCES USED section (MANDATORY for SME):
- List exactly what sources were found for each period (BSE filing title, article, concall date)

OUTPUT for SME_COMPANY or MAINBOARD_NO_CONCALLS:
<div class="concall-section sme-section" data-section-title="Company Updates">
  <div class="sme-summary-bar">
    <span class="sme-listing-badge">SME Listed</span>
    One sentence: reporting frequency, concall history, primary disclosure method.
  </div>
  <div class="sme-updates-grid">
    <div class="sme-update-card">
      <div class="sme-card-header">
        H1 FY26 (Apr–Sep 2025)
        <span class="sme-badge sme-results-badge">Results Filing</span>
      </div>
      <ul>
        <li><strong>Revenue:</strong> ₹X Cr (+X% YoY)</li>
        <li>Key highlight from board letter or filing</li>
        <li>Any guidance or outlook</li>
      </ul>
    </div>
    <!-- repeat for each period, max 6 cards -->
  </div>
  <div class="sme-capex-section">
    <h3>Capex &amp; Key Developments</h3>
    <div class="sme-capex-item">Description — amount if known</div>
  </div>
  <div class="sme-sources-section">
    <h3>Information Sources</h3>
    <ul>
      <li><strong>H1 FY26:</strong> BSE Board Meeting Outcome dated DD-MM-YYYY</li>
      <li><strong>H2 FY25:</strong> Half-yearly results press release, BSE filing</li>
    </ul>
  </div>
</div>

═══════════════════════════════════════════════════════════
UNIVERSAL RULES (apply to ALL output types)
═══════════════════════════════════════════════════════════
- Return ONLY valid HTML. NO markdown, NO code blocks, NO text outside HTML tags.
- The outermost tag MUST be <div class="concall-section" data-section-title="...">
- Set data-section-title="Concall Evaluation" for MAINBOARD_WITH_CONCALLS
- Set data-section-title="Company Updates" for SME_COMPANY or MAINBOARD_NO_CONCALLS
- Close every opened <div> tag — HTML MUST be balanced.""" + _reference_date_context()

    quarters_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(quarters))
    user = (
        f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange})\n\n"
        f"STEP 1: First determine if this is an SME-listed company or a mainboard company.\n"
        f"Search: '{company_name} {symbol} SME NSE Emerge BSE SME listing'\n\n"
        f"STEP 2: Based on the company type, generate the appropriate HTML:\n"
        f"  • If mainboard with concalls: cover these 8 quarters with the CONCALL FORMAT:\n{quarters_list}\n"
        f"  • If SME or no-concall mainboard: cover available half-yearly/quarterly periods with COMPANY UPDATES FORMAT\n\n"
        "For mainboard companies: first search for a concall each quarter; only fall back to press release/PPT if no concall was held.\n"
        "For SME companies: for EACH period, first search for a concall ('{company} H1/H2 FY2x concall'), then PPT, then board letter, then results filing.\n"
        "CRITICAL for half-yearly SME: H2 results = Oct–Mar half only (NOT full-year annual results). Annual results = show as separate full-year card.\n"
        "Always include capex/developments and sources (for SME).\n"
        "Set data-section-title='Concall Evaluation' (mainboard with concalls) or 'Company Updates' (SME/no-concall).\n"
        "Return the complete structured HTML only."
    )
    return system, user


def concall_structured_prompt(
    company_name: str,
    symbol: str,
    exchange: str,
    transcripts: list[dict] | None = None,
) -> tuple[str, str]:
    """Prompt for structured JSON concall output (schema-aligned for report payload).

    When `transcripts` is provided (list of {date, link, text, segment}), the LLM
    analyses the actual PDF content instead of web-searching for it.
    """
    quarters = _last_8_quarters()
    quarters_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(quarters))
    guidance_headers = ["Metric"] + [q.split(" (")[0] for q in reversed(quarters)]

    has_transcripts = bool(transcripts)
    is_sme = has_transcripts and any(t.get("segment") == "sme" for t in (transcripts or []))

    if has_transcripts:
        # Build transcript block to embed in the prompt
        transcript_block_parts = []
        for i, t in enumerate(transcripts, 1):
            text = (t.get("text") or "").strip()
            if not text:
                text = "[PDF text could not be extracted]"
            transcript_block_parts.append(
                f"--- TRANSCRIPT {i} | Date: {t.get('date', '')} | Link: {t.get('link', '')} ---\n{text}"
            )
        transcript_block = "\n\n".join(transcript_block_parts)
        company_type_hint = "SME_COMPANY" if is_sme else "MAINBOARD_WITH_CONCALLS"
        data_source_note = (
            f"You have been provided with {len(transcripts)} actual concall/earnings transcript(s) "
            f"fetched directly from NSE filings. Company type is {company_type_hint}. "
            "For quarters covered by the provided transcripts, extract data strictly from the transcript text — do not hallucinate. "
            "For all remaining quarters in the 8-quarter window NOT covered by any transcript, use web search to find the actual concall or filing details."
        )
    else:
        transcript_block = ""
        data_source_note = (
            f'Determine if the company is MAINBOARD_WITH_CONCALLS, MAINBOARD_NO_CONCALLS, or SME_COMPANY '
            f'(search: "{company_name} {symbol} SME NSE Emerge BSE SME"). '
            "Use web search to find concall filings for each quarter."
        )

    system = f"""You are an expert equity research analyst for Indian listed companies. {data_source_note} Return ONLY a single valid JSON object (no markdown, no code fences).

INDIAN FY: Q1=Apr–Jun, Q2=Jul–Sep, Q3=Oct–Dec, Q4=Jan–Mar.

FOR MAINBOARD_WITH_CONCALLS use this exact shape:
{{
  "sectionTitle": "Concall Evaluation",
  "type": "mainboard_concall",
  "summary": "One sentence summary.",
  "cards": [
    {{
      "period": "Q2 FY26 (Jul–Sep 2025)",
      "badge": "concall" | "press-release" | "ppt" | "missing",
      "link": "direct URL to the transcript PDF, BSE/NSE filing, or concall recording page — null if unavailable",
      "events": [
        {{ "type": "acquisition" | "fundraise" | "stake_sale" | "capex" | "order_win" | "mgmt_change" | "guidance_change", "headline": "Short headline ≤12 words", "details": ["detail 1", "detail 2"] }}
      ],
      "qaHighlights": [
        {{ "q": "Analyst question (one line)", "a": "Management answer (one-two lines)" }}
      ],
      "bullets": ["Operational highlight 1", "Operational highlight 2"],
      "guidance": "Guidance statement or null"
    }}
  ],
  "capex": [
    {{ "project": "...", "amount": "₹X Cr", "funding": "..." }}
  ],
  "guidanceTable": {{
    "headers": {json.dumps(guidance_headers)},
    "rows": [
      {{ "metric": "Revenue growth (FY)", "cells": [ {{ "value": "15-18%", "trend": "raised" | "cut" | "maintained" | "neutral" }}, ... ] }}
    ]
  }},
  "noConcallAlerts": ["Quarter X had only press release."]
}}

EVENTS — scan BOTH the transcript AND any press releases/BSE announcements for that quarter.
  Populate for each event that actually occurred:
  acquisition   = ANY M&A deal, acquisition, or JV formation — ALWAYS include if mentioned, even partial/pending
  fundraise     = QIP, rights issue, NCD, preferential allotment, loan facility
  stake_sale    = promoter or major shareholder sold/pledged stake
  capex         = major new capex (plant, equipment, expansion) — skip routine maintenance
  order_win     = significant contract or order received
  mgmt_change   = CEO/CFO/MD/promoter-director change
  guidance_change = guidance raised or cut meaningfully vs prior quarter
  For acquisitions: headline = "Acquired <target> for ₹X Cr" (or "Acquisition of <target> announced"),
    details = [funding source, strategic rationale, expected completion/accretion timeline].
  If none of these occurred, set "events": [].

Q&A — STRICT RULE: only include a Q&A entry if an analyst challenged management on ONE of these:
  1. Why a promoter/insider sold or pledged shares
  2. An auditor qualification, going concern, or governance concern
  3. A significant guidance cut (analyst pushed back on the reason)
  4. Acquisition price or deal rationale being questioned
  5. Debt sustainability or covenant breach concern
  Maximum 2 Q&A entries per card. Keep each Q and A to 1–2 sentences.
  If none of these apply, set "qaHighlights": [].

BULLETS — always include financial performance first, then operational highlights. Max 4 bullets total:
  • Revenue growth % YoY (e.g. "Revenue +18% YoY to ₹X Cr")
  • EBITDA margin or growth (e.g. "EBITDA margin 22%, +150bps YoY")
  • PAT growth % (e.g. "PAT +25% YoY to ₹X Cr")
  • 1 key operational highlight (capacity, geography, product, demand outlook)
  Skip any metric where the data is unavailable — do not write "N/A".

Cover these 8 quarters (latest first): {quarters_list}
Badge: "concall" when concall held; "press-release" when only press release; "ppt" when only presentation; "missing" when nothing found.
Trend in guidanceTable cells: "raised", "cut", "maintained", "neutral".

FOR SME_COMPANY or MAINBOARD_NO_CONCALLS use:
{{
  "sectionTitle": "Company Updates",
  "type": "sme_updates",
  "summaryBar": {{ "badge": "SME Listed", "text": "One sentence on reporting frequency and disclosure." }},
  "cards": [
    {{
      "period": "H1 FY26 (Apr–Sep 2025)",
      "badge": "sme-concall" | "sme-board" | "sme-ppt" | "sme-results" | "sme-interview" | "sme-missing",
      "link": "direct URL to BSE filing, concall recording, or transcript PDF — null if unavailable",
      "events": [
        {{ "type": "acquisition" | "fundraise" | "stake_sale" | "capex" | "order_win" | "mgmt_change" | "guidance_change", "headline": "Short headline ≤12 words", "details": ["detail 1"] }}
      ],
      "qaHighlights": [
        {{ "q": "Question (one line)", "a": "Answer (one-two lines)" }}
      ],
      "bullets": ["Operational highlight 1"],
      "guidance": "..." or null
    }}
  ],
  "capex": [ {{ "project": "...", "amount": "...", "funding": "..." }} or {{ "description": "..." }} ],
  "sources": [ {{ "period": "H1 FY26", "source": "NSE filing dated ..." }} ]
}}

Same events, Q&A, and bullets rules apply for SME (include revenue/PAT growth %, then 1 operational highlight). Up to 6 periods for SME (H1/H2 or quarterly). H2 = Oct–Mar half only; full-year = separate card.
Return ONLY the JSON object.""" + _reference_date_context() + _WEB_SEARCH_INSTRUCTION

    if has_transcripts:
        user = (
            f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange}).\n\n"
            f"Analyse the following {len(transcripts)} transcript(s) fetched from NSE and return "
            "the JSON object. Extract: (1) events — acquisitions/M&A MUST be captured if mentioned anywhere in transcript, "
            "plus fundraises, stake sales, major capex, order wins, mgmt changes, guidance changes; "
            "(2) Q&A ONLY for promoter stake/pledge, auditor concerns, guidance cut pushback, acquisition rationale challenged, or debt concerns; "
            "(3) bullets: revenue growth %, EBITDA margin/growth, PAT growth %, then 1 operational highlight. "
            "Mark quarters with no transcript as badge 'missing'.\n\n"
            f"{transcript_block}\n\n"
            "Return the single JSON object. No other text."
        )
    else:
        user = (
            f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange}).\n"
            "1) Determine company type (mainboard with concalls vs SME vs mainboard no concalls).\n"
            "2) Search for concalls/filings per quarter or half-year.\n"
            "3) Return the single JSON object matching the type. No other text."
        )
    return system, user


def sectoral_prompt(company_name: str, sector: str) -> tuple[str, str]:
    system = (
        "You are an equity research analyst. For the given company and sector, identify factors that could "
        "**increase or decrease revenue**, or **increase or decrease margins**, for this specific company. "
        "Focus on: (1) **Macroeconomic factors** (rates, inflation, growth, FX, commodity prices), "
        "(2) **Government policies and regulations** (new laws, schemes, tariffs, PLI, tax changes), "
        "(3) **Industry and competitive dynamics** (capacity, pricing, market share, disruption), "
        "(4) **Technology and demand shifts** relevant to the sector. "
        "**Tailwinds** = factors that could drive revenue growth or margin expansion. "
        "**Headwinds** = factors that could destroy revenue or compress margins. "
        "Use web search to find recent, factual information. For each point, **cite sources with URLs** where possible "
        "using markdown links: [Source name](url). "
        "Return ONLY a single valid JSON object with exactly these keys: "
        '"analysis" (string, 1–3 short paragraphs summarising the sector view for this company), '
        '"headwinds" (array of strings, 2–6 items; each item is one bullet in Markdown: brief factor description with optional [Source](url)), '
        '"tailwinds" (array of strings, 2–6 items; same format as headwinds). '
        "Each headwind/tailwind string must be a single bullet: plain text or markdown with **bold** and [link](url). "
        "No code fences, no text outside the JSON." + _reference_date_context() + _WEB_SEARCH_INSTRUCTION
    )
    user = (
        f"Company: {company_name}. Sector/industry: {sector or 'Not specified'}.\n\n"
        "Return a JSON object with keys: analysis, headwinds, tailwinds. "
        "Each headwind and tailwind must be a concise bullet (one factor per item). "
        "Include source links in markdown format [Source](url) wherever possible to build credibility."
    )
    return system, user


def company_updates_prompt(
    company_name: str,
    symbol: str,
    exchange: str,
    updates_data: dict,
) -> tuple[str, str]:
    """Prompt for companies with NO concalls in the last 8 quarters.

    Analyses PPT links, order wins, and press releases to produce a
    structured 'no_concall_updates' JSON for the frontend.
    """
    ppt_links = updates_data.get("ppt_links") or []
    order_items = updates_data.get("order_items") or []
    press_items = updates_data.get("press_items") or []

    ppt_block = ""
    if ppt_links:
        lines = [f"  - [{p['period']}]({p['link']})" for p in ppt_links]
        ppt_block = "INVESTOR PRESENTATIONS (from Screener):\n" + "\n".join(lines)

    order_block = ""
    if order_items:
        lines = [f"  - [{i['date']}] {i['description']} | link: {i['link']}" for i in order_items]
        order_block = "ORDER WINS / CONTRACTS (from NSE filings):\n" + "\n".join(lines)

    press_block = ""
    if press_items:
        lines = [f"  - [{i['date']}] {i['description']} | link: {i['link']}" for i in press_items]
        press_block = "PRESS RELEASES / COMPANY UPDATES (from NSE filings):\n" + "\n".join(lines)

    raw_data = "\n\n".join(b for b in [ppt_block, order_block, press_block] if b) or "(no structured data — use web search)"

    system = """You are an equity research analyst. The company below has NOT held any concall in the last 8 quarters.
Your job is to compile the best available public information about the company from investor presentations, order wins, and press releases.

OUTPUT FORMAT — return ONLY a single valid JSON object (no markdown fences, no text outside JSON):

{
  "type": "no_concall_updates",
  "sectionTitle": "Company Updates",
  "noConcallMessage": "No concalls held in last 8 quarters",
  "investorPresentation": {
    "period": "most recent PPT period, e.g. Q3 FY26",
    "link": "direct URL to the PPT — use one from INVESTOR PRESENTATIONS above",
    "bullets": [
      "Revenue guidance / growth trajectory mentioned in PPT",
      "Key business highlights from latest PPT",
      "Capacity / expansion plans if any"
    ]
  },
  "orderBook": {
    "bullets": [
      "Bagged ₹450 Cr order from [NTPC](https://ntpc.co.in) — [NSE Filing](LINK)",
      "Received L1 status in ₹220 Cr PGCIL tender — [NSE Filing](LINK)"
    ]
  },
  "pressReleases": {
    "bullets": [
      "Commissioned 50 MW solar plant in Madhya Pradesh — [NSE Filing](LINK)",
      "Board approved ₹200 Cr capex for FY26 — [NSE Filing](LINK)"
    ]
  }
}

RULES:
- investorPresentation: use the MOST RECENT PPT. Read it via web search to extract 3-5 meaningful bullets. If no PPT link available, use web search to find investor day / annual report highlights.
- orderBook: list each significant order/contract as a bullet. Use markdown links: wrap the client name as [ClientName](url) if you know the URL, and append [NSE Filing](filing_link) as the source.
- pressReleases: list key company announcements. Append [NSE Filing](filing_link) as source.
- If a section has no data, set its bullets to [].
- noConcallMessage: always exactly "No concalls held in last 8 quarters"
- Do NOT include any field outside the schema above.""" + _reference_date_context() + _WEB_SEARCH_INSTRUCTION

    user = (
        f"Company: {company_name} | Symbol: {symbol} | Exchange: {exchange}\n\n"
        f"{raw_data}\n\n"
        "Use the above data plus web search to fill the JSON. "
        "For the investor presentation bullets, read the PPT content via web search and extract real numbers (revenue, margins, order book size). "
        "For order wins, include the client name, value, and NSE filing link. "
        "Return ONLY the JSON."
    )
    return system, user


def aggregate_prompt(
    company_overview: str,
    management_research: str,
    financial_risk: str,
    concall_evaluation: str,
    sectoral_analysis: str,
) -> tuple[str, str]:
    system = "You are an equity research analyst. Write a short executive summary (1–2 paragraphs) that ties together the company overview, management, financial risk, concall evaluation, and sectoral view. Highlight key takeaways and risks." + _reference_date_context()
    user = (
        f"Company overview:\n{company_overview}\n\nManagement:\n{management_research}\n\n"
        f"Financial risk:\n{financial_risk}\n\nConcall evaluation:\n{concall_evaluation}\n\n"
        f"Sectoral:\n{sectoral_analysis}\n\nWrite the executive summary."
    )
    return system, user
