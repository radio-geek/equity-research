"""Tests for format_five_year_trend_as_text."""

import pytest

from src.report.financial_evaluation import format_five_year_trend_as_text


@pytest.mark.parametrize(
    "name, table, want_substr, expect_empty",
    [
        (
            "empty headers",
            {"headers": [], "rows": [{"metric": "Revenue", "unit": "₹ Cr", "cells": [1]}]},
            "",
            True,
        ),
        (
            "empty rows",
            {"headers": ["FY24"], "rows": []},
            "",
            True,
        ),
        (
            "normal table",
            {
                "headers": ["FY23", "FY24"],
                "rows": [
                    {"metric": "Revenue", "unit": "₹ Cr", "cells": [100, 110]},
                ],
            },
            "Revenue (₹ Cr)",
            False,
        ),
        (
            "pads short cell row",
            {
                "headers": ["FY23", "FY24", "TTM"],
                "rows": [
                    {"metric": "PAT", "unit": "₹ Cr", "cells": [10, 12]},
                ],
            },
            "—",
            False,
        ),
    ],
)
def test_format_five_year_trend_as_text(
    name: str,
    table: dict,
    want_substr: str,
    expect_empty: bool,
) -> None:
    got = format_five_year_trend_as_text(table)
    if expect_empty:
        assert got == "", name
    else:
        assert want_substr in got, name

