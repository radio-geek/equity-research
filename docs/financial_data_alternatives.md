# Alternative Approaches for Financial Data (Indian Stocks)

The project currently uses **yfinance** (directly and via **nifpy**) for:

- **Ratios**: ROE, Net Margin %, Debt/Equity, Debt/Assets (nifpy → income + balance sheet)
- **Quarterly financials**: revenue, EBITDA, PAT, CFO, D/E, QoQ % (yfinance)
- **Yearly financials + TTM**: same metrics, YoY %, TTM row (yfinance)
- **TTM statements**: income + balance sheet as text for LLM (yfinance)

When yfinance is unreliable (missing data, wrong tickers, rate limits), consider these alternatives.

---

## SME / small cap caveat (yfinance)

**Observed behaviour**: For **SME and many small cap** NSE names, yfinance often returns **only partial data**:

- **Quarterly** statements may be present (e.g. last 8 quarters).
- **Ratios** (nifpy), **yearly** financials, and **TTM** are frequently **missing or empty**.

Example: **PELATRO** (SME) — quarterlies ✓, ratios/yearly/TTM ✗; **ECOSMOBLTY** — full data ✓. So the “wonky” behaviour is especially common for SME/small cap; for those names, consider a fallback source (e.g. Bharat-sm-data / MoneyControl) for ratios and yearly/TTM.

---

## 1. Bharat-sm-data (MoneyControl / TickerTape)

- **Install**: `pip install Bharat-sm-data`
- **Data**: Income, balance sheet, cash flow from MoneyControl and TickerTape (quarterly/annual, mini or complete).
- **Pros**: Indian-focused; consolidated/standalone; multi-year; ratios API.
- **Cons**: Uses MoneyControl ticker/URL (need to resolve NSE symbol → MC ticker via `get_ticker(search_text)`); scraping-based so may break if site layout changes; SME coverage may vary.
- **Fit**: Good replacement for **yearly/quarterly statements and ratios** if we add a symbol → MC ticker mapping (e.g. company name or NSE symbol search).

**Relevant APIs (MoneyControl):**

- `get_ticker(search_text)` → get MoneyControl ticker/URL
- `get_income_mini_statement(ticker, statement_type, statement_frequency)` 
- `get_balance_sheet_mini_statement(ticker)`, `get_cash_flow_mini_statement(ticker)`
- `get_complete_profit_loss(company_mc_url, ...)`, `get_complete_balance_sheet(...)`, `get_complete_quarterly_results(...)`, `get_complete_ratios_data(...)`

---

## 2. Direct yfinance (current) + hardening

- Keep yfinance but add retries, timeouts, and validation.
- **Ticker format**: NSE → `SYMBOL.NS` (e.g. `RELIANCE.NS`). BSE → `SYMBOL.BO`.
- **SME / small cap**: Yahoo often has incomplete coverage: quarterlies may work while ratios, yearly, and TTM are missing (see SME caveat above). Test with `scripts/test_financial_data.py` for your list.
- **Pros**: No new dependencies; already integrated.
- **Cons**: Same data source; can remain “wonky” for SME and many small cap names.

---

## 3. NSEDownload

- **Focus**: Historical **price** and returns (OHLC, adjusted), not financial statements.
- **Not a drop-in** for income/balance/cash flow or ratios. Can complement for price/returns.

---

## 4. nse (NseIndiaApi) – already used

- Used in this repo for **equity meta, quote, shareholding** (see `src/data/nse_client.py`).
- Does **not** provide income statement, balance sheet, or cash flow. Keep for metadata only.

---

## 5. Paid / official data

- **NSE/BSE**: Official fundamental feeds (paid, licensed).
- **Bloomberg/Refinitiv**: Enterprise; overkill for a free-tier project.
- **Finscreener / Screener.in / Tijori Finance**: Some have APIs or scrapers; terms and stability vary.

---

## Recommendation

- **Short term**: Use the **test script** (`scripts/test_financial_data.py`) to see which symbols (large cap vs small cap vs SME) work with current yfinance/nifpy; fix ticker mapping and add retries/timeouts where needed.
- **Medium term**: If coverage or stability remains poor, add a **Bharat-sm-data (MoneyControl)** path: resolve NSE symbol → MoneyControl ticker, then fetch mini/complete statements and ratios behind the same interfaces used by the research nodes (e.g. same dict shape for ratios, quarterly, yearly).

---

## Test script

Run with default list (large cap + small cap examples) or your own list:

```bash
# Default list (built-in large cap + small cap symbols)
python scripts/test_financial_data.py

# Custom symbols (comma-separated)
python scripts/test_financial_data.py --symbols RELIANCE,TCS,YOUR_SME_SYMBOL

# From file (one symbol per line)
python scripts/test_financial_data.py --list path/to/symbols.txt
```

Output: per-symbol pass/fail for ratios, quarterly, yearly, TTM, plus a short summary (e.g. counts of ratios/quarters/years and any errors).
