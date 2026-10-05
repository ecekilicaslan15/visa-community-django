import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import ConsulateVisaStat, CountryVisaStat, StatsDataset

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SOURCE_URL = (
    "https://home-affairs.ec.europa.eu/news/"
    "schengen-short-stay-visa-applications-rise-2025-remain-below-pre-pandemic-levels-2026-05-28_en"
)


class Command(BaseCommand):
    help = "Load the 2025 Schengen visa statistics for applications lodged in Türkiye."

    def handle(self, *args, **options):
        dataset, _ = StatsDataset.objects.update_or_create(
            year=2025,
            defaults={
                "title": "Schengen short-stay visa statistics 2025",
                "source_name": "European Commission, DG Migration and Home Affairs",
                "source_url": SOURCE_URL,
                "published_on": date(2026, 5, 28),
                "notes": (
                    "Uniform short-stay (type C) visa applications lodged in Türkiye. "
                    "Türkiye is the 2nd-largest applicant country worldwide, after China."
                ),
            },
        )
        countries = _read(DATA_DIR / "schengen_2025_tr_countries.csv")
        consulates = _read(DATA_DIR / "schengen_2025_tr_consulates.csv")

        country_codes = set()
        for row in countries:
            code = row["country_code"]
            country_codes.add(code)
            CountryVisaStat.objects.update_or_create(
                dataset=dataset,
                country_code=code,
                defaults={
                    "country_name": row["country_name"],
                    "applications": int(row["applications"]),
                    "issued": int(row["issued"]),
                    "multiple_entry": int(row["multiple_entry"]),
                    "refused": int(row["refused"]),
                },
            )
        dataset.country_stats.exclude(country_code__in=country_codes).delete()

        consulate_keys = set()
        for row in consulates:
            key = (row["country_code"], row["city"])
            consulate_keys.add(key)
            ConsulateVisaStat.objects.update_or_create(
                dataset=dataset,
                country_code=row["country_code"],
                city=row["city"],
                defaults={
                    "country_name": row["country_name"],
                    "applications": int(row["applications"]),
                    "refusal_rate": Decimal(row["refusal_rate"]),
                },
            )
        stale = [
            stat.pk
            for stat in dataset.consulate_stats.all()
            if (stat.country_code, stat.city) not in consulate_keys
        ]
        if stale:
            ConsulateVisaStat.objects.filter(pk__in=stale).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(country_codes)} countries and {len(consulate_keys)} consulates for {dataset.year}."
        ))


def _read(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))
