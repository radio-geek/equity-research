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
        "Role: You are a Senior Equity Research Analyst.\n\n"

        "Objective:\n"
        "Explain to an investor what this company does, how it makes money, and where it sits in its "
        "industry value chain. The reader should understand in 30 seconds the core business and, in a few "
        "minutes, the full value chain of the industry and this company's place in it. Be specific and "
        "data-driven; avoid generic sector fluff.\n\n"

        "Web search (mandatory):\n"
        "You MUST use the web search tool. Do not rely on training knowledge for company-specific facts.\n\n"
        "Search in this order:\n"
        "1. Industry value chain: Search for \"[sector/industry name] value chain India\" or "
        "\"[sector] industry structure upstream downstream\". Identify the real stages (e.g. raw materials → "
        "processing → component manufacturing → OEM → distribution → end customer) for this sector.\n"
        "2. Company business: Search \"[company_name] annual report\", \"[company_name] investor presentation\", "
        "\"[company_name] business model\", \"[symbol] NSE company overview\". Get products, segments, customers, revenue mix.\n"
        "3. Company positioning: Search \"[company_name] supplier to\", \"[company_name] customers\", "
        "\"[company_name] backward integration\" or \"forward integration\" to pinpoint where it sits in the chain.\n"
        "4. Recent context: Search \"[company_name] expansion\", \"[company_name] acquisition\", "
        "\"[company_name] recent developments\" for M&A, capex, new segments.\n\n"
        "Base the entire overview on search results. Cite every fact with an inline Markdown link to the source URL.\n\n"

        "Output format:\n"
        "- Strictly Markdown (no HTML). Use ## for section headings.\n"
        "- Concise paragraphs; **bold** for emphasis. Every fact = inline citation, e.g. ([Source](url)).\n\n"

        "Required structure:\n\n"

        "Opening (1–2 sentences):\n"
        "\"[Company] is a [type of company] that primarily makes money by [core activity].\" "
        "Then one short paragraph: what it does, who its key customers are, and what differentiates it.\n\n"

        "## Industry Value Chain\n"
        "First describe the value chain of the industry in which this company operates. Use the actual "
        "stages for this sector (e.g. for auto components: Raw materials → Tier-2/Tier-3 → Tier-1 → OEM → "
        "Dealers → End customer). Use a simple flow like: Stage A → Stage B → Stage C → End customer.\n\n"
        "Then in a separate short paragraph: **Where [Company] fits:** State clearly which stage(s) the "
        "company operates in (upstream/midstream/downstream), what it buys from (inputs/suppliers) and "
        "what it sells to (OEMs, distributors, end consumers, etc.). This must be explicit and cited.\n\n"

        "## Business Model & Revenue Drivers\n"
        "How the company generates revenue; main revenue streams and customer types. Include a table:\n"
        "Business Segment | Importance | Description\n"
        "(Importance: Primary / Secondary / Emerging.)\n\n"

        "## Key Products / Services\n"
        "5–8 bullet points with actual product or service names from AR, investor presentations, or website. Cite sources.\n\n"

        "## Sector Overview & Industry Positioning\n"
        "Brief sector context (size, growth if available) and how this company is positioned vs peers "
        "(e.g. market share, niche, geography). Keep it company-specific, not generic.\n\n"

        "## Recent Developments\n"
        "Expansion, M&A, diversification, major orders, capacity additions, or regulatory changes. "
        "Format: YYYY – Event. Cite each.\n\n"

        "## Key Business Milestones\n"
        "Timeline: IPO/listing, major capacity additions, strategic acquisitions, key contracts. YYYY – Event.\n\n"

        "Critical rule: Every fact, number, or claim MUST have an inline citation with a link. "
        "If you cannot find a source for a claim, say \"(source not found)\" or omit it.\n"
    ) + _reference_date_context()

    user = (
        f"Company: {company_name} (symbol: {symbol})\n\n"
        f"Meta Data: {_serialize(meta)}\n\n"
        f"Quote Data: {_serialize(quote)}\n\n"
        "Using web search: (1) Find the industry value chain for this company's sector and describe it. "
        "(2) Find what the company does, its segments, products, and customers. "
        "(3) State clearly where the company fits in that value chain (which stages, upstream/downstream, who it sells to and buys from). "
        "Write the overview in the required structure. Explain as if briefing an investor who has never heard of the company."
    )

    return system, user


