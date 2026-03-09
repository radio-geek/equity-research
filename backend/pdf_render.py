"""Render report payload to HTML and PDF for download."""

from __future__ import annotations

import logging
import re
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


def _concall_to_html(concall: dict | None) -> str:
    """Turn structured concall object into simple HTML for PDF."""
    if not concall or not isinstance(concall, dict):
        return ""
    parts = []
    if concall.get("summary"):
        parts.append(f"<p><strong>Summary:</strong> {concall['summary']}</p>")
    cards = concall.get("cards") or []
    for card in cards[:12]:
        period = card.get("period", "")
        bullets = card.get("bullets") or []
        guidance = card.get("guidance")
        parts.append(f"<p><strong>{period}</strong></p><ul>")
        for b in bullets[:5]:
            parts.append(f"<li>{b}</li>")
        parts.append("</ul>")
        if guidance:
            parts.append(f"<p><em>Guidance: {guidance}</em></p>")
    return "\n".join(parts) if parts else ""


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
    key_metrics = build_key_metrics(yearly_metrics)
    company = payload.get("company") or {}
    screener_quote = company.get("screener_quote") or {}
    if screener_quote.get("current_price") is not None:
        key_metrics["current_price"] = str(screener_quote["current_price"])
    if screener_quote.get("market_cap"):
        key_metrics["market_cap"] = str(screener_quote["market_cap"])
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
        "company_overview": _markdown_to_html(payload.get("company_overview") or ""),
        "management_research": _text_to_html(payload.get("management_research") or ""),
        "financial_risk": _text_to_html(payload.get("financial_risk") or ""),
        "auditor_flags": payload.get("auditor_flags") if payload.get("auditor_flags") else None,
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


def _strip_html_to_plain(html: str | None) -> str:
    """Replace simple HTML tags with plain text for reportlab."""
    if html is None:
        return ""
    if not isinstance(html, str):
        html = str(html)
    s = (
        html.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("<strong>", "").replace("</strong>", "")
        .replace("<em>", "").replace("</em>", "")
        .replace("<p>", "\n").replace("</p>", "")
        .replace("<br>", "\n").replace("<br/>", "\n")
        .replace("<li>", "• ").replace("</li>", "\n")
        .replace("<ul>", "\n").replace("</ul>", "\n")
    )
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


# ReportLab palette (match app)
_TEAL = "#0f766e"
_teal_light = "#e6f2f1"
_green = "#059669"
_green_light = "#e8f5e9"
_red = "#dc2626"
_red_light = "#ffebee"
_amber = "#d97706"
_amber_light = "#fffbeb"
_fg = "#1c1917"
_muted = "#78716c"
_surface = "#f5f5f4"
_surface2 = "#fafaf9"


