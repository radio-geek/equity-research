"""Server-side chart rendering for reports (YoY metrics)."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

# 1 Crore = 10^7 (for P&L values in INR)
CRORE = 1e7

# (data_key, label, in_crores) — ROCE removed per requirement
_METRICS = (
    ("revenue", "Revenue (Cr)", True),
    ("net_income", "PAT (Cr)", True),
    ("ebitda", "EBITDA (Cr)", True),
    ("roe", "ROE (%)", False),
    ("debt_equity", "Debt/Equity", False),
)
_YOY_KEYS = {
    "revenue": "revenue_yoy_pct",
    "net_income": "pat_yoy_pct",
    "ebitda": "ebitda_yoy_pct",
    "roe": "roe_yoy_pct",
    "debt_equity": "debt_equity_yoy_pct",
}


def _to_crores(value: float | None) -> float | None:
    """Convert absolute value to Crores (divide by 10^7)."""
    if value is None:
        return None
    return round(value / CRORE, 2)


def yoy_metrics_to_chart_data(yoy_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Build chart data: periods and per-metric value series (Crores for P&L) plus YoY %."""
    if not yoy_metrics:
        return {"periods": [], "metrics": []}
    periods = [m.get("period", "") for m in yoy_metrics]
    metrics: list[dict[str, Any]] = []
    for key, label, in_crores in _METRICS:
        if in_crores:
            values = [_to_crores(m.get(key)) for m in yoy_metrics]
        else:
            values = [m.get(key) for m in yoy_metrics]
        yoy_key = _YOY_KEYS.get(key, key + "_yoy_pct")
        yoy_values = [m.get(yoy_key) for m in yoy_metrics]
        metrics.append({
            "label": label,
            "values": values,
            "yoy_pct": yoy_values,
            "in_crores": in_crores,
        })
    return {"periods": periods, "metrics": metrics}


def render_yoy_chart(chart_data: dict[str, Any]) -> bytes:
    """Build one matplotlib figure: 5 line charts (2x3 grid, last empty) with clear styling."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    periods = chart_data.get("periods") or []
    metrics = chart_data.get("metrics") or []
    if not periods or not metrics:
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center", fontsize=11)
        ax.axis("off")
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    # Investor-friendly: 2x3 grid, 5 metrics (Revenue, PAT, EBITDA, ROE, D/E)
    fig, axes = plt.subplots(2, 3, figsize=(10, 6.5), facecolor="#fafafa")
    axes_flat = list(axes.flatten())
    x = list(range(len(periods)))
    color_line = "#1a5f7a"
    color_positive = "#0d8050"
    color_negative = "#c23030"

    for idx, m in enumerate(metrics):
        ax = axes_flat[idx]
        ax.set_facecolor("white")
        values = m.get("values") or []
        yoy_pct = m.get("yoy_pct") or []
        label = m.get("label", "")

        valid_x = [i for i, v in enumerate(values) if v is not None]
        valid_y = [values[i] for i in valid_x]
        if not valid_x:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, fontsize=10)
            ax.set_xticks(x)
            ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=9)
            ax.set_title(label, fontsize=11, fontweight="600")
            continue

        ax.plot(valid_x, valid_y, color=color_line, linewidth=2.2, marker="o", markersize=7, markeredgecolor="white", markeredgewidth=1.2, label=label, zorder=3)
        for i, xi in enumerate(valid_x):
            if xi < len(yoy_pct) and yoy_pct[xi] is not None:
                y_val = valid_y[i]
                color = color_positive if yoy_pct[xi] >= 0 else color_negative
                ax.annotate(
                    f"{yoy_pct[xi]:+.1f}%",
                    (xi, y_val),
                    textcoords="offset points",
                    xytext=(0, 11),
                    ha="center",
                    fontsize=8,
                    fontweight="500",
                    color=color,
                )
        ax.set_xticks(x)
        ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel(label.split(" ")[0], fontsize=10)
        ax.set_title(label, fontsize=11, fontweight="600")
        ax.legend(loc="upper left", fontsize=9, framealpha=0.95)
        ax.grid(True, alpha=0.25, linestyle="-")
        ax.tick_params(axis="both", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes_flat[-1].axis("off")
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_yoy_charts(yoy_metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return list of { title, image_base64 } for report template. Empty if no data."""
    if not yoy_metrics:
        return []
    chart_data = yoy_metrics_to_chart_data(yoy_metrics)
    metrics = chart_data.get("metrics") or []
    has_any = any(
        any(v is not None for v in (m.get("values") or []))
        for m in metrics
    )
    if not chart_data.get("periods") or not has_any:
        return []
    try:
        png_bytes = render_yoy_chart(chart_data)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return [{"title": "Key metrics (Crores / %) with YoY change", "image_base64": b64}]
    except Exception:
        return []


