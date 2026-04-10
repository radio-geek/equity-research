"""Table-driven tests for Screener cell number parsing."""
from __future__ import annotations

import pytest

from src.data.screener_scraper import _parse_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("  ", None),
        ("-", None),
        ("—", None),
        ("NA", None),
        ("N/A", None),
        ("1,024,548", 1024548.0),
        ("17%", 17.0),
        ("(1,234)", -1234.0),
        ("(12.5)", -12.5),
        ("1,234 Cr", 1234.0),
        ("500 cr.", 500.0),
        ("−100", -100.0),
        ("-50", -50.0),
    ],
)
def test_parse_number(raw: str, expected: float | None) -> None:
    assert _parse_number(raw) == expected
