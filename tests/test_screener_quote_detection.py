"""Test Screener scraper: quote detection and table detection (standard vs bank structure)."""
from __future__ import annotations

from bs4 import BeautifulSoup

import pandas as pd

from src.data.screener_scraper import _find_tables_by_content, _page_has_quote_data, _tables_complete

# Quote block is first 3500 chars; these snippets simulate top-of-page content.


def test_consolidated_empty_borana_style() -> None:
    """Consolidated page with Current Price and Market Cap labels but values empty/NA."""
    html = """
    <div>Market Cap</div>
    <div>₹ <span class="number"></span></div>
    <div>Current Price</div>
    <div>₹ <span class="number"></span> / <span class="number"></span></div>
    <div>High / Low</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _page_has_quote_data(soup) is False


def test_consolidated_has_valid_price() -> None:
    """Consolidated with valid current price in quote block."""
    html = """
    <div>Current Price</div>
    <div>₹ 1,424</div>
    <div>Market Cap</div>
    <div>₹ 19,26,475 Cr.</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _page_has_quote_data(soup) is True


def test_consolidated_na_price_not_treated_as_valid() -> None:
    """Consolidated with Current Price then NA."""
    html = """
    <div>Current Price</div>
    <div>₹ NA</div>
    <div>Market Cap</div>
    <div>₹ N/A</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _page_has_quote_data(soup) is False


def test_consolidated_news_rupee_ignored() -> None:
    """Body text with ₹0.07 (e.g. news) must not make consolidated appear valid."""
    html = """
    <div>Market Cap</div>
    <div>₹ <span></span> Cr.</div>
    <div>Current Price</div>
    <div>₹ </div>
    <p>Later: minor ₹0.07 Cr reallocation.</p>
    """ + "x" * 4000  # push news beyond quote block
    soup = BeautifulSoup(html, "html.parser")
    # Quote block has no numeric price/cap; later ₹0.07 is outside block
    assert _page_has_quote_data(soup) is False


def test_company_page_has_valid_market_cap() -> None:
    """Company page with valid market cap."""
    html = """
    <div>Current Price</div>
    <div>₹ 399</div>
    <div>Market Cap</div>
    <div>₹ 1,045 Cr.</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _page_has_quote_data(soup) is True


def test_tiny_price_ignored() -> None:
    """Price 0.07 in quote block (noise) should not count as valid."""
    html = """
    <div>Current Price</div>
    <div>₹ 0.07</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _page_has_quote_data(soup) is False


# --- Table detection: standard vs bank P&L / Balance Sheet ---


def test_find_tables_standard_pl_detected() -> None:
    """Standard company P&L (Sales, Operating Profit, Net Profit, TTM) is detected."""
    html = """
    <table>
      <tr><th></th><th>Mar 2023</th><th>Mar 2024</th><th>TTM</th></tr>
      <tr><td>Sales</td><td>1000</td><td>1100</td><td>1200</td></tr>
      <tr><td>Operating Profit</td><td>100</td><td>120</td><td>130</td></tr>
      <tr><td>Net Profit</td><td>80</td><td>95</td><td>100</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    located = _find_tables_by_content(soup)
    assert "profit_loss" in located


def test_find_tables_standard_pl_detected_without_ttm_column() -> None:
    """P&L is detected when TTM column is absent (e.g. before TTM is published on Screener)."""
    html = """
    <table>
      <tr><th></th><th>Mar 2023</th><th>Jun 2023</th><th>Mar 2024</th></tr>
      <tr><td>Sales +</td><td>1000</td><td>1050</td><td>1100</td></tr>
      <tr><td>Operating Profit</td><td>100</td><td>110</td><td>120</td></tr>
      <tr><td>Net Profit +</td><td>80</td><td>88</td><td>95</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    located = _find_tables_by_content(soup)
    assert "profit_loss" in located


def test_find_tables_bank_pl_detected() -> None:
    """Bank P&L (Revenue +, Financing Profit, Profit before tax, Net Profit +, TTM) is detected."""
    html = """
    <table>
      <tr><th></th><th>Mar 2024</th><th>Mar 2025</th><th>TTM</th></tr>
      <tr><td>Revenue +</td><td>170754</td><td>283649</td><td>348212</td></tr>
      <tr><td>Interest</td><td>77780</td><td>154139</td><td>187257</td></tr>
      <tr><td>Financing Profit</td><td>29932</td><td>-44685</td><td>-50556</td></tr>
      <tr><td>Profit before tax</td><td>61498</td><td>76569</td><td>100043</td></tr>
      <tr><td>Net Profit +</td><td>46149</td><td>65446</td><td>77430</td></tr>
      <tr><td>EPS in Rs</td><td>41.22</td><td>42.16</td><td>48.54</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    located = _find_tables_by_content(soup)
    assert "profit_loss" in located


def test_find_tables_bank_pl_detected_without_ttm_column() -> None:
    """Bank-style P&L without a TTM column is still detected."""
    html = """
    <table>
      <tr><th></th><th>Mar 2024</th><th>Mar 2025</th></tr>
      <tr><td>Revenue +</td><td>170754</td><td>283649</td></tr>
      <tr><td>Financing Profit</td><td>29932</td><td>-44685</td></tr>
      <tr><td>Profit before tax</td><td>61498</td><td>76569</td></tr>
      <tr><td>Net Profit +</td><td>46149</td><td>65446</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    located = _find_tables_by_content(soup)
    assert "profit_loss" in located


def test_find_tables_bank_balance_sheet_detected() -> None:
    """Balance sheet with 'Borrowing' (singular) as used by banks is detected."""
    html = """
    <table>
      <tr><th></th><th>Mar 2024</th><th>Mar 2025</th></tr>
      <tr><td>Equity Capital</td><td>558</td><td>760</td></tr>
      <tr><td>Reserves</td><td>288880</td><td>455636</td></tr>
      <tr><td>Deposits</td><td>1882663</td><td>2376887</td></tr>
      <tr><td>Borrowing</td><td>256549</td><td>730615</td></tr>
      <tr><td>Total Liabilities</td><td>2530432</td><td>4030194</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    located = _find_tables_by_content(soup)
    assert "balance_sheet" in located


def test_tables_complete_all_four() -> None:
    """_tables_complete requires every table key with at least one period column."""
    one_col = pd.DataFrame({"Mar 2025": [1.0]}, index=["Sales"])
    full = {
        "profit_loss": one_col,
        "balance_sheet": one_col,
        "cash_flow": one_col,
        "ratios": one_col,
    }
    assert _tables_complete(full) is True
    assert _tables_complete({**full, "profit_loss": None}) is False
    assert _tables_complete({**full, "ratios": pd.DataFrame()}) is False
