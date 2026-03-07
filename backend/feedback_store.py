"""Store feedback (thumbs up/down + optional comment) in cache_data/feedback.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_FILE = _REPO_ROOT / "cache_data" / "feedback.json"


def append_feedback(report_id: str, rating: str, comment: str | None = None) -> None:
    """Append one feedback entry. rating is 'up' or 'down'."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "report_id": report_id,
        "rating": rating,
        "comment": comment or "",
    }
    entries: list[dict[str, Any]] = []
    if FEEDBACK_FILE.is_file():
        try:
            entries = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append(entry)
    FEEDBACK_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
