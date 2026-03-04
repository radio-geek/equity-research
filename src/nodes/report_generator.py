"""Report generator node: state -> Jinja2 -> WeasyPrint -> PDF."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import get_reports_dir
from src.report.charts import yearly_metrics_to_table
from src.state import ResearchState


def _as_html(text: str) -> str:
    """Pass through if already HTML, otherwise convert plain text."""
    if text.strip().startswith("<"):
        return text
    return _text_to_html(text)


def _text_to_html(text: str) -> str:
    """Convert plain text (with basic markdown) to HTML paragraphs."""
    if not text:
        return ""
    # Strip markdown citation links [label](url) → keep label only
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Escape HTML special chars
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    # Render markdown bold/italic (applied after escaping — safe)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return "<p>" + re.sub(r"\n\n+", "</p><p>", text).replace("\n", "<br>") + "</p>"


def _render_html(state: ResearchState, template_dir: Path, styles_path: Path) -> str:
    """Render state to HTML string using Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader

    symbol = (state.get("symbol") or "unknown").upper()
    exchange = state.get("exchange") or "NSE"
    company_name = state.get("company_name") or symbol
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("base.html")
    return template.render(
        symbol=symbol,
        exchange=exchange,
        company_name=company_name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        executive_summary=_text_to_html(state.get("executive_summary") or ""),
        company_overview=_text_to_html(state.get("company_overview") or ""),
        management_research=_text_to_html(state.get("management_research") or ""),
        financial_risk=_text_to_html(state.get("financial_risk") or ""),
        auditor_flags=_as_html(state.get("auditor_flags") or ""),
        concall_evaluation=_as_html(state.get("concall_evaluation") or ""),
        sectoral_analysis=_text_to_html(state.get("sectoral_analysis") or ""),
        financial_ratios=state.get("financial_ratios") or [],
        yearly_metrics=state.get("yearly_metrics") or [],
        yearly_table=yearly_metrics_to_table(state.get("yearly_metrics") or []),
        qoq_highlights=state.get("qoq_highlights") or {"good": [], "bad": []},
    )


def report_generator(state: ResearchState) -> dict[str, Any]:
    """Render state to PDF (or HTML if WeasyPrint unavailable) under reports/; return {report_path}."""
    reports_dir = get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    template_dir = Path(__file__).resolve().parent.parent / "report" / "templates"
    styles_path = Path(__file__).resolve().parent.parent / "report" / "styles.css"
    html_content = _render_html(state, template_dir, styles_path)

    symbol = (state.get("symbol") or "unknown").upper()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        from weasyprint import HTML, CSS

        out_name = f"{symbol}_{timestamp}.pdf"
        out_path = reports_dir / out_name
        html_doc = HTML(string=html_content, base_url=str(template_dir))
        css = CSS(filename=str(styles_path))
        html_doc.write_pdf(out_path, stylesheets=[css])
        return {"report_path": str(out_path)}
    except OSError:
        out_name = f"{symbol}_{timestamp}.html"
        out_path = reports_dir / out_name
        if styles_path.exists():
            css_content = styles_path.read_text(encoding="utf-8")
            html_content = html_content.replace(
                "</head>", f"<style>\n{css_content}\n</style>\n</head>"
            )
        out_path.write_text(html_content, encoding="utf-8")
        print(
            "WeasyPrint system libraries (e.g. Pango) not available; report saved as HTML. "
            "Install them for PDF: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        )
        return {"report_path": str(out_path)}
