from django.test import TestCase
from django.urls import reverse

from core.models import Country


class GuidePageTests(TestCase):
    def test_guide_pages_and_navigation_links_resolve(self):
        pages = ("guides", "motivation_letter", "sponsorship_letter")
        for name in pages:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "This is general guidance, not legal advice.")
            self.assertNotContains(response, 'method="post"')
            self.assertContains(response, reverse("guides"))
            self.assertContains(response, reverse("motivation_letter"))
            self.assertContains(response, reverse("sponsorship_letter"))

        home = self.client.get(reverse("home"))
        self.assertContains(home, "Guides")
        self.assertContains(home, reverse("motivation_letter"))
        self.assertContains(home, reverse("sponsorship_letter"))

        country = Country.objects.create(name="France", slug="france", code="FR")
        detail = self.client.get(reverse("country_detail", args=[country.slug]))
        self.assertContains(detail, "Need a motivation letter? → Guide")
        self.assertContains(detail, reverse("motivation_letter"))

    def test_motivation_examples_include_english_and_turkish(self):
        response = self.client.get(reverse("motivation_letter"))
        self.assertContains(response, "Application for a short-stay Schengen visa")
        self.assertContains(response, "Seyahatin amacı turizmdir.")
        self.assertContains(response, "Ayşe Yılmaz")
        self.assertContains(response, "Deniz Kaya")
        self.assertContains(response, "Exemple Trade Fair")
        self.assertContains(response, "Emre Demir")
        self.assertContains(response, 'data-lang-panel="en"')
        self.assertContains(response, 'data-lang-panel="tr"')
        self.assertContains(response, "Copy")
        self.assertContains(response, "Print")
        self.assertContains(response, "Nothing you type is sent or saved.")

    def test_sponsorship_examples_cover_parent_spouse_and_company(self):
        response = self.client.get(reverse("sponsorship_letter"))
        self.assertContains(
            response,
            "including travel, accommodation, living expenses, and insurance.",
        )
        self.assertContains(response, "00000000000")
        self.assertContains(response, "Mehmet Kaya")
        self.assertContains(response, "Kerem Yılmaz eşimdir.")
        self.assertContains(response, "Selin Arslan")
        self.assertContains(response, "Authorised signatory")
        self.assertContains(response, "İmza yetkilisi")
        self.assertContains(response, "notarised")
        self.assertContains(response, 'data-lang-panel="tr"')
        self.assertContains(response, "Nothing you type is sent or saved.")
