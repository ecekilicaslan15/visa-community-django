from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.names import avatar_class
from core.models import Comment, Country, Reply

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


class ReplyTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            "ayse", "ayse@example.com", PASSWORD, first_name="Ayşe", last_name="Kaya"
        )
        self.other = User.objects.create_user(
            "mehmet", "mehmet@example.com", PASSWORD, first_name="Mehmet", last_name="Demir"
        )
        self.staff = User.objects.create_user(
            "mod", "mod@example.com", PASSWORD, is_staff=True
        )
        self.country = Country.objects.create(name="France", slug="france", code="FR")
        self.question = Comment.objects.create(
            country=self.country,
            user=self.author,
            text="Which documents did they actually check?",
            kind=Comment.KIND_QUESTION,
        )
        self.rejected = Comment.objects.create(
            country=self.country,
            user=self.author,
            text="Refused in Ankara.",
            kind=Comment.KIND_EXPERIENCE,
            outcome=Comment.OUTCOME_REJECTED,
        )

    def _reply(self, comment=None, user=None, text="Take your insurance certificate."):
        return Reply.objects.create(
            comment=comment or self.question,
            user=user or self.other,
            text=text,
        )

    def test_thread_is_public_and_anonymous_users_are_asked_to_sign_in(self):
        self._reply()
        response = self.client.get(reverse("comment_thread", args=[self.question.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Which documents did they actually check?")
        self.assertContains(response, "Take your insurance certificate.")
        self.assertContains(response, "Sign in to reply")
        self.assertContains(response, f"?next=/comments/{self.question.id}/")

    def test_create_reply_is_post_only_and_ignores_forged_author(self):
        url = reverse("create_reply", args=[self.question.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {"text": "hello"})
        self.assertRedirects(response, f"/accounts/login/?next={url}")

        self.client.force_login(self.other)
        response = self.client.post(
            url,
            {"text": "Bring the hotel booking.", "user": self.author.id, "comment": self.rejected.id},
        )
        self.assertRedirects(response, reverse("comment_thread", args=[self.question.id]))
        reply = Reply.objects.get()
        self.assertEqual(reply.user, self.other)
        self.assertEqual(reply.comment, self.question)
        self.assertEqual(reply.text, "Bring the hotel booking.")

    def test_reply_text_is_required_and_capped_at_1000_characters(self):
        self.client.force_login(self.other)
        url = reverse("create_reply", args=[self.question.id])
        response = self.client.post(url, {"text": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertFalse(Reply.objects.exists())

        response = self.client.post(url, {"text": "a" * 1001})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1000")
        self.assertFalse(Reply.objects.exists())

    def test_owner_can_edit_and_others_cannot(self):
        reply = self._reply()
        edit_url = reverse("edit_reply", args=[reply.id])

        self.assertRedirects(
            self.client.get(edit_url),
            f"/accounts/login/?next={edit_url}",
        )
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(self.client.post(edit_url, {"text": "nope"}).status_code, 404)

        self.client.force_login(self.other)
        response = self.client.post(edit_url, {"text": "Updated tip."}, follow=True)
        self.assertContains(response, "Your reply was updated.")
        self.assertContains(response, "Updated tip.")
        reply.refresh_from_db()
        self.assertEqual(reply.text, "Updated tip.")

    def test_delete_is_post_only_owner_or_staff(self):
        reply = self._reply()
        url = reverse("delete_reply", args=[reply.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(
            self.client.post(url),
            f"/accounts/login/?next={url}",
        )

        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Reply.objects.filter(pk=reply.pk).exists())

        self.client.force_login(self.other)
        response = self.client.post(url, {"next": "https://evil.example/phish"})
        self.assertRedirects(response, reverse("comment_thread", args=[self.question.id]))
        self.assertFalse(Reply.objects.filter(pk=reply.pk).exists())

        staff_target = self._reply(text="Spam reply")
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("delete_reply", args=[staff_target.id]),
            follow=True,
        )
        self.assertContains(response, "The reply was deleted.")
        self.assertFalse(Reply.objects.filter(pk=staff_target.pk).exists())

    def test_helpful_toggles_and_skips_your_own_reply(self):
        reply = self._reply()
        url = reverse("toggle_reply_like", args=[reply.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), f"/accounts/login/?next={url}")

        self.client.force_login(self.other)
        self.client.post(url)
        self.assertEqual(reply.likes.count(), 0)

        self.client.force_login(self.author)
        self.client.post(url)
        self.assertEqual(reply.likes.count(), 1)
        self.client.post(url)
        self.assertEqual(reply.likes.count(), 0)

    def test_cards_show_reply_counts_and_encouragement(self):
        response = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(response, "Be the first to answer")
        self.assertNotContains(response, "Community sent encouragement")

        self._reply()
        self._reply(comment=self.rejected, text="Sorry to hear that — the appeal window is short.")
        response = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(response, "1 reply")
        self.assertContains(response, "Last reply")
        self.assertContains(response, "Community sent encouragement")
        self.assertNotContains(response, "Be the first to answer")

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Join the discussion")
        self.assertContains(response, reverse("comment_thread", args=[self.question.id]))

    def test_home_answer_rate_uses_questions_with_a_reply(self):
        self._reply()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "100%")
        self.assertContains(response, "of questions get answers")

        Reply.objects.all().delete()
        Comment.objects.all().delete()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "—")

    def test_unanswered_second_question_lowers_the_rate(self):
        Comment.objects.create(
            country=self.country,
            user=self.author,
            text="Is a cover letter required?",
            kind=Comment.KIND_QUESTION,
        )
        self._reply()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "50%")

    def test_profile_counts_replies_and_awards_community_helper(self):
        self._reply(user=self.other)
        self.client.force_login(self.other)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Replies")
        self.assertContains(response, "1 contribution")
        self.assertContains(response, "New Traveler")
        self.assertContains(response, "View thread")
        self.assertNotContains(response, "🏆 Community Helper")

        for i in range(9):
            Reply.objects.create(
                comment=self.question,
                user=self.other,
                text=f"Another answer {i}",
            )
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "🏆 Community Helper")
        self.assertContains(response, "Frequent Traveler")
        self.assertContains(response, "10 contributions")

    def test_replies_on_experiences_do_not_earn_the_helper_badge(self):
        for i in range(10):
            Reply.objects.create(
                comment=self.rejected,
                user=self.other,
                text=f"Note {i}",
            )
        self.client.force_login(self.other)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Frequent Traveler")
        self.assertNotContains(response, "🏆 Community Helper")

    def test_deleting_a_comment_deletes_its_replies(self):
        reply = self._reply()
        self.question.delete()
        self.assertFalse(Reply.objects.filter(pk=reply.pk).exists())

    def test_country_list_does_not_query_once_per_post(self):
        def queries():
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(reverse("country_detail", args=["france"]))
                self.assertEqual(response.status_code, 200)
            return len(captured)

        baseline = queries()
        for i in range(3):
            comment = Comment.objects.create(
                country=self.country,
                user=self.author,
                text=f"Question {i}",
                kind=Comment.KIND_QUESTION,
            )
            Reply.objects.create(comment=comment, user=self.other, text=f"Answer {i}")
        self.assertEqual(queries(), baseline)

