"""Community estimate of the next appointment-opening window.

The expected date is the latest distinct opening plus the median gap between
consecutive openings. The window is that date plus or minus half the
interquartile range of the gaps, and never narrower than two days on each
side. Fewer than five distinct dates is not an estimate.
"""

import math
from datetime import date, datetime, timedelta
import statistics

# Report count → label and meter fill. Counts below five never reach this.
_CONFIDENCE = (
    (40, "high", 95),
    (20, "medium-high", 80),
    (10, "medium", 60),
    (5, "low", 40),
)
_LOWER = {
    "high": ("medium-high", 80),
    "medium-high": ("medium", 60),
    "medium": ("low", 40),
    "low": ("low", 40),
}


def predict_next_window(dates, today=None):
    """Return the next opening window, or None when there is not enough data.

    ``dates`` is one date per community report. Duplicate dates count toward
    confidence, but only distinct dates form the gaps. ``today`` defaults to
    the real current date so tests can pin the calendar.
    """
    if today is None:
        today = date.today()
    cleaned = [_as_date(value) for value in dates if value is not None]
    distinct = sorted(set(cleaned))
    if len(distinct) < 5:
        return None

    gaps = [(distinct[index] - distinct[index - 1]).days for index in range(1, len(distinct))]
    if any(gap <= 0 for gap in gaps):
        return None
    median_gap = statistics.median(gaps)
    if median_gap <= 0:
        return None

    quartiles = statistics.quantiles(gaps, n=4, method="inclusive")
    iqr = quartiles[2] - quartiles[0]
    gap_days = max(1, _nearest_day(median_gap))
    half_days = max(2, _nearest_day(iqr / 2))
    confidence, meter = _band(len(cleaned))
    if iqr > median_gap:
        confidence, meter = _LOWER[confidence]

    expected = distinct[-1] + timedelta(days=gap_days)
    start, end = _window(expected, half_days)
    steps = 0
    while end < today and steps < 500:
        expected = expected + timedelta(days=gap_days)
        start, end = _window(expected, half_days)
        steps += 1

    return {
        "start": start,
        "end": end,
        "expected": expected,
        "confidence": confidence,
        "meter": meter,
        "reports": len(cleaned),
        "median_gap_days": gap_days,
    }


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _nearest_day(value):
    """Round a positive day count to the nearest day, with halves rounding up."""
    return int(math.floor(value + 0.5))


def _window(expected, half_days):
    half = timedelta(days=half_days)
    return expected - half, expected + half


def _band(count):
    for minimum, name, meter in _CONFIDENCE:
        if count >= minimum:
            return name, meter
    return "low", 40
