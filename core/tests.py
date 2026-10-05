from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.names import avatar_class
from core.models import Comment, Country

User = get_user_model()
PASSWORD = "Traveler-pass-2026"


class DisplayNameTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "ayse",
            "ayse@example.com",
            PASSWORD,
            first_name="Ayşe",
            last_name="Kaya",
        )
        self.country = Country.objects.create(name="France", slug="france", code="FR")
        Comment.objects.create(
            country=self.country,
            user=self.user,
            text="Has anyone applied in Istanbul this month?",
            kind=Comment.KIND_QUESTION,
        )

    def test_country_page_shows_display_name_and_avatar(self):
        response = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(response, "Ayşe K.")
        self.assertContains(response, ">AK<")
        self.assertContains(response, f'class="avatar {avatar_class(self.user)}"')
        self.assertNotContains(response, ">ayse<")

    def test_profile_links_to_settings_and_uses_display_name(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Ayşe K.")
        self.assertContains(response, reverse("accounts:settings"))
        self.assertContains(response, f'class="avatar {avatar_class(self.user)}"')
