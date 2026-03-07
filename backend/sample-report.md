# Equity Research Report — Output JSON Schema

This document defines the **single JSON structure** that your LangGraph pipeline should produce as the final report payload. The frontend (experiments app or production report UI) and any PDF/HTML generator can consume this contract.

- **Canonical sample:** `sample-report-output.json` in this folder.
- **Key naming:** This schema uses `snake_case` for consistency with Python/LangGraph state. If your frontend expects `camelCase` (e.g. `companyName`, `yearlyMetrics`), add a thin mapping layer when sending the payload to the client.

---

## Top-level structure

```json
{
  "meta": { ... },
  "company": { ... },
  "executive_summary": "...",
  "company_overview": "...",
  "management_research": "...",
  "financial_risk": "...",
  "auditor_flags": "...",
  "concall": { ... },
  "sectoral": { ... },
  "financials": { ... },
  "generated_at": "..."
}
```

All fields are optional at top level; omit any key when data is unavailable.

---

## 1. `meta`

Metadata and identifiers (from **resolve_company** / user input).

| Field       | Type   | Description                          |
|------------|--------|--------------------------------------|
| `symbol`   | string | Stock symbol (e.g. `"RELIANCE"`)      |
| `exchange` | string | `"NSE"` or `"BSE"`                   |
| `company_name` | string | Full company name                 |
| `sector`   | string | Sector (e.g. `"Technology"`)          |
| `industry` | string | Optional industry sub-classification  |

**Example:**
```json
"meta": {
  "symbol": "TECHCORP",
  "exchange": "NSE",
  "company_name": "TechCorp Industries Ltd",
  "sector": "Technology",
  "industry": "Software"
}
```

---

## 2. `company`

Optional raw payloads from resolve_company (for debugging or downstream use). Can be omitted in the report JSON if you only need display fields.

| Field              | Type           | Description                    |
|--------------------|----------------|--------------------------------|
| `meta`             | object         | Raw meta from NSE/fundamentals |
| `quote`            | object         | Quote / trade info             |
| `shareholding`     | array of dict  | Shareholding pattern           |

---

## 3. `executive_summary`

**Type:** string (plain text or markdown)

One or two paragraphs tying together overview, management, financial risk, concall, and sectoral view. From **aggregate** node.

---

## 4. `company_overview`

**Type:** string (plain text or markdown)

Business description, exchange, sector, products/services, recent context. From **company_overview** node.

---

## 5. `management_research`

**Type:** string (plain text or markdown)

Management quality, promoter/shareholding, governance, related-party concerns. From **management_prompt** node.

---

## 6. `financial_risk`

**Type:** string (plain text or markdown)

Summary of ROE, ROCE, debt/equity, interest coverage, liquidity, strengths and risks. From **financial_risk** node.

---

## 7. `auditor_flags`

**Type:** string (plain text **or** HTML)

Auditor qualifications, emphasis of matter, going concern, CARO/secretarial observations, auditor changes. From **auditor_flags_prompt** node. If your node returns HTML (as in the prompt), you can pass it through; otherwise use plain text.

---

## 8. `concall`

**Type:** object (structured) **or** `null`

Structured concall/company updates. If your pipeline still returns HTML from the concall node, you can either (a) keep a separate `concall_evaluation_html` string for legacy renderers, or (b) parse/LLM-extract into this object. The experiments frontend expects this object.

### 8a. Mainboard with concalls (`type: "mainboard_concall"`)

| Field              | Type   | Description |
|--------------------|--------|-------------|
| `sectionTitle`     | string | e.g. `"Concall Evaluation"` |
| `type`             | string | `"mainboard_concall"` |
| `summary`          | string | One-line summary sentence |
| `cards`            | array  | See **Concall card** below |
| `capex`            | array  | See **Capex item (mainboard)** below |
| `guidanceTable`    | object | See **Guidance table** below |
| `noConcallAlerts`  | array of string | Optional; quarters with no concall |

**Concall card:**

| Field      | Type   | Description |
|------------|--------|-------------|
| `period`   | string | e.g. `"Q2 FY26 (Jul–Sep 2025)"` |
| `badge`    | string | `"concall"` \| `"press-release"` \| `"ppt"` \| `"missing"` |
| `bullets`  | array of string | 3–4 bullet points |
| `guidance` | string \| null | Guidance given for that quarter |

**Capex item (mainboard):**

| Field     | Type   | Description |
|----------|--------|-------------|
| `project`| string | Project name |
| `amount` | string | e.g. `"₹45 Cr"` |
| `funding`| string | e.g. `"Internal accruals"` |

**Guidance table:**

| Field     | Type   | Description |
|----------|--------|-------------|
| `headers`| array of string | `["Metric", "Q4 FY24", "Q1 FY25", ...]` (Metric + 8 quarters) |
| `rows`   | array  | Each element: `{ "metric": string, "cells": [ { "value": string, "trend": "raised" \| "cut" \| "maintained" \| "neutral" } ] }` — one cell per quarter |

