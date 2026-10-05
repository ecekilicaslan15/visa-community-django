from datetime import datetime
from decimal import Decimal

from django.shortcuts import render

from .cascade import GUARANTEE, cascade_eligibility
from .community_stats import appointment_board
from .visa_stats import (
    CITIES,
    SOURCE_DISCLAIMER,
    city_gap_sentence,
    consulate_rows,
    country_stat_rows,
    dataset_totals,
    largest_city_gap,
    latest_dataset,
    lowest_refusal_countries,
)


def stats_overview(request):
    dataset = latest_dataset()
    return render(
        request,
        "core/stats/overview.html",
        {
            "dataset": dataset,
            "totals": dataset_totals(dataset) if dataset else None,
            "disclaimer": SOURCE_DISCLAIMER,
        },
    )


def stats_refusals(request):
    dataset = latest_dataset()
    sort = request.GET.get("sort", "rate")
    if sort not in {"rate", "applications"}:
        sort = "rate"
    city = request.GET.get("city", "")
    if city not in CITIES:
        city = ""
    context = {
        "dataset": dataset,
        "sort": sort,
        "city": city,
        "cities": CITIES,
        "disclaimer": SOURCE_DISCLAIMER,
        "country_rows": [],
        "highest": [],
        "lowest": [],
        "gap_sentence": "",
    }
    if dataset is not None:
        context["country_rows"] = country_stat_rows(dataset, sort=sort)
        context["highest"], context["lowest"] = consulate_rows(dataset, city=city)
        context["gap_sentence"] = city_gap_sentence(largest_city_gap(dataset))
    return render(request, "core/stats/refusals.html", context)


def stats_cascade(request):
    previous = request.GET.get("previous", "")
    expired_raw = request.GET.get("expired_on", "")
    lawful_raw = request.GET.get("lawful", "")
    result = None
    expired_on = None
    date_error = bool(expired_raw) and _parse_date(expired_raw) is None
    if expired_raw and not date_error:
        expired_on = _parse_date(expired_raw)
    if previous:
        if date_error:
            result = {
                "eligible": False,
                "step": None,
                "reason": "Enter a valid expiry date.",
            }
        else:
            lawful = {"yes": True, "no": False}.get(lawful_raw)
            result = cascade_eligibility(previous, expired_on, lawful)
    dataset = latest_dataset()
    share_rows = []
    if dataset is not None:
        share_rows = sorted(
            country_stat_rows(dataset),
            key=lambda row: row["share"] if row["share"] is not None else Decimal("-1"),
            reverse=True,
        )
    return render(
        request,
        "core/stats/cascade.html",
        {
            "previous": previous,
            "expired_on": expired_raw,
            "lawful": lawful_raw,
            "result": result,
            "guarantee": GUARANTEE,
            "disclaimer": SOURCE_DISCLAIMER,
            "dataset": dataset,
            "share_rows": share_rows,
        },
    )


def stats_appointments(request):
    dataset = latest_dataset()
    return render(
        request,
        "core/stats/appointments.html",
        {
            "board": appointment_board(),
            "lowest": lowest_refusal_countries(dataset) if dataset else [],
            "dataset": dataset,
            "disclaimer": SOURCE_DISCLAIMER,
        },
    )


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
