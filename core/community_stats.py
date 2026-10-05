"""Appointment figures computed only from posts and opening reports."""

import math
import statistics
from collections import defaultdict

from .models import Comment, Country, OpeningReport


def median_gap_days(dates):
    """Median days between consecutive distinct opening dates, or None."""
    distinct = sorted({day for day in dates if day is not None})
    if len(distinct) < 2:
        return None
    gaps = [(distinct[index] - distinct[index - 1]).days for index in range(1, len(distinct))]
    if any(gap <= 0 for gap in gaps):
        return None
    return max(1, _nearest_day(statistics.median(gaps)))


def median_number(values):
    numbers = [value for value in values if value is not None]
    if not numbers:
        return None
    return _nearest_day(statistics.median(numbers))


def appointment_board():
    """One row per active country, plus the date span of every opening report."""
    openings = defaultdict(list)
    for country_id, opened_on in OpeningReport.objects.values_list("country_id", "opened_on"):
        openings[country_id].append(opened_on)

    waits = defaultdict(list)
    experience_waits = Comment.objects.filter(
        kind=Comment.KIND_EXPERIENCE,
        wait_days__isnull=False,
    ).values_list("country_id", "wait_days")
    for country_id, wait_days in experience_waits:
        waits[country_id].append(wait_days)

    all_dates = [day for dates in openings.values() for day in dates]
    rows = []
    for country in Country.objects.filter(is_active=True).order_by("name"):
        dates = openings.get(country.id, [])
        enough = len(dates) >= 3
        gap = median_gap_days(dates) if enough else None
        rows.append(
            {
                "name": country.name,
                "slug": country.slug,
                "code": country.sticker_code,
                "reports": len(dates),
                "gap_days": gap,
                "enough": gap is not None,
                "wait_days": median_number(waits.get(country.id, [])),
            }
        )

    chart = sorted(
        (row for row in rows if row["enough"]),
        key=lambda row: row["gap_days"],
    )
    longest = chart[-1]["gap_days"] if chart else 0
    for row in chart:
        row["bar_width"] = "100" if longest <= 0 else f"{max(4, round(100 * row['gap_days'] / longest))}"
    waiting = [row for row in rows if not row["enough"]]
    return {
        "chart": chart,
        "waiting": waiting,
        "first_on": min(all_dates) if all_dates else None,
        "last_on": max(all_dates) if all_dates else None,
    }


def _nearest_day(value):
    return int(math.floor(float(value) + 0.5))