def company_overview_structured_prompt(
    company_name: str, symbol: str, meta: dict, quote: dict
) -> tuple[str, str]:
    """Prompt for structured JSON company overview (opening, value chain, table, products, timeline)."""
    system = (
        "Role: You are a Senior Equity Research Analyst.\n\n"
        "Objective: Produce a structured company overview for an investor. You MUST use the web search tool; do not rely on training knowledge for company-specific facts.\n\n"
        "Search in this order:\n"
        "1. Industry value chain: \"[sector/industry] value chain India\", \"[sector] industry structure upstream downstream\". Get real stages (e.g. raw materials → processing → OEM → distribution → end customer).\n"
        "2. Company business: \"[company_name] annual report\", \"[company_name] investor presentation\", \"[company_name] business model\", \"[symbol] NSE company overview\". Get products, segments, revenue mix.\n"
        "3. Company positioning: \"[company_name] supplier to\", \"[company_name] customers\", \"[company_name] backward integration\" or \"forward integration\".\n"
        "4. Recent context: \"[company_name] expansion\", \"[company_name] acquisition\", \"[company_name] recent developments\".\n\n"
        "Return ONLY a single valid JSON object (no markdown, no code fences). Use this exact shape:\n\n"
        "{\n"
        '  "opening": "3–4 lines of plain text: what the company actually does — core business, who it serves, how it makes money. Concise and investor-ready. No markdown."\n'
        ',  "value_chain": { "stages": ["Stage A", "Stage B", "Stage C", "End customer"], "company_stage_indices": [0, 1], "company_position_description": "2–3 lines: what the company does in these nodes. Be descriptive.", "company_position": "Optional short label (e.g. Tier-1 supplier, or Integrated player)." }\n'
        ',  "business_model_table": { "rows": [ { "segment": "Segment name", "importance": "Primary" | "Secondary" | "Emerging", "description": "Brief description" } ] }\n'
        ',  "key_products": ["Product or service 1", "Product or service 2", "…"]\n'
        ',  "recent_developments": [ { "year": "YYYY", "event": "Short description" } ]\n'
        "}\n\n"
        "Rules:\n"
        "- opening: 3–4 lines only; what the company does, who it serves, how it makes money.\n"
        "- value_chain.stages: ordered list of industry stages (typically 4–8). company_stage_indices: array of 0-based indices of stages where this company operates — e.g. [1] for one stage, [0, 1, 2] for three, or [0, 1, 2, 3, 4] for all if the company spans the entire value chain. company_position_description: 2–3 lines describing what the company does in these nodes (inputs, outputs, role). company_position: optional one-line label.\n"
        "- business_model_table.rows: at least one row; importance must be Primary, Secondary, or Emerging.\n"
        "- key_products: 5–8 actual product or service names from AR/investor materials.\n"
        "- recent_developments: combine recent developments and key milestones; chronological; each entry has year and event. If multiple milestones in the same year, use separate { year, event } entries for each (they will be grouped by year in the UI).\n"
        "Base every fact on search results. If you cannot find a source, omit the claim or say so briefly.\n"
    ) + _reference_date_context()

    user = (
        f"Company: {company_name} (symbol: {symbol})\n\n"
        f"Meta Data: {_serialize(meta)}\n\n"
        f"Quote Data: {_serialize(quote)}\n\n"
        "Using web search: (1) Industry value chain for this sector. (2) What the company does, segments, products, customers. "
        "(3) Where the company fits in the value chain. (4) Recent developments and milestones. "
        "Return only the JSON object with opening, value_chain, business_model_table, key_products, recent_developments."
    )
    return system, user


