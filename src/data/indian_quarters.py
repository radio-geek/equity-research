"""Indian financial year quarter utilities (FY: April–March)."""

from __future__ import annotations

from datetime import datetime
def get_current_indian_quarter(as_of: datetime | None = None) -> tuple[int, int]:
    """Return (quarter 1–4, fy_year) for the given date.

    Indian FY: Q1 Apr–Jun, Q2 Jul–Sep, Q3 Oct–Dec, Q4 Jan–Mar.
    Jan–Mar → Q4 FY(calendar_year); Apr–Dec → Q1–Q3 FY(calendar_year+1).
    fy_year is 2-digit (e.g. 26 for FY26 = Apr 2025–Mar 2026).
    """
    dt = as_of or datetime.now()
    month = dt.month
    year = dt.year
    if 1 <= month <= 3:
        return (4, year % 100)
    if 4 <= month <= 6:
        return (1, (year % 100) + 1)
    if 7 <= month <= 9:
        return (2, (year % 100) + 1)
    return (3, (year % 100) + 1)


def _quarter_to_period_key_and_label(q: int, fy: int) -> tuple[str, str]:
    """Return (period_key e.g. '2025-06-30', label e.g. 'Q1 FY26') for (q, fy)."""
    full_year = 2000 + (fy % 100)
    prev_year = full_year - 1
    if q == 1:
        return (f"{prev_year}-06-30", f"Q1 FY{fy}")
    if q == 2:
        return (f"{prev_year}-09-30", f"Q2 FY{fy}")
    if q == 3:
        return (f"{prev_year}-12-31", f"Q3 FY{fy}")
    return (f"{full_year}-03-31", f"Q4 FY{fy}")


def _prev_quarter(q: int, fy: int) -> tuple[int, int]:
    """Return (quarter, fy) for the previous quarter."""
    if q >= 2:
        return (q - 1, fy)
    return (4, fy - 1)


def get_last_n_quarters(
    n: int, as_of: datetime | None = None
) -> list[tuple[str, str]]:
    """Return up to n quarters as [(period_key, label), ...] in chronological order (oldest first).

    period_key is period-end date string (e.g. '2025-06-30'); label is e.g. 'Q1 FY26'.
    """
    if n <= 0:
        return []
    q, fy = get_current_indian_quarter(as_of)
    # Collect backwards: current, then previous (n-1) times
    pairs: list[tuple[int, int]] = []
    for _ in range(n):
        pairs.append((q, fy))
        q, fy = _prev_quarter(q, fy)
    # Reverse so oldest first, then map to (period_key, label)
    pairs.reverse()
    return [_quarter_to_period_key_and_label(qq, ff) for qq, ff in pairs]


def calendar_date_to_indian_quarter(d: datetime | None = None) -> str:
    """Map a period-end date to Indian quarter label (e.g. Jun 30 → 'Q1 FY26').

    Uses month/day: Jun(6) → Q1, Sep(9) → Q2, Dec(12) → Q3, Mar(3) → Q4.
    FY from year: Jan–Mar use calendar year; Apr–Dec use calendar year + 1 for FY.
    """
    if d is None:
        d = datetime.now()
    month = d.month
    year = d.year
    if month == 3:
        return f"Q4 FY{year % 100}"
    if month == 6:
        return f"Q1 FY{(year % 100) + 1}"
    if month == 9:
        return f"Q2 FY{(year % 100) + 1}"
    if month == 12:
        return f"Q3 FY{(year % 100) + 1}"
    # Non quarter-end: treat as current quarter
    q, fy = get_current_indian_quarter(d)
    return _quarter_to_period_key_and_label(q, fy)[1]
