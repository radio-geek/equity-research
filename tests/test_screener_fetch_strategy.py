"""Tests: consolidated URL first, then company page without /consolidated/."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

import src.data.screener_scraper as ss


def _four_table_html() -> str:
    """Minimal HTML that satisfies _find_tables_by_content for all four tables."""
    return """
    <table>
      <tr><th></th><th>Mar 2024</th><th>TTM</th></tr>
      <tr><td>Sales</td><td>100</td><td>110</td></tr>
      <tr><td>Operating Profit</td><td>10</td><td>11</td></tr>
      <tr><td>Net Profit</td><td>8</td><td>9</td></tr>
    </table>
    <table>
      <tr><th></th><th>Mar 2024</th></tr>
      <tr><td>Borrowings</td><td>1</td></tr>
      <tr><td>Equity Capital</td><td>1</td></tr>
      <tr><td>Reserves</td><td>10</td></tr>
    </table>
    <table>
      <tr><th></th><th>Mar 2024</th></tr>
      <tr><td>Cash from Operating Activity</td><td>5</td></tr>
    </table>
    <table>
      <tr><th></th><th>Mar 2024</th></tr>
      <tr><td>ROCE %</td><td>10</td></tr>
    </table>
    """


def test_fetch_consolidated_company_only_when_consolidated_http_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_page = _four_table_html()

    def fake_get(url: str, **_kwargs) -> MagicMock:
        if "/consolidated/" in url:
            raise requests.ConnectionError("network")
        r = MagicMock()
        r.text = full_page
        r.raise_for_status = lambda: None
        return r

    monkeypatch.setattr(ss.requests, "get", fake_get)
    out = ss.fetch_consolidated("RELIANCE")
    assert ss._tables_complete(out)
    assert out["profit_loss"] is not None
    assert out["profit_loss"].loc["Sales", "Mar 2024"] == 100.0


def test_fetch_consolidated_prefers_consolidated_when_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_page = _four_table_html()
    calls: list[str] = []

    def fake_get(url: str, **_kwargs) -> MagicMock:
        calls.append(url)
        r = MagicMock()
        r.text = full_page
        r.raise_for_status = lambda: None
        return r

    monkeypatch.setattr(ss.requests, "get", fake_get)
    out = ss.fetch_consolidated("TCS")
    assert ss._tables_complete(out)
    assert len(calls) == 1
    assert "/consolidated/" in calls[0]