# --- QoQ metrics (last 8 quarters, Indian FY): Debt/Equity, Revenue, CFO, EBITDA, PAT ---
_QOQ_METRICS = (
    ("debt_equity", "Debt/Equity", False),
    ("revenue_cr", "Revenue (Cr)", True),
    ("cfo_cr", "Cash Flow from Operations (Cr)", True),
    ("ebitda_cr", "EBITDA (Cr)", True),
    ("pat_cr", "PAT (Cr)", True),
)
_QOQ_PCT_KEYS = {
    "debt_equity": "debt_equity_qoq_pct",
    "revenue_cr": "revenue_qoq_pct",
    "cfo_cr": "cfo_qoq_pct",
    "ebitda_cr": "ebitda_qoq_pct",
    "pat_cr": "pat_qoq_pct",
}


def qoq_metrics_to_chart_data(qoq_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Build chart data: periods and per-metric value series plus QoQ % for annotations."""
    if not qoq_metrics:
        return {"periods": [], "metrics": []}
    periods = [m.get("period_label", "") for m in qoq_metrics]
    metrics: list[dict[str, Any]] = []
    for key, label, in_crores in _QOQ_METRICS:
        values = [m.get(key) for m in qoq_metrics]
        qoq_key = _QOQ_PCT_KEYS.get(key, key.replace("_cr", "_qoq_pct"))
        qoq_values = [m.get(qoq_key) for m in qoq_metrics]
        metrics.append({
            "label": label,
            "values": values,
            "qoq_pct": qoq_values,
            "in_crores": in_crores,
        })
    return {"periods": periods, "metrics": metrics}


def render_qoq_chart(chart_data: dict[str, Any]) -> bytes:
    """One figure: 5 line charts (2x3 grid, last cell empty) with values in Cr/ratio and QoQ % colored."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    periods = chart_data.get("periods") or []
    metrics = chart_data.get("metrics") or []
    if not periods or not metrics:
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center", fontsize=11)
        ax.axis("off")
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    fig, axes = plt.subplots(2, 3, figsize=(10, 6.5), facecolor="#fafafa")
    axes_flat = list(axes.flatten())
    x = list(range(len(periods)))
    color_line = "#1a5f7a"
    color_positive = "#0d8050"
    color_negative = "#c23030"

    for idx, m in enumerate(metrics):
        ax = axes_flat[idx]
        ax.set_facecolor("white")
        values = m.get("values") or []
        qoq_pct = m.get("qoq_pct") or []
        label = m.get("label", "")

        valid_x = [i for i, v in enumerate(values) if v is not None]
        valid_y = [values[i] for i in valid_x]
        if not valid_x:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, fontsize=10)
            ax.set_xticks(x)
            ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=9)
            ax.set_title(label, fontsize=11, fontweight="600")
            continue

        ax.plot(valid_x, valid_y, color=color_line, linewidth=2.2, marker="o", markersize=7, markeredgecolor="white", markeredgewidth=1.2, zorder=3)
        for i, xi in enumerate(valid_x):
            y_val = valid_y[i]
            # Value label (Cr or ratio)
            if m.get("in_crores"):
                val_str = f"{y_val:.1f}"
            else:
                val_str = f"{y_val:.2f}" if y_val is not None else ""
            ax.annotate(val_str, (xi, y_val), textcoords="offset points", xytext=(0, -14), ha="center", fontsize=8, color="#333")
            # QoQ % colored
            if xi < len(qoq_pct) and qoq_pct[xi] is not None:
                color = color_positive if qoq_pct[xi] >= 0 else color_negative
                ax.annotate(f"{qoq_pct[xi]:+.1f}%", (xi, y_val), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8, fontweight="500", color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel(label.split(" ")[0], fontsize=10)
        ax.set_title(label, fontsize=11, fontweight="600")
        ax.grid(True, alpha=0.25, linestyle="-")
        ax.tick_params(axis="both", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes_flat[-1].axis("off")
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_qoq_charts(qoq_metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return list of { title, image_base64 } for report template. Empty if no data."""
    if not qoq_metrics:
        return []
    chart_data = qoq_metrics_to_chart_data(qoq_metrics)
    metrics = chart_data.get("metrics") or []
    has_any = any(any(v is not None for v in (m.get("values") or [])) for m in metrics)
    if not chart_data.get("periods") or not has_any:
        return []
    try:
        png_bytes = render_qoq_chart(chart_data)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return [{"title": "Quarterly trends (QoQ) – last 8 quarters", "image_base64": b64}]
    except Exception:
        return []


def qoq_metrics_to_table(qoq_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Return table-friendly structure: headers (period labels) and rows (metric name + cells with value, qoq_pct, trend)."""
    if not qoq_metrics:
        return {"headers": [], "rows": []}
    headers = [m.get("period_label", "") for m in qoq_metrics]
    rows: list[dict[str, Any]] = []
    for key, label, in_crores in _QOQ_METRICS:
        qoq_key = _QOQ_PCT_KEYS.get(key, key.replace("_cr", "_qoq_pct"))
        cells: list[dict[str, Any]] = []
        for m in qoq_metrics:
            val = m.get(key)
            pct = m.get(qoq_key)
            if val is not None:
                value_display = f"{val:.2f}" if isinstance(val, float) else str(val)
            else:
                value_display = "—"
            if pct is None:
                trend = "neutral"
            elif pct > 0:
                trend = "positive"
            elif pct < 0:
                trend = "negative"
            else:
                trend = "neutral"
            cells.append({"value_display": value_display, "qoq_pct": pct, "trend": trend})
        rows.append({"metric": label, "cells": cells})
    return {"headers": headers, "rows": rows}


# Yearly + TTM (same metrics, YoY % instead of QoQ)
_YEARLY_METRICS = (
    ("debt_equity", "Debt/Equity", False),
    ("revenue_cr", "Revenue (Cr)", True),
    ("cfo_cr", "Cash Flow from Operations (Cr)", True),
    ("ebitda_cr", "EBITDA (Cr)", True),
    ("pat_cr", "PAT (Cr)", True),
)
_YEARLY_PCT_KEYS = {
    "debt_equity": "debt_equity_yoy_pct",
    "revenue_cr": "revenue_yoy_pct",
    "cfo_cr": "cfo_yoy_pct",
    "ebitda_cr": "ebitda_yoy_pct",
    "pat_cr": "pat_yoy_pct",
}


def yearly_metrics_to_table(yearly_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Return table-friendly structure for yearly + TTM: headers and rows with value_display, yoy_pct, trend."""
    if not yearly_metrics:
        return {"headers": [], "rows": []}
    headers = [m.get("period_label", "") for m in yearly_metrics]
    rows: list[dict[str, Any]] = []
    for key, label, in_crores in _YEARLY_METRICS:
        pct_key = _YEARLY_PCT_KEYS.get(key, key.replace("_cr", "_yoy_pct"))
        cells: list[dict[str, Any]] = []
        for m in yearly_metrics:
            val = m.get(key)
            pct = m.get(pct_key)
            if val is not None:
                value_display = f"{val:.2f}" if isinstance(val, float) else str(val)
            else:
                value_display = "—"
            if pct is None:
                trend = "neutral"
            elif pct > 0:
                trend = "positive"
            elif pct < 0:
                trend = "negative"
            else:
                trend = "neutral"
            cells.append({"value_display": value_display, "qoq_pct": pct, "trend": trend})
        rows.append({"metric": label, "cells": cells})
    return {"headers": headers, "rows": rows}