def _pdf_fallback_reportlab(payload: dict) -> bytes:
    """Generate a styled PDF with reportlab (pure Python). Used when WeasyPrint system libs are missing."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx = payload_to_template_context(payload)
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    styles = getSampleStyleSheet()
    teal = colors.HexColor(_TEAL)
    body_style = ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=10,
        textColor=colors.HexColor(_fg),
    )
    heading_style = ParagraphStyle(
        name="Heading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        spaceAfter=6,
        spaceBefore=18,
        textColor=colors.HexColor(_fg),
        borderPadding=(0, 0, 4, 0),
    )
    flow = []

    # ---- Title block (accent bar): name + price (black) + % (green/red), then symbol + time ----
    company_name = (ctx.get("company_name") or "").replace("&", "&amp;")
    symbol = (ctx.get("symbol") or "").replace("&", "&amp;")
    screener_quote = ctx.get("screener_quote") or {}
    price_part = ""
    if screener_quote.get("current_price") is not None:
        price_part = f" &nbsp; <font size=\"11\" color=\"#1c1917\">₹ {screener_quote['current_price']}</font>"
        pct = (screener_quote.get("price_change_pct") or "").strip()
        if pct:
            hex_color = "#dc2626" if pct.startswith("-") else "#059669"
            price_part += f" &nbsp; <font size=\"10\" color=\"{hex_color}\">{pct}</font>"
    line1 = f'<b><font size="14" color="#ffffff">{company_name}</font></b>{price_part}'
    line2_parts = [f'<font size="10" color="#ffffff">({symbol})</font>']
    if screener_quote.get("last_price_updated"):
        line2_parts.append(f'<font size="9" color="#e0f2f1"> {screener_quote["last_price_updated"]}</font>')
    meta_line = f"{ctx.get('exchange', 'NSE')} · Generated {ctx.get('generated_at', '')}"
    line2_parts.append(f'<font size="9" color="#e0f2f1"> · {meta_line}</font>')
    title_table = Table([
        [Paragraph(line1)],
        [Paragraph(" ".join(line2_parts))],
    ], colWidths=[16 * cm])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), teal),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
    ]))
    flow.append(title_table)
    flow.append(Spacer(1, 12))
    # Key metrics (TTM) at top
    key_metrics = ctx.get("key_metrics") or {}
    if isinstance(key_metrics, dict) and (key_metrics.get("revenue_cr") or key_metrics.get("pat_cr") or key_metrics.get("roe") or key_metrics.get("market_cap")):
        parts = ["<b>Key metrics (TTM):</b>"]
        if key_metrics.get("market_cap"):
            parts.append(f"Market Cap ₹ {key_metrics['market_cap']}")
        if key_metrics.get("revenue_cr"):
            parts.append(f"Revenue {key_metrics['revenue_cr']} Cr")
        if key_metrics.get("pat_cr"):
            parts.append(f"PAT {key_metrics['pat_cr']} Cr")
        if key_metrics.get("roe"):
            parts.append(f"ROE {key_metrics['roe']}")
        if key_metrics.get("roce"):
            parts.append(f"ROCE {key_metrics['roce']}")
        if key_metrics.get("debt_equity"):
            parts.append(f"D/E {key_metrics['debt_equity']}")
        if key_metrics.get("eps"):
            parts.append(f"EPS ₹{key_metrics['eps']}")
        if key_metrics.get("debt_cr"):
            parts.append(f"Debt {key_metrics['debt_cr']} Cr")
        flow.append(Paragraph(" · ".join(parts).replace("&", "&amp;"), body_style))
        flow.append(Spacer(1, 12))
    flow.append(Spacer(1, 8))

    def section(heading: str, text_key: str) -> None:
        flow.append(Paragraph(heading.replace("&", "&amp;"), heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), teal),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])))
        flow.append(Spacer(1, 8))
        text = _strip_html_to_plain(ctx.get(text_key) or "")
        if text:
            flow.append(Paragraph(text.replace("&", "&amp;").replace("\n", "<br/>"), body_style))

    for h, k in [
        ("Executive Summary", "executive_summary"),
        ("Company Overview", "company_overview"),
        ("Management & Governance", "management_research"),
        ("Financial Risk", "financial_risk"),
    ]:
        section(h, k)

    # ---- Financial Strength Scorecard (report card style) ----
    scorecard = ctx.get("financial_scorecard")
    if isinstance(scorecard, dict):
        flow.append(Paragraph("Financial Strength Scorecard", heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), teal),
        ])))
        flow.append(Spacer(1, 8))
        intro = Paragraph(
            '<font size="9" color="#78716c">30-second health check across 6 core signals (TTM and YoY).</font>',
            body_style,
        )
        flow.append(intro)
        flow.append(Spacer(1, 8))
        # Grade + verdict row
        tier = scorecard.get("verdict_tier") or "average"
        letter_grade = scorecard.get("letter_grade") or "—"
        score_val = scorecard.get("score", 0)
        total_val = scorecard.get("total", 6)
        verdict_text = (scorecard.get("verdict") or "").replace("&", "&amp;")
        if tier == "strong":
            grade_bg = colors.HexColor(_green)
            verdict_bg = colors.HexColor(_green_light)
            verdict_border = _green
        elif tier == "weak":
            grade_bg = colors.HexColor(_red)
            verdict_bg = colors.HexColor(_red_light)
            verdict_border = _red
        else:
            grade_bg = colors.HexColor(_amber)
            verdict_bg = colors.HexColor(_amber_light)
            verdict_border = _amber
        grade_cell = Paragraph(
            f'<b><font size="16" color="#ffffff">{letter_grade}</font></b>',
            ParagraphStyle(name="Grade", fontSize=16, textColor=colors.white, alignment=1),
        )
        verdict_para = Paragraph(f'<b>Verdict:</b> {verdict_text}', body_style) if verdict_text else Paragraph("", body_style)
        score_table = Table(
            [[grade_cell, f"{score_val} / {total_val}", verdict_para]],
            colWidths=[2 * cm, 2.5 * cm, 11.5 * cm],
        )
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), grade_bg),
            ("BACKGROUND", (2, 0), (2, -1), verdict_bg),
            ("BOX", (2, 0), (2, -1), 0.5, colors.HexColor(verdict_border)),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (1, 0), (1, -1), 11),
        ]))
        flow.append(score_table)
        flow.append(Spacer(1, 8))
        # Metrics table: Metric | Value | Signal | Pass/Fail
        metrics = scorecard.get("metrics") or []
        if metrics:
            m_headers = ["Metric", "Value", "Signal", "Result"]
            m_data = [m_headers]
            for m in metrics:
                name = (m.get("name") or "").replace("&", "&amp;")
                val = (m.get("display_value") or "").replace("&", "&amp;")
                sig = (m.get("signal") or "").replace("&", "&amp;")
                result = "Pass" if m.get("passed") else "Needs improvement"
                m_data.append([name, val, sig, result])
            m_table = Table(m_data, colWidths=[4 * cm, 3.5 * cm, 4.5 * cm, 4 * cm])
            m_style = [
                ("BACKGROUND", (0, 0), (-1, 0), teal),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e5e4")),
            ]
            for i, row in enumerate(m_data[1:], start=1):
                passed = metrics[i - 1].get("passed")
                if passed:
                    m_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(_green_light)))
                    m_style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor(_green)))
                else:
                    m_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(_red_light)))
                    m_style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor(_red)))
            m_table.setStyle(TableStyle(m_style))
            flow.append(m_table)
        flow.append(Spacer(1, 16))

    # ---- 5-Year Financial Trend ----
    five_year = ctx.get("five_year_trend") or {}
    if five_year.get("headers") and five_year.get("rows"):
        flow.append(Paragraph("5-Year Financial Trend", heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), teal),
        ])))
        flow.append(Spacer(1, 8))
        intro = Paragraph(
            '<font size="9" color="#78716c">Latest 5 completed financial years. Values in Rs Crores unless noted.</font>',
            body_style,
        )
        flow.append(intro)
        flow.append(Spacer(1, 6))
        headers = ["Metric", "Unit"] + list(five_year["headers"])
        data = [headers]
        for row in five_year.get("rows", []):
            cells = [row.get("metric", ""), row.get("unit", "")]
            cells.extend(str(c) for c in row.get("cells", []))
            data.append(cells)
        col_count = len(headers)
        col_width = 16.0 * cm / col_count
        t = Table(data, colWidths=[3.2 * cm, 1.2 * cm] + [col_width] * (col_count - 2))
        st = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), teal),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor(_surface)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e5e4")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ])
        for i in range(1, len(data)):
            if i % 2 == 0:
                st.add("BACKGROUND", (1, i), (-1, i), colors.HexColor(_surface2))
        t.setStyle(st)
        flow.append(t)
        flow.append(Spacer(1, 8))
        if ctx.get("trend_insight_summary"):
            flow.append(Paragraph(
                ctx["trend_insight_summary"].replace("&", "&amp;").replace("\n", "<br/>"),
                body_style,
            ))
        flow.append(Spacer(1, 12))

    # ---- Balance sheet highlights (Strengths / Concerns) ----
    highlights = ctx.get("qoq_highlights") or {}
    if isinstance(highlights, dict):
        for box_title, color_hex, bg_hex in [
            ("Strengths", _green, _green_light),
            ("Concerns", _red, _red_light),
        ]:
            points = highlights.get("good" if "Strengths" in box_title else "bad") or []
            if not points:
                continue
            content = "<br/>".join("• " + str(p).replace("&", "&amp;") for p in points[:8])
            box = Table([
                [Paragraph(f'<b><font color="{color_hex}" size="10">{box_title.replace("&", "&amp;")} (TTM)</font></b>')],
                [Paragraph(f'<font size="9" color="#1c1917">{content}</font>')],
            ], colWidths=[16 * cm])
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg_hex)),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(color_hex)),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor(color_hex)),
            ]))
            flow.append(box)
            flow.append(Spacer(1, 12))

    if ctx.get("auditor_flags"):
        flow.append(Paragraph("Auditor Flags & Qualifications".replace("&", "&amp;"), heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), teal)])))
        flow.append(Spacer(1, 8))
        flow.append(Paragraph(
            _strip_html_to_plain(ctx["auditor_flags"]).replace("&", "&amp;").replace("\n", "<br/>"),
            body_style,
        ))
        flow.append(Spacer(1, 12))

    flow.append(Paragraph(ctx.get("concall_section_title", "Concall Evaluation").replace("&", "&amp;"), heading_style))
    flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), teal)])))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(
        _strip_html_to_plain(ctx.get("concall_evaluation", "")).replace("&", "&amp;").replace("\n", "<br/>"),
        body_style,
    ))
    flow.append(Spacer(1, 12))

    flow.append(Paragraph("Sectoral Headwinds & Tailwinds".replace("&", "&amp;"), heading_style))
    flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), teal)])))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(
        _strip_html_to_plain(ctx.get("sectoral_analysis", "—")).replace("&", "&amp;").replace("\n", "<br/>"),
        body_style,
    ))

    doc.build(flow)
    return buf.getvalue()


def render_payload_to_pdf(payload: dict) -> bytes:
    """Render report payload to PDF bytes. Uses WeasyPrint if available, else xhtml2pdf fallback."""
    html_content = render_payload_to_html(payload)
    styles_path = _REPO_ROOT / "src" / "report" / "styles.css"
    template_dir = _REPO_ROOT / "src" / "report" / "templates"

    try:
        from weasyprint import HTML, CSS
        if not styles_path.is_file():
            raise FileNotFoundError(f"PDF styles not found: {styles_path}")
        html_doc = HTML(string=html_content, base_url=str(template_dir))
        css = CSS(filename=str(styles_path))
        return html_doc.write_pdf(stylesheets=[css])
    except (ImportError, OSError) as e:
        log.warning("WeasyPrint unavailable (%s), using reportlab fallback", e)
        return _pdf_fallback_reportlab(payload)
    except Exception as e:
        log.warning("WeasyPrint failed (%s), using reportlab fallback", e)
        return _pdf_fallback_reportlab(payload)