### 8b. SME / Company updates (`type: "sme_updates"`)

| Field        | Type   | Description |
|-------------|--------|-------------|
| `sectionTitle` | string | e.g. `"Company Updates"` |
| `type`      | string | `"sme_updates"` |
| `summaryBar`| object | `{ "badge": string, "text": string }` |
| `cards`     | array  | Same **Concall card** shape; `badge`: `"sme-concall"` \| `"sme-board"` \| `"sme-ppt"` \| `"sme-results"` \| `"sme-interview"` \| `"sme-missing"` |
| `capex`     | array  | Either mainboard-style `{ project, amount?, funding? }` or `{ "description": string }` |
| `sources`   | array  | `[ { "period": string, "source": string } ]` |

---

## 9. `sectoral`

**Type:** object

Sectoral headwinds and tailwinds (from **sectoral_prompt**). Can be a single narrative string or structured lists.

| Field     | Type            | Description |
|-----------|-----------------|-------------|
| `analysis`| string          | Optional narrative (from `sectoral_analysis` in state) |
| `headwinds`  | array of string | List of headwinds |
| `tailwinds`  | array of string | List of tailwinds |

If you only have a single `sectoral_analysis` string from the node, you can put it in `analysis` and leave `headwinds`/`tailwinds` empty, or parse/LLM-extract into lists.

---

## 10. `financials`

**Type:** object

All financial data for the report: key ratios, yearly + TTM metrics, and green/red highlights.

### 10.1 `financials.ratios`

**Type:** array of objects

From **resolve_company** → `financial_ratios`. Each element:

| Field   | Type   | Description |
|--------|--------|-------------|
| `metric` | string | e.g. `"ROE %"`, `"Debt/Equity"` |
| `value`  | string or number | Display value |
| `period` | string | e.g. `"TTM"`, `"Latest"` |

### 10.2 `financials.yearly_metrics`

**Type:** array of objects (chronological order, TTM last)

From **qoq_financials** → `yearly_metrics`. Each element:

| Field                 | Type    | Description |
|-----------------------|---------|-------------|
| `period_label`        | string  | e.g. `"FY22"`, `"FY24"`, `"TTM"` |
| `revenue_cr`          | number  | Revenue in Crores |
| `ebitda_cr`          | number  | EBITDA in Crores |
| `pat_cr`              | number  | PAT in Crores |
| `cfo_cr`              | number  | Cash flow from operations, Crores |
| `debt_equity`         | number  | Debt/Equity ratio |
| `roe`                 | number  | Optional; ROE % |
| `roce`                | number  | Optional; ROCE % |
| `revenue_yoy_pct`     | number \| null | YoY % change (null for first period / TTM if not computed) |
| `ebitda_yoy_pct`      | number \| null | |
| `pat_yoy_pct`         | number \| null | |
| `cfo_yoy_pct`         | number \| null | |
| `debt_equity_yoy_pct` | number \| null | |
| `roe_yoy_pct`         | number \| null | Optional |
| `roce_yoy_pct`        | number \| null | Optional |

### 10.3 `financials.highlights`

**Type:** object

From **qoq_financials** → `qoq_highlights` (LLM-derived from TTM balance sheet / income statement).

| Field | Type            | Description |
|-------|-----------------|-------------|
| `good`| array of string | Green flags / strengths |
| `bad` | array of string | Red flags / concerns |

---

## 11. `generated_at`

**Type:** string (ISO 8601 or display format)

e.g. `"2025-03-07T10:30:00Z"` or `"2025-03-07 16:00"`.

---

## Mapping from LangGraph state to this JSON

| Report JSON path       | LangGraph state / node source        |
|------------------------|--------------------------------------|
| `meta`                 | `symbol`, `exchange`, `company_name`, `sector`, `industry` (resolve_company) |
| `company.meta`         | `meta`                               |
| `company.quote`        | `quote`                              |
| `company.shareholding` | `shareholding`                       |
| `executive_summary`    | `executive_summary` (aggregate)      |
| `company_overview`     | `company_overview`                   |
| `management_research`  | `management_research`                |
| `financial_risk`       | `financial_risk`                     |
| `auditor_flags`        | `auditor_flags`                      |
| `concall`              | **Structured output** from concall node (or parse `concall_evaluation` HTML → object) |
| `sectoral.analysis`    | `sectoral_analysis`                  |
| `sectoral.headwinds`   | Parse or separate node              |
| `sectoral.tailwinds`   | Parse or separate node              |
| `financials.ratios`     | `financial_ratios`                  |
| `financials.yearly_metrics` | `yearly_metrics`                |
| `financials.highlights`| `qoq_highlights`                     |
| `generated_at`         | Set at report generation time        |

---

## Optional: legacy HTML concall

If you still produce HTML from the concall node and want to support legacy consumers:

- Add an optional top-level field: `concall_evaluation_html` (string).
- When present, a legacy renderer can use it; the experiments app uses `concall` (object) when available and ignores `concall_evaluation_html`.
