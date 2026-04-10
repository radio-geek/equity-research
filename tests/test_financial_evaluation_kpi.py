"""KPI helpers: TTM vs latest FY when Screener has no TTM column."""
from __future__ import annotations

from src.report.financial_evaluation import build_key_metrics, build_financial_scorecard


def test_build_key_metrics_prefers_ttm_when_present() -> None:
    yearly = [
        {"period_label": "FY23", "revenue_cr": 100.0, "pat_cr": 10.0, "roe": 12.0, "roce": 14.0, "debt_equity": 0.1, "eps": 1.0, "debt_cr": 5.0, "pat_margin_pct": 10.0, "ebitda_margin_pct": 20.0},
        {"period_label": "TTM", "revenue_cr": 120.0, "pat_cr": 15.0, "roe": 18.0, "roce": 20.0, "debt_equity": 0.2, "eps": 1.5, "debt_cr": 6.0, "pat_margin_pct": 12.5, "ebitda_margin_pct": 22.0},
    ]
    km = build_key_metrics(yearly)
    assert km.get("revenue_cr") == "120"
    assert km.get("pat_cr") == "15"
    assert km.get("roe") == "18%"


def test_build_key_metrics_falls_back_to_latest_fy_without_ttm() -> None:
    yearly = [
        {"period_label": "FY23", "revenue_cr": 100.0, "pat_cr": 10.0, "roe": 12.0, "roce": 14.0, "debt_equity": 0.1, "eps": 1.0, "debt_cr": 5.0, "pat_margin_pct": 10.0, "ebitda_margin_pct": 20.0},
        {"period_label": "FY24", "revenue_cr": 110.0, "pat_cr": 12.0, "roe": 15.0, "roce": 17.0, "debt_equity": 0.15, "eps": 1.2, "debt_cr": 5.5, "pat_margin_pct": None, "ebitda_margin_pct": None},
    ]
    km = build_key_metrics(yearly)
    assert km.get("revenue_cr") == "110"
    assert km.get("pat_cr") == "12"
    assert km.get("roe") == "15%"
    assert km.get("pat_margin") == "11%"  # 100 * 12 / 110


def test_build_key_metrics_empty() -> None:
    assert build_key_metrics([]) == {}


def test_scorecard_ocf_uses_latest_fy_when_ttm_row_has_no_cfo() -> None:
    """Screener TTM metric row has cfo_cr None; scorecard must still use latest year CFO."""
    yearly = [
        {"period_label": "FY23", "revenue_cr": 100.0, "pat_cr": 10.0, "revenue_yoy_pct": 5.0, "pat_yoy_pct": 8.0, "roe": 20.0, "debt_equity": 0.1, "cfo_cr": -1.0},
        {
            "period_label": "FY24",
            "revenue_cr": 120.0,
            "pat_cr": 12.0,
            "revenue_yoy_pct": 20.0,
            "pat_yoy_pct": 20.0,
            "roe": 22.0,
            "debt_equity": 0.1,
            "cfo_cr": 25.0,
        },
        {"period_label": "TTM", "revenue_cr": 125.0, "pat_cr": 13.0, "roe": 22.0, "debt_equity": 0.1, "cfo_cr": None},
    ]
    sc = build_financial_scorecard(yearly, [])
    ocf = next(m for m in sc["metrics"] if m["name"] == "Operating Cash Flow")
    assert ocf["passed"] is True
    assert ocf["display_value"] == "Positive"
