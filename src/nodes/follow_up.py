"""Follow-up Q&A node: answer user questions on the research; detect 'I am Done'."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from src.state import ResearchState

from .prompts import invoke_llm

DONE_PHRASE = "i am done"


def _last_user_content(state: ResearchState) -> str:
    messages = state.get("messages") or []
    for m in reversed(messages):
        if isinstance(m, dict) and (m.get("role") or "").lower() == "user":
            return (m.get("content") or "").strip().lower()
    return ""


def follow_up(state: ResearchState) -> dict[str, Any]:
    """Wait for user input via interrupt; then answer or ack 'I am Done'."""
    messages = list(state.get("messages") or [])
    user_input = interrupt(
        "Ask a question about the research, or type 'I am Done' to generate the PDF report."
    )
    if not isinstance(user_input, str):
        user_input = ""
    messages.append({"role": "user", "content": user_input})
    last_user = user_input.strip().lower()

    if last_user == DONE_PHRASE:
        messages.append({"role": "assistant", "content": "Generating your PDF report..."})
        return {"messages": messages}
    else:
        system = (
            "You are an equity research analyst. Answer the user's question based only on the "
            "following equity research. Be concise and factual."
        )
        research = (
            f"Company: {state.get('company_name')} ({state.get('symbol')})\n\n"
            f"Executive summary:\n{state.get('executive_summary') or 'N/A'}\n\n"
            f"Company overview:\n{state.get('company_overview') or 'N/A'}\n\n"
            f"Management:\n{state.get('management_research') or 'N/A'}\n\n"
            f"Financial risk:\n{state.get('financial_risk') or 'N/A'}\n\n"
            f"Concall:\n{state.get('concall_evaluation') or 'N/A'}\n\n"
            f"Sectoral:\n{state.get('sectoral_analysis') or 'N/A'}"
        )
        user_content = f"{research}\n\nUser question: {last_user or '(no question)'}"
        reply = invoke_llm(system, user_content)
        messages.append({"role": "assistant", "content": reply})
        return {"messages": messages}


def should_generate_report(state: ResearchState) -> bool:
    """Return True if the last user message was 'I am Done' (used by graph conditional edge)."""
    return _last_user_content(state) == DONE_PHRASE