def management_prompt(company_name: str, symbol: str, meta: dict, shareholding: list) -> tuple[str, str]:
    system = (
        "Role: You are an equity research analyst preparing the Management & Governance section of a detailed stock research report.\n\n"

        "Objective:\n"
        "Use the provided materials (ARs, concalls, presentations, announcements) and web search to produce structured, objective, data-driven output that helps investors assess management quality and governance.\n\n"

        "Web search (mandatory):\n"
        "You MUST use the web search tool. Do not rely on training knowledge for company-specific facts.\n"
        "Search for: promoter background and history; board composition and director credentials; "
        "related party transactions (RPT) from annual reports or BSE/NSE filings; shareholding pledges. "
        "For governance_news only: search strictly for governance-related developments (see below). "
        "Base the output on search results.\n\n"

        "Output format: Return ONLY a single JSON object (no markdown, no code fences, no preamble). "
        "The JSON must have exactly these keys:\n\n"

        "1. \"people\" (array of objects): One entry per promoter, key executive, or board member. "
        "Each object: \"name\" (string), \"designation\" (string, e.g. Promoter, MD, Independent Director), "
        "\"description\" (string, 1–3 sentences: background, expertise, tenure, other roles, reputation). "
        "Include promoters and board members; keep list focused (typically 5–12 people).\n\n"

        "2. \"governance_news\" (array of objects): STRICTLY governance-only news from the last 1 year only (from today, back 12 months). "
        "Include ONLY items that are clearly about governance: board composition changes, independent director appointments/resignations, "
        "audit committee or other board committee changes, SEBI/regulatory actions on governance, governance awards or ratings, "
        "related-party or disclosure violations, auditor changes, shareholder voting on governance, ESG governance disclosures. "
        "EXCLUDE: general business news, earnings, product launches, capacity, orders, sector trends, stock price, or any non-governance item. "
        "Each object: \"text\" (string, short headline or 1-sentence summary; include date or recency if possible), "
        "\"sentiment\" (string, exactly one of: \"positive\", \"negative\", \"neutral\"). "
        "Use positive for e.g. board diversity, governance awards, clean disclosures; negative for regulatory action, violations; neutral for routine appointments. "
        "Include up to 5–8 items; if none in the last 12 months, use empty array.\n\n"

        "3. \"rpt_and_gaps\" (string): Short Markdown paragraph(s) covering: (a) Related party transactions summary (material RPTs, arm's length, any concerns); "
        "(b) Gaps & assumptions if you had to infer anything or lacked data. If nothing to add, use empty string.\n\n"

        "Example shape:\n"
        '{"people": [{"name": "...", "designation": "...", "description": "..."}], '
        '"governance_news": [{"text": "...", "sentiment": "positive"}], "rpt_and_gaps": "..."}\n\n'
    ) + _reference_date_context() + _WEB_SEARCH_INSTRUCTION

    user = (
        f"Company: {company_name} (symbol: {symbol}).\n\n"
        f"Meta (company/financial context): {_serialize(meta)}\n\n"
        f"Shareholding pattern (quarterly): {_serialize(shareholding)}\n\n"
        "Using the above and mandatory web search: return the single JSON object with people, governance_news, and rpt_and_gaps. "
        "Be objective and data-driven."
    )
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


def _last_5_fy() -> list[str]:
    """Return the last 5 Indian financial years (most recent first), e.g. ['FY25', 'FY24', 'FY23', 'FY22', 'FY21'].
    Indian FY runs 1 Apr – 31 Mar; FY25 = year ending March 2025.
    """
    today = date.today()
    m, y = today.month, today.year
    end_year = y if m <= 3 else y + 1  # FY end year
    return [f"FY{str(end_year - i)[2:]}" for i in range(5)]


