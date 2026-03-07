"""Render report payload to HTML and PDF for download."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent


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
    sectoral = payload.get("sectoral") or {}

    # Build yearly_table using same helper as report
    yearly_table = {"headers": [], "rows": []}
    if yearly_metrics:
        from src.report.charts import yearly_metrics_to_table
        yearly_table = yearly_metrics_to_table(yearly_metrics)

    concall = payload.get("concall")
    concall_html = _concall_to_html(concall)
    concall_section_title = "Concall Evaluation"
    if isinstance(concall, dict) and concall.get("sectionTitle"):
        concall_section_title = str(concall["sectionTitle"])

    sectoral_analysis = sectoral.get("analysis") or ""
    if sectoral.get("headwinds") or sectoral.get("tailwinds"):
        lines = [sectoral_analysis] if sectoral_analysis else []
        if sectoral.get("headwinds"):
            lines.append("<strong>Headwinds:</strong> " + "; ".join(sectoral["headwinds"]))
        if sectoral.get("tailwinds"):
            lines.append("<strong>Tailwinds:</strong> " + "; ".join(sectoral["tailwinds"]))
        sectoral_analysis = "<p>".join(lines)

    generated_at = payload.get("generated_at") or ""
    if not isinstance(generated_at, str):
        generated_at = str(generated_at)
    generated_at = generated_at.replace("T", " ").replace("Z", "")[:16]

    return {
        "print_only": True,
        "symbol": meta.get("symbol", ""),
        "exchange": meta.get("exchange", "NSE"),
        "company_name": meta.get("company_name", meta.get("symbol", "")),
        "generated_at": generated_at,
        "executive_summary": _text_to_html(payload.get("executive_summary") or ""),
        "company_overview": _text_to_html(payload.get("company_overview") or ""),
        "management_research": _text_to_html(payload.get("management_research") or ""),
        "financial_risk": _text_to_html(payload.get("financial_risk") or ""),
        "auditor_flags": payload.get("auditor_flags") if payload.get("auditor_flags") else None,
        "financial_ratios": financials.get("ratios") or [],
        "yearly_table": yearly_table,
        "qoq_highlights": highlights,
        "concall_evaluation": concall_html or "<p>No concall data.</p>",
        "concall_section_title": concall_section_title,
        "sectoral_analysis": _text_to_html(sectoral_analysis) if sectoral_analysis else "<p>—</p>",
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

    # ---- Title block (accent bar) ----
    company_name = (ctx.get("company_name") or "").replace("&", "&amp;")
    symbol = (ctx.get("symbol") or "").replace("&", "&amp;")
    meta_line = f"{ctx.get('exchange', 'NSE')} · Generated {ctx.get('generated_at', '')}"
    title_table = Table([
        [Paragraph(f'<b><font size="14">{company_name}</font></b> &nbsp; <font size="11" color="#ffffff">({symbol})</font>')],
        [Paragraph(f'<font size="9">{meta_line}</font>')],
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
    flow.append(Spacer(1, 20))

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

    # ---- Key ratios (teal header, zebra rows) ----
    if ctx.get("financial_ratios"):
        flow.append(Paragraph("Key ratios", heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), teal),
        ])))
        flow.append(Spacer(1, 8))
        data = [["Metric", "Value", "Period"]]
        for r in ctx["financial_ratios"]:
            data.append([str(r.get("metric", "")), str(r.get("value", "")), str(r.get("period", ""))])
        t = Table(data, colWidths=[6 * cm, 4 * cm, 6 * cm])
        st = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), teal),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e5e4")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
        for i in range(1, len(data)):
            if i % 2 == 0:
                st.add("BACKGROUND", (0, i), (-1, i), colors.HexColor(_surface2))
        t.setStyle(st)
        flow.append(t)
        flow.append(Spacer(1, 16))

    # ---- Yearly table (teal header, colored YoY %) ----
    if ctx.get("yearly_table") and ctx["yearly_table"].get("headers"):
        flow.append(Paragraph("Yearly trends + TTM", heading_style))
        flow.append(Table([[""]], colWidths=[16 * cm], rowHeights=[2]).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), teal),
        ])))
        flow.append(Spacer(1, 8))
        intro = Paragraph(
            '<font size="9" color="#78716c">Annual figures and TTM. Values in Crores unless noted. YoY % change highlighted.</font>',
            body_style,
        )
        flow.append(intro)
        flow.append(Spacer(1, 6))
        headers = ["Metric"] + list(ctx["yearly_table"]["headers"])
        data = [headers]
        for row in ctx["yearly_table"].get("rows", []):
            cells = [row.get("metric", "")]
            for c in row.get("cells", []):
                v = c.get("value_display", "")
                pct = c.get("qoq_pct")
                if pct is not None:
                    color = _green if pct >= 0 else _red
                    cells.append(Paragraph(
                        f'<font size="8">{v}</font><br/><font size="7" color="{color}">({pct:+.1f}%)</font>',
                        ParagraphStyle(name="Cell", fontSize=8),
                    ))
                else:
                    cells.append(Paragraph(f'<font size="8">{v}</font>', ParagraphStyle(name="Cell", fontSize=8)))
            data.append(cells)
        col_count = len(headers)
        col_width = 16.0 * cm / col_count
        t = Table(data, colWidths=[3.5 * cm] + [col_width] * (col_count - 1))
        st = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), teal),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor(_surface)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e7e5e4")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ])
        for i in range(1, len(data)):
            if i % 2 == 0:
                st.add("BACKGROUND", (1, i), (-1, i), colors.HexColor(_surface2))
        t.setStyle(st)
        flow.append(t)
        flow.append(Spacer(1, 12))

        # Strengths / Concerns boxes
        highlights = ctx.get("qoq_highlights") or {}
        if isinstance(highlights, dict):
            for box_title, color_hex, bg_hex in [
                ("Strengths (TTM & balance sheet)", _green, _green_light),
                ("Concerns (TTM & balance sheet)", _red, _red_light),
            ]:
                points = highlights.get("good" if "Strengths" in box_title else "bad") or []
                if not points:
                    continue
                content = "<br/>".join("• " + str(p).replace("&", "&amp;") for p in points[:8])
                box = Table([
                    [Paragraph(f'<b><font color="{color_hex}" size="10">{box_title.replace("&", "&amp;")}</font></b>')],
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
