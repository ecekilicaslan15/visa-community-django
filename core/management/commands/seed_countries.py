from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Country

# Every Schengen country in the 2025 Türkiye statistics, with its sticker code.
SCHENGEN = [
    ("Greece", "GR"),
    ("Germany", "DE"),
    ("France", "FR"),
    ("Netherlands", "NL"),
    ("Bulgaria", "BG"),
    ("Italy", "IT"),
    ("Spain", "ES"),
    ("Denmark", "DK"),
    ("Hungary", "HU"),
    ("Romania", "RO"),
    ("Czechia", "CZ"),
    ("Switzerland", "CH"),
    ("Sweden", "SE"),
    ("Norway", "NO"),
    ("Austria", "AT"),
    ("Belgium", "BE"),
    ("Malta", "MT"),
    ("Poland", "PL"),
    ("Slovenia", "SI"),
    ("Finland", "FI"),
    ("Portugal", "PT"),
    ("Croatia", "HR"),
    ("Luxembourg", "LU"),
    ("Lithuania", "LT"),
    ("Slovakia", "SK"),
    ("Estonia", "EE"),
    ("Latvia", "LV"),
]
DESCRIPTION = "Schengen Area · short-stay (Type C) visa experiences"


class Command(BaseCommand):
    help = "Create the default Schengen countries (safe to run more than once)."

    def handle(self, *args, **options):
        created = updated = 0
        for name, code in SCHENGEN:
            country, was_created = Country.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name, "code": code, "description": DESCRIPTION},
            )
            if was_created:
                created += 1
            elif country.code != code:
                # Keep the existing row, and fill in the Schengen code.
                country.code = code
                country.save(update_fields=["code"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"{created} countries created, {updated} updated with a code."
        ))
