import json
import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.tests import PASSWORD, NEW_PASSWORD, signup_data
from core.models import Comment, Country, OpeningReport, Reply

User = get_user_model()


def _uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VerificationTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name="France", slug="france", code="FR")

    def _signup(self):
        self.client.post(reverse("accounts:signup"), signup_data(), follow=True)
        return User.objects.get(username="ayse")

    def test_signup_requires_the_privacy_notice(self):
        data = signup_data()
        del data["privacy_accepted"]
        response = self.client.post(reverse("accounts:signup"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please read and accept the Privacy Notice.")
        self.assertContains(response, "KVKK Aydınlatma Metni")
        self.assertFalse(User.objects.filter(username="ayse").exists())

    def test_unverified_user_cannot_post_reply_or_report_an_opening(self):
        user = self._signup()
        self.assertTrue(user.is_active)
        self.assertFalse(user.profile.email_verified)
        self.assertIsNotNone(user.profile.consent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Confirm your VisaCommunity email")
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")

        home = self.client.get(reverse("home"))
        self.assertContains(home, "Please confirm your email")
        self.assertContains(home, "Resend email")

        response = self.client.post(
            reverse("country_detail", args=["france"]),
            {"kind": "question", "text": "Which documents did they check?"},
        )
        self.assertContains(response, "Please confirm your email before posting.")
        self.assertFalse(Comment.objects.filter(user=user).exists())

        comment = Comment.objects.create(
            country=self.country,
            user=User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD),
            text="Approved in Ankara.",
            kind=Comment.KIND_EXPERIENCE,
        )
        response = self.client.post(
            reverse("create_reply", args=[comment.id]),
            {"text": "Thanks for the note."},
        )
        self.assertContains(response, "Please confirm your email before posting.")
        self.assertFalse(Reply.objects.filter(user=user).exists())

        response = self.client.post(
            reverse("report_opening", args=["france"]),
            {"opened_on": timezone.localdate().isoformat()},
            follow=True,
        )
        self.assertContains(response, "Please confirm your email before posting.")
        self.assertFalse(OpeningReport.objects.filter(user=user).exists())

    def test_verification_link_activates_the_account(self):
        user = self._signup()
        match = re.search(r"https?://[^/]+(/accounts/verify/\S+)", mail.outbox[0].body)
        self.assertIsNotNone(match)
        response = self.client.get(match.group(1), follow=True)
        self.assertContains(response, "Your email is confirmed.")
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)

        response = self.client.post(
            reverse("country_detail", args=["france"]),
            {"kind": "question", "text": "Which documents did they check?"},
            follow=True,
        )
        self.assertContains(response, "your post is live")
        self.assertTrue(Comment.objects.filter(user=user).exists())

    def test_invalid_and_expired_links_fail_gracefully(self):
        user = self._signup()
        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"uidb64": _uid(user), "token": "not-a-token"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This confirmation link isn")
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)

        now = default_token_generator._num_seconds(datetime.now())
        old = now - (60 * 60 * 24 * 3) - 10
        token = default_token_generator._make_token_with_timestamp(
            user, old, default_token_generator.secret
        )
        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"uidb64": _uid(user), "token": token},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This confirmation link isn")
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)

    def test_resend_is_post_only_and_stops_after_three_an_hour(self):
        self._signup()
        url = reverse("accounts:resend_verification")
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(3):
            self.client.post(url)
        self.assertEqual(len(mail.outbox), 4)
        response = self.client.post(url, follow=True)
        self.assertContains(response, "3 times an hour")
        self.assertEqual(len(mail.outbox), 4)

    def test_changing_email_asks_for_confirmation_again(self):
        user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        self.assertTrue(user.profile.email_verified)
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "first_name": "Ayşe",
                "last_name": "Kaya",
                "email": "ayse.new@example.com",
            },
            follow=True,
        )
        self.assertContains(response, "Please confirm your new email.")
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)
        self.assertEqual(len(mail.outbox), 1)


class LockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        self.other = User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD)

    def test_axes_locks_the_username_and_ip_after_five_failures(self):
        login = reverse("login")
        for _ in range(4):
            response = self.client.post(
                login, {"username": "ayse", "password": "wrong-password"}
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            login, {"username": "ayse", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(
            response, "Too many sign-in attempts", status_code=429
        )

        response = self.client.post(
            login, {"username": "ayse", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(
            login, {"username": "mehmet", "password": PASSWORD}
        )
        self.assertRedirects(response, "/")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetThrottleTests(TestCase):
    def test_reset_requests_stop_after_five_in_thirty_minutes(self):
        User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        url = reverse("password_reset")
        for _ in range(5):
            self.client.post(url, {"email": "ayse@example.com"})
        self.assertEqual(len(mail.outbox), 5)
        response = self.client.post(url, {"email": "ayse@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many reset requests")
        self.assertEqual(len(mail.outbox), 5)


class DataExportTests(TestCase):
    def test_export_contains_only_the_requesting_users_data(self):
        ayse = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        mehmet = User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD)
        country = Country.objects.create(name="France", slug="france", code="FR")
        Comment.objects.create(
            country=country,
            user=ayse,
            text="How long did the France appointment take?",
            kind=Comment.KIND_QUESTION,
        )
        Comment.objects.create(
            country=country,
            user=mehmet,
            text="Mehmet private note about nine weeks.",
            kind=Comment.KIND_EXPERIENCE,
        )
        self.client.force_login(ayse)
        response = self.client.get(reverse("accounts:download_data"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("visacommunity-data.json", response["Content-Disposition"])
        payload = json.loads(response.content)
        self.assertEqual(payload["account"]["email"], "ayse@example.com")
        self.assertIn("How long did the France appointment take?", response.content.decode())
        self.assertNotIn("Mehmet private note", response.content.decode())
        self.assertNotIn("mehmet@example.com", response.content.decode())

        self.client.logout()
        response = self.client.get(reverse("accounts:download_data"))
        self.assertRedirects(
            response,
            "/accounts/login/?next=" + reverse("accounts:download_data"),
        )


class SessionSafetyTests(TestCase):
    def test_password_change_keeps_this_session_and_logs_out_the_other(self):
        user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        other = Client()
        self.client.force_login(user)
        other.force_login(user)
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
            follow=True,
        )
        self.assertContains(response, "Your password was changed.")
        self.assertEqual(self.client.get(reverse("accounts:settings")).status_code, 200)
        settings_url = reverse("accounts:settings")
        self.assertRedirects(
            other.get(settings_url),
            f"/accounts/login/?next={settings_url}",
        )

    def test_remember_me_unchecked_ends_when_the_browser_closes(self):
        User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        login = reverse("login")
        self.client.post(login, {"username": "ayse", "password": PASSWORD})
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.logout()
        self.client.post(
            login,
            {"username": "ayse", "password": PASSWORD, "remember_me": "on"},
        )
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 14)
