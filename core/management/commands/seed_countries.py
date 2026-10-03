from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Country

SCHENGEN = [
    ("France", "FR"), ("Germany", "DE"), ("Netherlands", "NL"), ("Spain", "ES"),
    ("Italy", "IT"), ("Portugal", "PT"), ("Greece", "GR"), ("Czechia", "CZ"),
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
            elif not country.code:
                # Existing country from before the redesign: just fill in its code.
                country.code = code
                country.save(update_fields=["code"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"{created} countries created, {updated} updated with a code."
        ))
