"""Shared prompt fragments and LLM invocation helper."""

from __future__ import annotations

import json
import logging
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
