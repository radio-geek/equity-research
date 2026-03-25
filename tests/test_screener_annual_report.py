"""Table-driven tests: Screener annual report HTML parsing and governance excerpt builder."""
from __future__ import annotations

import pytest

from src.data.screener_annual_report import (
    build_governance_excerpt,
    fetch_latest_annual_report_from_screener,
    parse_annual_report_links_from_html,
)
from src.nodes.schemas import AuditorEvent, AuditorFlagsStructured


def test_parse_annual_reports_empty_html() -> None:
    assert parse_annual_report_links_from_html("<html><body></body></html>") == []


def test_parse_annual_reports_no_section() -> None:
    html = "<html><body><h3>Credit ratings</h3><ul><li><a href='/x'>x</a></li></ul></body></html>"
    assert parse_annual_report_links_from_html(html) == []


def test_parse_annual_reports_single_link() -> None:
    html = """
    <html><body>
    <h3>Annual reports</h3>
    <ul>
    <li><a href="https://www.bseindia.com/x/ar2025.pdf">Financial Year 2025 from bse</a></li>
    </ul>
    </body></html>
    """
    rows = parse_annual_report_links_from_html(html)
    assert len(rows) == 1
    assert rows[0]["year"] == 2025
    assert rows[0]["fy_label"] == "FY25"
    assert rows[0]["url"] == "https://www.bseindia.com/x/ar2025.pdf"


def test_parse_annual_reports_newest_first() -> None:
    html = """
    <html><body>
    <h3>Annual reports</h3>
    <ul>
    <li><a href="https://b.example/a20.pdf">Financial Year 2020 from bse</a></li>
    <li><a href="https://b.example/a25.pdf">Financial Year 2025 from bse</a></li>
    <li><a href="https://b.example/a23.pdf">Financial Year 2023 from bse</a></li>
    </ul>
    </body></html>
    """
    rows = parse_annual_report_links_from_html(html)
    assert [r["year"] for r in rows] == [2025, 2023, 2020]


def test_build_governance_excerpt_keyword_window() -> None:
    filler = "intro " * 200
    core = "The Independent Auditor's Report states a CARO qualification on inventory verification."
    text = filler + core + filler
    ex = build_governance_excerpt(text, max_chars=50_000)
    assert "CARO" in ex or "auditor" in ex.lower()


def test_build_governance_excerpt_empty() -> None:
    assert build_governance_excerpt("") == ""
    assert build_governance_excerpt("   ") == ""


def test_auditor_event_legacy_description_coalesce() -> None:
    ev = AuditorEvent.model_validate({
        "date": "2025-03",
        "fy": "FY25",
        "description": "Legacy line",
        "is_red_flag": True,
    })
    assert ev.issue == "Legacy line"
    assert ev.type == "Other"
    assert ev.signal == "red"


def test_auditor_flags_structured_roundtrip() -> None:
    data = {
        "verdict": "OK",
        "summary": "Test",
        "events": [
            {
                "date": "2025-03",
                "fy": "FY25",
                "category": "Auditor report",
                "type": "CARO",
                "signal": "yellow",
                "issue": "Observation noted",
                "evidence": "Note 5",
                "status": "Pending",
            },
        ],
    }
    m = AuditorFlagsStructured.model_validate(data)
    assert m.verdict == "OK"
    assert m.summary == "Test"
    assert m.events[0].issue == "Observation noted"
    assert m.events[0].signal == "yellow"


def test_fetch_latest_annual_report_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <h3>Annual reports</h3>
    <ul>
    <li><a href="/r.pdf">Financial Year 2024 from bse</a></li>
    </ul>
    """

    def fake_fetch(symbol: str, session=None, timeout=25):
        del symbol, session, timeout
        return parse_annual_report_links_from_html(html)

    monkeypatch.setattr(
        "src.data.screener_annual_report.fetch_annual_report_links_from_screener",
        fake_fetch,
    )
    meta = fetch_latest_annual_report_from_screener("TEST")
    assert meta is not None
    assert meta["fy_label"] == "FY24"
    assert meta["year"] == 2024
