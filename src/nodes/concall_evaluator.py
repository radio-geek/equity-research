"""Concall evaluator node: stub when no transcript source is available."""

from __future__ import annotations

from typing import Any

from src.data.concall import get_concall_stub_message
from src.state import ResearchState


def concall_evaluator(state: ResearchState) -> dict[str, Any]:
    """Return stub message; real implementation would use concall transcripts."""
    return {"concall_evaluation": get_concall_stub_message()}
