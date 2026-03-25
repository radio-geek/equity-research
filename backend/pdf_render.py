"""Render report payload to HTML and PDF for download."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _markdown_to_html(text: str) -> str:
    """Convert Markdown to HTML for report/PDF. Uses 'tables' extension. Output is escaped by the library."""
    if not text or not text.strip():
        return ""
    try:
        import markdown
        return markdown.markdown(text, extensions=["tables"])
    except Exception as e:
        log.warning("Markdown conversion failed, falling back to plain text: %s", e)
        return _text_to_html(text)


def _text_to_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return "<p>" + re.sub(r"\n\n+", "</p><p>", text).replace("\n", "<br>") + "</p>"


def _sectoral_bullets_to_html(bullets: list[str]) -> str:
    """Convert list of markdown bullet strings to HTML <ul><li>...</li></ul> with links preserved."""
    if not bullets:
        return ""
    items = []
    for raw in bullets:
        if not raw or not raw.strip():
            continue
        html = _markdown_to_html(raw.strip())
        if html.strip():
            items.append("<li>" + html.strip() + "</li>")
    if not items:
        return ""
    return "<ul class=\"sectoral-list\">" + "".join(items) + "</ul>"


def _company_overview_structured_to_html(coh: dict | None) -> str:
    """Build Company Overview HTML from structured object (opening, value_chain, table, products, timeline)."""
    if not coh or not isinstance(coh, dict):
        return ""
    parts = []
    opening = coh.get("opening")
    if opening and isinstance(opening, str):
        parts.append(f"<p>{_escape_html(opening)}</p>")
    vc = coh.get("value_chain")
    if isinstance(vc, dict):
        stages = vc.get("stages")
        if isinstance(stages, list) and stages:
            chain = " → ".join(_escape_html(str(s)) for s in stages)
            parts.append(f"<p><strong>Value chain:</strong> {chain}</p>")
        stage_indices = vc.get("company_stage_indices")
        if isinstance(stage_indices, list) and stages:
            valid = [i for i in stage_indices if isinstance(i, int) and 0 <= i < len(stages)]
            if valid:
                if len(valid) == len(stages):
                    parts.append("<p><strong>Company spans the full value chain.</strong></p>")
                else:
                    names = ", ".join(_escape_html(str(stages[i])) for i in sorted(valid))
                    parts.append(f"<p><strong>Company operates in:</strong> {names}</p>")
        elif stages:
            stage_idx = vc.get("company_stage_index")
            if stage_idx is not None and isinstance(stage_idx, int) and 0 <= stage_idx < len(stages):
                stage_name = _escape_html(str(stages[stage_idx]))
                parts.append(f"<p><strong>Company operates in:</strong> {stage_name}</p>")
        desc = vc.get("company_position_description")
        if desc and isinstance(desc, str):
            parts.append(f"<p>{_escape_html(desc)}</p>")
        elif vc.get("company_position") and isinstance(vc["company_position"], str):
            parts.append(f"<p><strong>Company position:</strong> {_escape_html(vc['company_position'])}</p>")
    bmt = coh.get("business_model_table")
    if isinstance(bmt, dict):
        rows = bmt.get("rows")
        if isinstance(rows, list) and rows:
            parts.append("<p><strong>Business model & revenue drivers</strong></p>")
            parts.append("<table class=\"report-table\"><thead><tr><th>Segment</th><th>Importance</th><th>Description</th></tr></thead><tbody>")
            for r in rows:
                if isinstance(r, dict):
                    seg = _escape_html(str(r.get("segment", "")))
                    imp = _escape_html(str(r.get("importance", "")))
                    desc = _escape_html(str(r.get("description", "")))
                    parts.append(f"<tr><td>{seg}</td><td>{imp}</td><td>{desc}</td></tr>")
            parts.append("</tbody></table>")
    kp = coh.get("key_products")
    if isinstance(kp, list) and kp:
        parts.append("<p><strong>Key products / services</strong></p><ul>")
        for item in kp:
            if item:
                parts.append(f"<li>{_escape_html(str(item))}</li>")
        parts.append("</ul>")
    rd = coh.get("recent_developments")
    if isinstance(rd, list) and rd:
        parts.append("<p><strong>Recent developments & milestones</strong></p><ul>")
        for item in rd:
            if isinstance(item, dict):
                y = item.get("year", "")
                e = item.get("event", "")
                if y or e:
                    parts.append(f"<li><strong>{_escape_html(str(y))}</strong> – {_escape_html(str(e))}</li>")
        parts.append("</ul>")
    return "\n".join(parts) if parts else ""


def _escape_html(s: str) -> str:
    """Escape HTML entities in a string."""
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_MONTHS = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_VERDICT_STYLES = {
    "RISK": "background:#c62828;color:#fff;",
    "OK":   "background:#e65100;color:#fff;",
    "GOOD": "background:#059669;color:#fff;",
}

_SIGNAL_STYLES = {
    "red":    ("audit-timeline-item--red", "#c62828"),
    "yellow": ("audit-timeline-item--yellow", "#ef6c00"),
    "green":  ("audit-timeline-item--green", "#059669"),
}


def _auditor_timeline_to_html(structured: dict | None) -> str:
    """Build governance verdict + event cards HTML from auditor_flags_structured."""
    if not structured or not isinstance(structured, dict):
        return ""

    verdict = (structured.get("verdict") or "OK").strip().upper()
    summary = (structured.get("summary") or "").strip()
    events = structured.get("events")
    if not isinstance(events, list):
        events = []

    if not verdict and not summary and not events:
        return ""

    parts: list[str] = []

    vstyle = _VERDICT_STYLES.get(verdict, _VERDICT_STYLES["OK"])
    parts.append('<div class="audit-verdict-block">')
    parts.append(f'<span class="audit-verdict-badge" style="{vstyle}">{_escape_html(verdict)}</span>')
    if summary:
        parts.append(f'<span class="audit-verdict-text">{_escape_html(summary)}</span>')
    parts.append("</div>")

    if events:
        parts.append('<div class="audit-timeline">')
        for ev in events:
            if not isinstance(ev, dict):
                continue
            signal = (ev.get("signal") or "yellow").strip().lower()
            sig_class, _ = _SIGNAL_STYLES.get(signal, _SIGNAL_STYLES["yellow"])
            sig_label = {"red": "RISK", "yellow": "OK", "green": "GOOD"}.get(signal, "OK")

            date_val = ev.get("date") or ""
            fy = _escape_html(str(ev.get("fy") or ""))
            category = _escape_html(str(ev.get("category") or ""))
            typ = _escape_html(str(ev.get("type") or ""))
            issue = _escape_html(str(ev.get("issue") or ""))
            evidence = (ev.get("evidence") or "").strip()
            status = (ev.get("status") or "").strip()

            date_label = fy
            if date_val and len(date_val) >= 7 and date_val[4] == "-":
                try:
                    y, m = date_val[:4], date_val[5:7]
                    mi = int(m)
                    if 1 <= mi <= 12:
                        date_label = f"{fy} · {_MONTHS[mi]} {y}"
                except (ValueError, IndexError):
                    pass

            parts.append(f'<div class="audit-timeline-item {sig_class}">')
            parts.append('<div class="audit-timeline-item-header">')
            parts.append(f'<span class="audit-signal-badge audit-signal-badge--{signal}">{sig_label}</span>')
            if category:
                parts.append(f'<span class="audit-timeline-category">{category}</span>')
            parts.append(f'<span class="audit-timeline-date">{_escape_html(date_label)}</span>')
            if status:
                parts.append(f'<span class="audit-timeline-status">{_escape_html(status)}</span>')
            parts.append("</div>")
            if typ and typ != "Other":
                parts.append(f'<div class="audit-timeline-type">{typ}</div>')
            parts.append(f'<p class="audit-timeline-issue">{issue}</p>')
            if evidence:
                parts.append(f'<p class="audit-timeline-evidence">"{_escape_html(evidence)}"</p>')
            parts.append("</div>")
        parts.append("</div>")

    return "\n".join(parts)


def _concall_get(d: dict, *keys: str) -> Any:
    """Get first present key from dict (camelCase or snake_case)."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _concall_to_html(concall: dict | None) -> str:
    """Turn structured concall object into HTML matching the web ConcallSection (cards, events, capex, guidance, etc.)."""
    if not concall or not isinstance(concall, dict):
        return ""
    parts: list[str] = []
    ctype = _concall_get(concall, "type", "Type") or ""

    # ---- no_concall_updates: message + investor presentation, order book, press releases ----
    if ctype == "no_concall_updates":
        msg = _concall_get(concall, "noConcallMessage", "no_concall_message") or "No concalls held in last 8 quarters"
        parts.append(
            f'<div class="no-concall-alerts"><div class="no-concall-alert">⚠ {_escape_html(msg)}</div></div>'
        )
        ip = _concall_get(concall, "investorPresentation", "investor_presentation")
        if isinstance(ip, dict):
            bullets = ip.get("bullets") or ip.get("Bullets") or []
            if bullets:
                period = ip.get("period") or ip.get("Period") or ""
                link = ip.get("link") or ip.get("Link")
                parts.append('<div class="capex-section"><h3>Investor Presentation</h3>')
                if period:
                    parts.append(f"<p><em>{_escape_html(str(period))}</em></p>")
                if link:
                    parts.append(f'<p><a href="{_escape_html(str(link))}">View PPT ↗</a></p>')
                parts.append("<ul>")
                for b in bullets[:15]:
                    parts.append(f"<li>{_markdown_to_html(str(b)).strip() or _escape_html(str(b))}</li>")
                parts.append("</ul></div>")
        ob = _concall_get(concall, "orderBook", "order_book")
        if isinstance(ob, dict):
            bullets = ob.get("bullets") or ob.get("Bullets") or []
            if bullets:
                parts.append("<h3>Order Book &amp; Contracts</h3><ul>")
                for b in bullets[:15]:
                    parts.append(f"<li>{_markdown_to_html(str(b)).strip() or _escape_html(str(b))}</li>")
                parts.append("</ul>")
        pr = _concall_get(concall, "pressReleases", "press_releases")
        if isinstance(pr, dict):
            bullets = pr.get("bullets") or pr.get("Bullets") or []
            if bullets:
                parts.append("<h3>Press Releases</h3><ul>")
                for b in bullets[:15]:
                    parts.append(f"<li>{_markdown_to_html(str(b)).strip() or _escape_html(str(b))}</li>")
                parts.append("</ul>")
        return "\n".join(parts) if parts else ""

    # ---- mainboard_concall / sme_updates: summary, summaryBar, cards, capex, guidanceTable, alerts, sources ----
    summary = _concall_get(concall, "summary", "Summary")
    if summary and isinstance(summary, str):
        parts.append(f'<p class="concall-section-header">{_escape_html(summary)}</p>')
    summary_bar = _concall_get(concall, "summaryBar", "summary_bar")
    if isinstance(summary_bar, dict):
        badge = summary_bar.get("badge") or summary_bar.get("Badge")
        text = summary_bar.get("text") or summary_bar.get("Text")
        if text:
            b = f'<span class="concall-type-badge concall-badge">{_escape_html(str(badge or ""))}</span>' if badge else ""
            parts.append(f'<p>{b} {_escape_html(str(text))}</p>')

    cards = _concall_get(concall, "cards", "Cards") or []
    if not isinstance(cards, list):
        cards = []
    event_type_labels = {
        "acquisition": "Acquisition",
        "fundraise": "Fundraise",
        "stake_sale": "Stake Sale",
        "capex": "Capex",
        "order_win": "Order Win",
        "mgmt_change": "Mgmt Change",
        "guidance_change": "Guidance",
    }
    badge_class = {
        "concall": "concall-badge",
        "press-release": "press-release-badge",
        "ppt": "ppt-badge",
        "missing": "missing-badge",
        "sme-concall": "concall-badge",
        "sme-board": "ppt-badge",
        "sme-ppt": "ppt-badge",
        "sme-results": "press-release-badge",
        "sme-interview": "ppt-badge",
        "sme-missing": "missing-badge",
    }
    if cards:
        parts.append('<div class="concall-cards-grid">')
    for i, card in enumerate(cards[:12]):
        if not isinstance(card, dict):
            continue
        period = _concall_get(card, "period", "Period") or "—"
        badge = _concall_get(card, "badge", "Badge")
        link = _concall_get(card, "link", "Link")
        badge_cl = badge_class.get(str(badge).lower() if badge else "", "ppt-badge")
        link_html = ""
        if link:
            link_html = f' <a href="{_escape_html(str(link))}">View source ↗</a>'
        parts.append(
            f'<div class="concall-card concall-card-{(i % 8) + 1}">'
            f'<div class="concall-card-header">{_escape_html(str(period))}'
            f'<span class="concall-type-badge {badge_cl}">{_escape_html(str(badge or ""))}</span>{link_html}</div>'
        )
        events = _concall_get(card, "events", "Events") or []
        if isinstance(events, list):
            for ev in events[:8]:
                if not isinstance(ev, dict):
                    continue
                etype = ev.get("type") or ev.get("Type")
                headline = ev.get("headline") or ev.get("Headline")
                details = ev.get("details") or ev.get("Details") or []
                if headline:
                    label = event_type_labels.get(str(etype or "").lower(), str(etype or "Event"))
                    parts.append(f'<p><strong>{_escape_html(str(label))}:</strong> {_escape_html(str(headline))}</p>')
                for d in details[:5]:
                    if d:
                        parts.append(f"<p>• {_escape_html(str(d))}</p>")
        bullets = _concall_get(card, "bullets", "Bullets") or []
        if isinstance(bullets, list) and bullets:
            parts.append("<ul>")
            for b in bullets[:9]:
                parts.append(f"<li>{_escape_html(str(b))}</li>")
            parts.append("</ul>")
        guidance = _concall_get(card, "guidance", "Guidance")
        if guidance:
            parts.append(f'<p><em>Guidance: {_escape_html(str(guidance))}</em></p>')
        qa = _concall_get(card, "qaHighlights", "qa_highlights") or []
        if isinstance(qa, list) and qa:
            parts.append("<p><strong>Key Q&amp;A</strong></p>")
            for qa_item in qa[:5]:
                if isinstance(qa_item, dict):
                    q = qa_item.get("q") or qa_item.get("Q")
                    a = qa_item.get("a") or qa_item.get("A")
                    if q:
                        parts.append(f"<p><strong>Q:</strong> {_escape_html(str(q))}</p>")
                    if a:
                        parts.append(f"<p><strong>A:</strong> {_escape_html(str(a))}</p>")
        parts.append("</div>")
    if cards:
        parts.append("</div>")

    capex_list = _concall_get(concall, "capex", "Capex") or []
    if isinstance(capex_list, list) and capex_list:
        parts.append('<div class="capex-section"><h3>Capital expenditure &amp; major developments</h3>')
        for item in capex_list[:10]:
            if not isinstance(item, dict):
                continue
            project = _concall_get(item, "project", "Project")
            amount = _concall_get(item, "amount", "Amount")
            funding = _concall_get(item, "funding", "Funding")
            desc = _concall_get(item, "description", "Description")
            if project or desc:
                parts.append("<div class=\"capex-item\">")
                if project:
                    parts.append(f"<strong>{_escape_html(str(project))}</strong>")
                    if amount:
                        parts.append(f' <span class="capex-amount">{_escape_html(str(amount))}</span>')
                    if funding:
                        parts.append(f'<br><span class="capex-funding">Funding: {_escape_html(str(funding))}</span>')
                else:
                    parts.append(_escape_html(str(desc or "")))
                parts.append("</div>")
        parts.append("</div>")

    gt = _concall_get(concall, "guidanceTable", "guidance_table")
    if isinstance(gt, dict):
        headers = gt.get("headers") or gt.get("Headers") or []
        rows = gt.get("rows") or gt.get("Rows") or []
        if headers and rows:
            parts.append('<div class="guidance-section"><h3>Guidance tracker</h3>')
            parts.append('<table class="guidance-table"><thead><tr>')
            for h in headers:
                parts.append(f"<th>{_escape_html(str(h))}</th>")
            parts.append("</tr></thead><tbody>")
            trend_class = {"raised": "guidance-raised", "cut": "guidance-cut", "maintained": "guidance-maintained"}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                metric = row.get("metric") or row.get("Metric") or "—"
                cells = row.get("cells") or row.get("Cells") or []
                parts.append(f"<tr><td>{_escape_html(str(metric))}</td>")
                for cell in cells:
                    if isinstance(cell, dict):
                        val = cell.get("value") or cell.get("Value") or "—"
                        trend = (cell.get("trend") or cell.get("Trend") or "neutral").lower()
                        cl = trend_class.get(trend, "")
                        parts.append(f'<td class="{cl}">{_escape_html(str(val))}</td>')
                    else:
                        parts.append(f"<td>{_escape_html(str(cell))}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
            parts.append("<p><small>Green = Raised · Red = Cut · Yellow = Maintained</small></p></div>")

    alerts = _concall_get(concall, "noConcallAlerts", "no_concall_alerts") or []
    if isinstance(alerts, list) and alerts:
        parts.append('<div class="no-concall-alerts">')
        for msg in alerts[:5]:
            parts.append(f'<div class="no-concall-alert">{_escape_html(str(msg))}</div>')
        parts.append("</div>")

    sources = _concall_get(concall, "sources", "Sources") or []
    if isinstance(sources, list) and sources and ctype == "sme_updates":
        parts.append("<h3>Information sources</h3><ul>")
        for s in sources[:10]:
            if isinstance(s, dict):
                period = s.get("period") or s.get("Period") or ""
                source = s.get("source") or s.get("Source") or ""
                parts.append(f"<li><strong>{_escape_html(str(period))}:</strong> {_escape_html(str(source))}</li>")
            parts.append("</ul>")

    if not parts:
        return ""
    return '<div class="concall-section">' + "\n".join(parts) + "</div>"


def payload_to_template_context(payload: dict) -> dict[str, Any]:
    """Build Jinja template context from report payload."""
    meta = payload.get("meta") or {}
    financials = payload.get("financials") or {}
    yearly_metrics = financials.get("yearly_metrics") or []
    highlights = financials.get("highlights") or {}
    financial_scorecard = financials.get("financial_scorecard")
    five_year_trend = financials.get("five_year_trend") or {"headers": [], "rows": []}
    trend_insight_summary = financials.get("trend_insight_summary") or ""
    sectoral = payload.get("sectoral") or {}

    concall = payload.get("concall")
    concall_html = _concall_to_html(concall)
    concall_section_title = "Concall Evaluation"
    if isinstance(concall, dict) and concall.get("sectionTitle"):
        concall_section_title = str(concall["sectionTitle"])

    sectoral_analysis = sectoral.get("analysis") or ""
    sectoral_tailwinds: list[str] = sectoral.get("tailwinds") or []
    sectoral_headwinds: list[str] = sectoral.get("headwinds") or []
    sectoral_intro_html = _markdown_to_html(sectoral_analysis) if sectoral_analysis else ""
    sectoral_tailwinds_html = _sectoral_bullets_to_html(sectoral_tailwinds)
    sectoral_headwinds_html = _sectoral_bullets_to_html(sectoral_headwinds)
    # Legacy combined block for reportlab PDF path (plain text)
    sectoral_combined = sectoral_intro_html or ""
    if sectoral_tailwinds_html or sectoral_headwinds_html:
        if sectoral_combined:
            sectoral_combined += " "
        if sectoral_tailwinds_html:
            sectoral_combined += "<p><strong>Tailwinds:</strong></p>" + sectoral_tailwinds_html
        if sectoral_headwinds_html:
            sectoral_combined += "<p><strong>Headwinds:</strong></p>" + sectoral_headwinds_html

    generated_at = payload.get("generated_at") or ""
    if not isinstance(generated_at, str):
        generated_at = str(generated_at)
    generated_at = generated_at.replace("T", " ").replace("Z", "")[:16]

    from src.report.financial_evaluation import build_key_metrics
    company = payload.get("company") or {}
    screener_quote = company.get("screener_quote") or {}
    key_metrics = dict(payload.get("key_metrics") or build_key_metrics(yearly_metrics))
    if screener_quote.get("current_price") is not None:
        key_metrics["current_price"] = str(screener_quote["current_price"])
    if screener_quote.get("market_cap"):
        key_metrics["market_cap"] = str(screener_quote["market_cap"])
    if screener_quote.get("stock_pe") is not None:
        key_metrics["pe"] = str(screener_quote["stock_pe"])
    if screener_quote.get("last_price_updated"):
        key_metrics["last_price_updated"] = str(screener_quote["last_price_updated"])

    return {
        "print_only": True,
        "symbol": meta.get("symbol", ""),
        "exchange": meta.get("exchange", "NSE"),
        "company_name": meta.get("company_name", meta.get("symbol", "")),
        "generated_at": generated_at,
        "key_metrics": key_metrics,
        "screener_quote": screener_quote,
        "executive_summary": _text_to_html(payload.get("executive_summary") or ""),
        "company_overview": (
            _company_overview_structured_to_html(payload.get("company_overview_structured"))
            if payload.get("company_overview_structured")
            else _markdown_to_html(payload.get("company_overview") or "")
        ),
        "management_research": _markdown_to_html(payload.get("management_research") or ""),
        "management_people": payload.get("management_people") if isinstance(payload.get("management_people"), list) else [],
        "management_governance_news": payload.get("management_governance_news") if isinstance(payload.get("management_governance_news"), list) else [],
        "financial_risk": _text_to_html(payload.get("financial_risk") or ""),
        "auditor_flags": (
            _auditor_timeline_to_html(payload.get("auditor_flags_structured"))
            if payload.get("auditor_flags_structured")
            else (_markdown_to_html(payload.get("auditor_flags") or "") if payload.get("auditor_flags") else None)
        ),
        "financial_ratios": financials.get("ratios") or [],
        "financial_scorecard": financial_scorecard,
        "five_year_trend": five_year_trend,
        "trend_insight_summary": trend_insight_summary,
        "qoq_highlights": highlights,
        "concall_evaluation": concall_html or "<p>No concall data.</p>",
        "concall_section_title": concall_section_title,
        "sectoral_intro": sectoral_intro_html or "<p>—</p>",
        "sectoral_tailwinds_html": sectoral_tailwinds_html,
        "sectoral_headwinds_html": sectoral_headwinds_html,
        "sectoral_analysis": sectoral_combined or "<p>—</p>",
    }


def render_payload_to_html(payload: dict) -> str:
    """Render report payload to HTML string using Jinja template."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = _REPO_ROOT / "src" / "report" / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("base.html")
    ctx = payload_to_template_context(payload)
    return template.render(**ctx)


def _chromium_executable() -> str | None:
    """Path to minimal Chromium (Sparticuz bundle).

    Resolution order:
    1. CHROMIUM_PATH env var (explicit override)
    2. /opt/chromium/chromium  — Render / Docker / build.sh path
    3. /var/task/chromium-bin/chromium — Vercel Lambda (project-relative download)
    4. None → Playwright uses its own installed browser (local dev)
    """
    path = os.environ.get("CHROMIUM_PATH")
    if path and os.path.isfile(path):
        return path
    for candidate in ("/opt/chromium/chromium", "/var/task/chromium-bin/chromium"):
        if os.path.isfile(candidate):
            return candidate
    return None


def _pdf_playwright(payload: dict) -> bytes | None:
    """Generate PDF via headless Chromium (Playwright). Uses CHROMIUM_PATH or /opt/chromium when set; else Playwright's installed browser (local dev)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    executable = _chromium_executable()
    html_content = render_payload_to_html(payload)
    styles_path = _REPO_ROOT / "src" / "report" / "styles.css"
    css_content = styles_path.read_text(encoding="utf-8") if styles_path.is_file() else ""
    launch_kwargs: dict = {"headless": True, "timeout": 15_000}
    if executable:
        launch_kwargs["executable_path"] = executable
        launch_kwargs["args"] = ["--no-sandbox", "--disable-dev-shm-usage", "--single-process"]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page()
                page.set_content(html_content, wait_until="load")
                if css_content:
                    page.add_style_tag(content=css_content)
                pdf_bytes = page.pdf(
                    format="A4",
                    margin={"top": "2.2cm", "right": "2cm", "bottom": "2.2cm", "left": "2cm"},
                    print_background=True,
                )
                return pdf_bytes
            finally:
                browser.close()
    except Exception:
        raise  # let caller log (outside _suppress_stderr) so the message is visible


@contextlib.contextmanager
def _suppress_stderr():
    """Context manager that redirects stderr to devnull at fd level so C libraries (e.g. WeasyPrint deps) don't print."""
    stderr_fd = sys.stderr.fileno()
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        yield
        return
    try:
        old_stderr = os.dup(stderr_fd)
        try:
            os.dup2(devnull_fd, stderr_fd)
            yield
        finally:
            os.dup2(old_stderr, stderr_fd)
            os.close(old_stderr)
    finally:
        os.close(devnull_fd)


def render_payload_to_pdf(payload: dict) -> bytes:
    """Render report payload to PDF using Playwright only. Raises on failure."""
    playwright_pdf = None
    playwright_error = None
    with _suppress_stderr():
        try:
            playwright_pdf = _pdf_playwright(payload)
        except Exception as e:
            playwright_error = e

    if playwright_pdf is not None:
        return playwright_pdf
    if playwright_error is not None:
        raise RuntimeError(f"PDF generation failed: {playwright_error}") from playwright_error
    raise RuntimeError(
        "PDF generation failed: Chromium not available. Run ./build.sh or playwright install chromium."
    )
