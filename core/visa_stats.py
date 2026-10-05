"""Official 2025 Schengen figures and the rates derived from them.

Refusal rate uses the Commission's formula: refused / (issued + refused).
Consulate rates are the published percentages, not recomputed.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from .models import ConsulateVisaStat, Country, CountryVisaStat, StatsDataset

SOURCE_DISCLAIMER = "Official EU statistics — not a prediction for your application."
CITIES = ("Istanbul", "Ankara", "Izmir", "Edirne", "Bursa")
_STICKERS = ("s-navy", "s-teal", "s-amber", "s-rose")


def refusal_rate(issued, refused):
    """Percent refused among decisions, rounded to one decimal. None if empty."""
    decided = (issued or 0) + (refused or 0)
    if decided <= 0:
        return None
    percent = (Decimal(refused) / Decimal(decided)) * Decimal(100)
    return percent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def multiple_entry_share(multiple_entry, issued):
    """Percent of issued visas that were multiple-entry, rounded to one decimal."""
    if not issued:
        return None
    percent = (Decimal(multiple_entry) / Decimal(issued)) * Decimal(100)
    return percent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def rate_band(rate):
    """Bar colour: reject at 20% and above, amber from 10%, approve below 10%."""
    if rate >= 20:
        return "reject"
    if rate >= 10:
        return "amber"
    return "approve"


def rate_label(rate):
    if rate is None:
        return "—"
    return f"{rate:.1f}"


def count_label(value):
    return f"{value:,}"


def sticker_class(code):
    return _STICKERS[sum(ord(char) for char in code) % len(_STICKERS)]


def latest_dataset():
    return StatsDataset.objects.order_by("-year").first()


def dataset_totals(dataset):
    totals = dataset.country_stats.aggregate(
        applications=Sum("applications"),
        issued=Sum("issued"),
        refused=Sum("refused"),
        multiple_entry=Sum("multiple_entry"),
    )
    totals["refusal_rate"] = refusal_rate(totals["issued"], totals["refused"])
    totals["multiple_entry_share"] = multiple_entry_share(
        totals["multiple_entry"], totals["issued"]
    )
    for key in ("applications", "issued", "refused", "multiple_entry"):
        totals[key] = totals[key] or 0
        totals[f"{key}_label"] = count_label(totals[key])
    return totals


def _country_lookup(codes):
    return {
        country.code: country
        for country in Country.objects.filter(code__in=codes, is_active=True)
    }


def country_stat_rows(dataset, sort="rate"):
    stats = list(dataset.country_stats.all())
    countries = _country_lookup([stat.country_code for stat in stats])
    rows = []
    for stat in stats:
        rate = refusal_rate(stat.issued, stat.refused)
        share = multiple_entry_share(stat.multiple_entry, stat.issued)
        country = countries.get(stat.country_code)
        rows.append(
            {
                "code": stat.country_code,
                "name": stat.country_name,
                "slug": country.slug if country else "",
                "sticker_class": sticker_class(stat.country_code),
                "applications": stat.applications,
                "applications_label": count_label(stat.applications),
                "issued": stat.issued,
                "issued_label": count_label(stat.issued),
                "multiple_entry": stat.multiple_entry,
                "multiple_entry_label": count_label(stat.multiple_entry),
                "refused": stat.refused,
                "rate": rate,
                "rate_label": rate_label(rate),
                "share": share,
                "share_label": rate_label(share),
                "band": rate_band(rate) if rate is not None else "approve",
                "bar_width": f"{rate:.1f}" if rate is not None else "0",
                "share_width": f"{share:.1f}" if share is not None else "0",
            }
        )
    if sort == "applications":
        rows.sort(key=lambda row: row["applications"], reverse=True)
    else:
        rows.sort(key=lambda row: row["rate"] if row["rate"] is not None else Decimal(0), reverse=True)
    return rows


def consulate_rows(dataset, city=""):
    stats = dataset.consulate_stats.all()
    if city in CITIES:
        stats = stats.filter(city=city)
    stats = list(stats)
    countries = _country_lookup([stat.country_code for stat in stats])
    rows = []
    for stat in stats:
        country = countries.get(stat.country_code)
        rate = stat.refusal_rate
        rows.append(
            {
                "code": stat.country_code,
                "name": stat.country_name,
                "city": stat.city,
                "slug": country.slug if country else "",
                "sticker_class": sticker_class(stat.country_code),
                "applications": stat.applications,
                "applications_label": count_label(stat.applications),
                "rate": rate,
                "rate_label": rate_label(rate),
                "band": rate_band(rate),
                "bar_width": f"{rate:.1f}",
            }
        )
    by_rate = sorted(rows, key=lambda row: row["rate"], reverse=True)
    highest = by_rate[:15]
    if len(rows) <= 15:
        lowest = []
    else:
        shown = {(row["code"], row["city"]) for row in highest}
        lowest = [
            row
            for row in sorted(rows, key=lambda row: row["rate"])
            if (row["code"], row["city"]) not in shown
        ][:15]
    return highest, lowest


def largest_city_gap(dataset):
    """The country whose consulates differ the most, with both cities."""
    grouped = {}
    for stat in dataset.consulate_stats.all():
        grouped.setdefault(stat.country_code, []).append(stat)
    best = None
    for stats in grouped.values():
        if len(stats) < 2:
            continue
        low = min(stats, key=lambda stat: stat.refusal_rate)
        high = max(stats, key=lambda stat: stat.refusal_rate)
        gap = high.refusal_rate - low.refusal_rate
        if best is None or gap > best["gap"]:
            best = {
                "country_name": high.country_name,
                "low_city": low.city,
                "low_rate": rate_label(low.refusal_rate),
                "high_city": high.city,
                "high_rate": rate_label(high.refusal_rate),
                "gap": gap,
            }
    return best


def city_gap_sentence(gap):
    if gap is None:
        return ""
    return (
        f"The same country can differ a lot between cities — e.g. {gap['country_name']}: "
        f"{gap['low_city']} {gap['low_rate']}% vs {gap['high_city']} {gap['high_rate']}%."
    )


def official_snapshot(country):
    """Sidebar card for one country. None when that country has no 2025 row."""
    dataset = latest_dataset()
    if dataset is None or not country.code:
        return None
    stat = CountryVisaStat.objects.filter(dataset=dataset, country_code=country.code).first()
    if stat is None:
        return None
    consulates = [
        {
            "city": row.city,
            "rate_label": rate_label(row.refusal_rate),
            "applications_label": count_label(row.applications),
        }
        for row in ConsulateVisaStat.objects.filter(
            dataset=dataset, country_code=country.code
        ).order_by("-refusal_rate")
    ]
    rate = refusal_rate(stat.issued, stat.refused)
    return {
        "rate_label": rate_label(rate),
        "applications_label": count_label(stat.applications),
        "consulates": consulates,
        "year": dataset.year,
    }


def lowest_refusal_countries(dataset, limit=5):
    rows = country_stat_rows(dataset, sort="rate")
    ranked = sorted(
        (row for row in rows if row["rate"] is not None),
        key=lambda row: row["rate"],
    )
    return ranked[:limit]
