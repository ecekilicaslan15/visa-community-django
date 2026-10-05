import re

from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.names import avatar_class, display_name, initials
from core.models import Comment, Country

User = get_user_model()
PASSWORD = "Traveler-pass-2026"
NEW_PASSWORD = "Updated-pass-2026"


def signup_data(**overrides):
    data = {
        "username": "ayse",
        "email": "ayse@example.com",
        "first_name": "Ayşe",
        "last_name": "Kaya",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class DisplayNameTests(TestCase):
    def test_first_name_and_last_initial(self):
        user = User(username="ayse", first_name="Ayşe", last_name="Kaya")
        self.assertEqual(display_name(user), "Ayşe K.")
        self.assertEqual(initials(user), "AK")

    def test_falls_back_to_username_when_a_name_part_is_missing(self):
        user = User(username="ayse", first_name="Ayşe", last_name="")
        self.assertEqual(display_name(user), "ayse")
        self.assertEqual(initials(user), "AY")

    def test_avatar_class_is_stable_for_the_user_id(self):
        user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        self.assertEqual(avatar_class(user), ("", "a2", "a3", "a4")[user.pk % 4])
        self.assertEqual(avatar_class(user), avatar_class(user))


class SignUpTests(TestCase):
    def test_signup_logs_in_and_welcomes_by_display_name(self):
        response = self.client.post(reverse("accounts:signup"), signup_data(), follow=True)
        self.assertContains(response, "Welcome aboard, Ayşe K.!")
        user = User.objects.get(username="ayse")
        self.assertEqual(user.email, "ayse@example.com")
        self.assertEqual(user.first_name, "Ayşe")
        self.assertEqual(user.last_name, "Kaya")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.pk, user.pk)

    def test_names_are_optional_and_welcome_uses_the_username(self):
        data = signup_data(first_name="", last_name="")
        response = self.client.post(reverse("accounts:signup"), data, follow=True)
        self.assertContains(response, "Welcome aboard, ayse!")
        user = User.objects.get(username="ayse")
        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")

    def test_email_is_required(self):
        response = self.client.post(reverse("accounts:signup"), signup_data(email=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="ayse").exists())
        self.assertContains(response, "This field is required")

    def test_email_is_unique_regardless_of_case(self):
        User.objects.create_user("taken", "AySe@Example.com", PASSWORD)
        response = self.client.post(
            reverse("accounts:signup"),
            signup_data(username="other", email="ayse@example.com"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertFalse(User.objects.filter(username="other").exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "ayse", "ayse@example.com", PASSWORD, first_name="Ayşe", last_name="Kaya"
        )

    def test_backends_include_email_lookup_and_model_backend(self):
        from django.conf import settings

        self.assertIn(
            "accounts.backends.EmailOrUsernameBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
        self.assertIn(
            "django.contrib.auth.backends.ModelBackend",
            settings.AUTHENTICATION_BACKENDS,
        )

    def test_login_page_offers_email_and_password_reset(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Username or email")
        self.assertContains(response, "Forgot your password?")
        self.assertContains(response, reverse("password_reset"))

    def test_login_with_username(self):
        response = self.client.post(
            reverse("login"),
            {"username": "ayse", "password": PASSWORD},
        )
        self.assertRedirects(response, "/")
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_with_email_is_case_insensitive(self):
        response = self.client.post(
            reverse("login"),
            {"username": "AySe@Example.com", "password": PASSWORD},
        )
        self.assertRedirects(response, "/")

    def test_wrong_password_stays_on_the_form(self):
        response = self.client.post(
            reverse("login"),
            {"username": "ayse@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username or email and password.")
        self.assertIsNone(authenticate(username="ayse@example.com", password="wrong-password"))

    def test_ambiguous_shared_email_does_not_authenticate(self):
        User.objects.create_user("other", "ayse@example.com", PASSWORD)
        self.assertIsNone(authenticate(username="ayse@example.com", password=PASSWORD))
        self.assertIsNotNone(authenticate(username="ayse", password=PASSWORD))
        self.assertIsNotNone(authenticate(username="other", password=PASSWORD))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)

    def test_pages_use_the_auth_design(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "auth-card")
        self.assertContains(response, "Reset your password")
        self.assertNotContains(response, "Django administration")

    def test_reset_email_and_new_password(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "AYSE@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Reset your VisaCommunity password")
        match = re.search(r"https?://[^/]+(/accounts/reset/\S+)", mail.outbox[0].body)
        self.assertIsNotNone(match)

        confirm = self.client.get(match.group(1), follow=True)
        self.assertContains(confirm, "Choose a new password")
        response = self.client.post(
            confirm.request["PATH_INFO"],
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
            follow=True,
        )
        self.assertContains(response, "Password updated")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertContains(response, "Your password was reset. You can sign in now.")

    def test_unknown_email_does_not_send_mail(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "nobody@example.com"},
            follow=True,
        )
        self.assertContains(response, "Check your email")
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_reset_link(self):
        response = self.client.get(
            reverse(
                "password_reset_confirm",
                kwargs={"uidb64": "AAA", "token": "set-password"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This reset link isn't valid")


class AccountSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "ayse", "ayse@example.com", PASSWORD, first_name="Ayşe", last_name="Kaya"
        )
        self.other = User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD)
        self.country = Country.objects.create(name="France", slug="france", code="FR")
        self.comment = Comment.objects.create(
            country=self.country,
            user=self.user,
            text="How long did you wait?",
            kind=Comment.KIND_QUESTION,
        )
        Comment.objects.create(
            country=self.country,
            user=self.other,
            text="About nine days.",
            kind=Comment.KIND_EXPERIENCE,
            outcome=Comment.OUTCOME_APPROVED,
        )

    def test_anonymous_visitors_are_sent_to_login(self):
        settings_url = reverse("accounts:settings")
        response = self.client.get(settings_url)
        self.assertRedirects(response, f"/accounts/login/?next={settings_url}")
        change_url = reverse("password_change")
        response = self.client.post(change_url)
        self.assertRedirects(response, f"/accounts/login/?next={change_url}")

    def test_settings_updates_name_and_email(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "first_name": "Ayşe",
                "last_name": "Yılmaz",
                "email": "AYSE@example.com",
            },
            follow=True,
        )
        self.assertContains(response, "Your profile was updated.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Yılmaz")
        self.assertEqual(self.user.email, "AYSE@example.com")
        self.assertContains(response, "Ayşe Y.")

    def test_cannot_take_another_members_email(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "first_name": "Ayşe",
                "last_name": "Kaya",
                "email": "Mehmet@Example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ayse@example.com")
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, "mehmet@example.com")

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("password_change"))
        self.assertContains(response, "auth-card")
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
        self.assertContains(response, "Password changed")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_get_on_delete_is_not_allowed(self):
        response = self.client.get(reverse("accounts:delete_account"))
        self.assertEqual(response.status_code, 405)
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:delete_account"))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_post_on_delete_redirects_to_login(self):
        url = reverse("accounts:delete_account")
        response = self.client.post(url, {"username": "ayse"})
        self.assertRedirects(response, f"/accounts/login/?next={url}")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_username_does_not_delete_the_account(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"username": "AYSE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Type your username exactly to confirm.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_delete_removes_the_user_and_their_posts_only(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:delete_account"),
            {"username": "ayse"},
            follow=True,
        )
        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "Your account was deleted.")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Comment.objects.filter(user=self.other).exists())