def auditor_flags_prompt(company_name: str, symbol: str, exchange: str) -> tuple[str, str]:
    fy_list = ", ".join(_last_5_fy())
    system = """You are an expert equity research analyst and forensic accountant specializing in audit quality for Indian listed companies.

**CRITICAL: You MUST use web search to find real, current data.** Do not rely on internal knowledge or generalisations. Search BSE/NSE filings, annual reports, company websites, Screener.in, Trendlyne, MoneyControl, and financial news for this specific company. If you cannot find recent information via search, say so explicitly.

Your task: Identify ALL auditor qualifications, emphasis of matter, going concern doubts, CARO/secretarial audit observations, and auditor changes for the company across the last 5 annual reports.

**Search strategy (use web search for each):**
1. Search: "{company} {symbol} annual report auditor qualification", "{company} auditor report emphasis of matter"
2. Search: "{company} CARO qualification", "{company} secretarial audit observations"
3. Search: "{company} going concern", "{company} audit qualified opinion"
4. Search: "{company} auditor change", "{company} auditor resignation"
5. Look at BSE/NSE disclosure filings, latest annual report PDFs or summaries, and investor forums

**Cover only these 5 financial years (most recent first):** """ + fy_list + """

**For each finding:**
- **date** (string): For ordering. Use YYYY-MM when known (e.g. audit report date or FY year-end March → 2025-03). If only year is known use YYYY (e.g. 2024). Indian FY year-end is March (e.g. FY25 → 2025-03).
- **fy** (string): Display label, e.g. FY25.
- **type** (string): Exactly one of: Qualified Opinion, Emphasis of Matter, Going Concern, CARO, Secretarial Audit, Auditor Change, Other.
- **issue** (string): One short line; be concise.
- **is_red_flag** (boolean): true for qualifications, going concern, auditor resignation, filing delays, restatements, or other serious concerns; false for routine emphasis of matter or clean items.
- **status** (string, optional): Resolved, Recurring, or Pending.
- **management_response** (string, optional): One line if available.

**OUTPUT FORMAT: Return a single JSON object only.** No markdown, no code fences, no text outside the JSON.

Schema:
{
  "summary": "One line, e.g. '3 qualifications (FY22–FY25); 1 recurring, 1 pending' or 'Clean opinions — no qualifications in last 5 years.'",
  "events": [
    {
      "date": "2025-03",
      "fy": "FY25",
      "type": "Qualified Opinion",
      "issue": "Short description of the qualification.",
      "is_red_flag": true,
      "status": "Pending",
      "management_response": "Optional one line."
    }
  ]
}

- List events in **descending** order by date (most recent first).
- If no qualifications are found after searching, return events: [] and summary explaining that you searched and found none.
- Keep issue and management_response to one short line each.""" + _reference_date_context()

    user = (
        f"Company: **{company_name}** (Symbol: {symbol}, Exchange: {exchange}).\n\n"
        "Use web search to find and document all auditor qualifications, emphasis of matter, going concern opinions, "
        "CARO qualifications, secretarial audit observations, and auditor changes for the last 5 years. "
        f"Cover only: {fy_list}. Return a single JSON object with summary and events (descending by date). Do not invent; cite search results."
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

BULLETS — always financial first, then ALL operational highlights found in the concall. Target 6–9 bullets; include fewer only when data is genuinely absent.

  FINANCIAL (always first — include all three if available):
  • Revenue: growth % YoY AND absolute number (e.g. "Revenue +18% YoY to ₹450 Cr")
  • EBITDA: absolute ₹ AND margin % AND YoY change (e.g. "EBITDA ₹90 Cr, margin 20% (+150bps YoY)")
  • PAT: growth % YoY AND absolute ₹ (e.g. "PAT +25% YoY to ₹55 Cr")

  OPERATIONAL — scan the entire transcript and include EVERY point below that management mentioned:
  • Order book: outstanding order book size, L1 wins, revenue visibility (e.g. "Order book ₹1,200 Cr, ~18-month visibility")
  • Margin guidance: management's commentary on future margin direction and the reason (expansion from operating leverage, RM easing, etc. OR compression from pricing pressure)
  • Raw materials / input costs: MANDATORY if management mentions ANY price change for ANY input (RM, fuel, freight, power, chemicals, metals, etc.) — always include the exact number they gave (e.g. "Steel prices up 12% YoY, ~80bps EBITDA headwind", "Crude oil down $15/bbl, margin tailwind of ~150bps", "Cotton prices declined 8%, gross margin improved 200bps"). If multiple inputs are mentioned, include all of them. If management mentions only direction (up/down) with no number, still include it.
  • Receivables / working capital: debtor days change, collection outlook, any stress (e.g. "Debtor days improved from 95 to 72")
  • Government / policy tailwinds: PLI benefits, budget allocations, tender wins, policy changes explicitly mentioned by management
  • Headwinds: demand softness, pricing pressure, competition, regulatory challenges, project delays raised by management
  • Capex / expansion update: include ONLY if not already shown as an event — e.g. plant progress, capacity utilisation milestone
  • Corporate action: stock split, bonus issue, buyback, special dividend — only if not in events
  • Competitive edge / differentiation: if management claims superiority over peers — unique technology, proprietary process, exclusive certifications, switching costs, pricing power, customer stickiness, faster delivery, better quality metrics — quote the specific claim (e.g. "Only Indian co. with aerospace-grade titanium forging capacity", "95% client retention vs industry avg 70%", "3x faster turnaround than peers")
  • Any other forward-looking statement: new geographies, products, partnerships, major customer additions

  Skip a bullet ONLY if the topic was genuinely not discussed — NEVER write "N/A" or "not mentioned".

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

Same events, Q&A, and bullets rules apply for SME — use the same expanded bullets (financial first, then all operational highlights: order book, margin guidance, RM costs, receivables, govt tailwinds, headwinds, capex, corporate actions). Up to 6 periods for SME (H1/H2 or quarterly). H2 = Oct–Mar half only; full-year = separate card.
Return ONLY the JSON object.""" + _reference_date_context() + _WEB_SEARCH_INSTRUCTION

    if has_transcripts:
        user = (
            f"Company: {company_name} (Symbol: {symbol}, Exchange: {exchange}).\n\n"
            f"Analyse the following {len(transcripts)} transcript(s) fetched from NSE and return "
            "the JSON object. Extract:\n"
            "(1) EVENTS — acquisitions/M&A MUST be captured if mentioned anywhere; plus fundraises, stake sales, major capex, order wins, mgmt changes, guidance changes.\n"
            "(2) Q&A ONLY for promoter stake/pledge, auditor concerns, guidance cut pushback, acquisition rationale challenged, or debt concerns.\n"
            "(3) BULLETS — financial first (Revenue %, EBITDA ₹+margin, PAT %), then scan the ENTIRE transcript for: "
            "order book / L1 pipeline, margin guidance and direction, "
            "raw material / input cost changes (MANDATORY: if management mentions any price change for any input with a % or ₹ figure, include it verbatim with the exact number), "
            "receivables / debtor days / working capital, government policy tailwinds, business headwinds, "
            "capex progress, corporate actions (split/bonus/buyback), new geographies/products/customers. "
            "Include 6–9 bullets; skip a topic only if genuinely not discussed.\n"
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
