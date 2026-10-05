from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.views.defaults import server_error

from core.models import Comment, ContentReport, Country, OpeningReport, Reply

User = get_user_model()
PASSWORD = "Traveler-pass-2026"


class ModerationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        self.other = User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD)
        self.staff = User.objects.create_user(
            "mod", "mod@example.com", PASSWORD, is_staff=True
        )
        self.country = Country.objects.create(name="France", slug="france", code="FR")
        self.comment = Comment.objects.create(
            country=self.country,
            user=self.author,
            text="Which documents did they actually check?",
            kind=Comment.KIND_QUESTION,
        )
        self.reply = Reply.objects.create(
            comment=self.comment,
            user=self.other,
            text="Take the hotel booking.",
        )

    def test_reports_are_registered_in_the_admin(self):
        self.assertIn(ContentReport, admin.site._registry)

    def test_staff_can_remove_any_comment_and_others_cannot(self):
        url = reverse("delete_comment", args=[self.comment.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), f"/accounts/login/?next={url}")

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
        page = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(page, "Report")
        self.assertNotContains(page, ">Remove<")

        self.client.force_login(self.author)
        page = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(page, ">Delete<")
        self.assertNotContains(page, ">Remove<")
        self.assertNotContains(page, ">Report<")

        self.client.force_login(self.staff)
        page = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(page, ">Remove<")
        response = self.client.post(url, {"next": "https://evil.example/phish"}, follow=True)
        self.assertContains(response, "The post was removed.")
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertFalse(Reply.objects.filter(pk=self.reply.pk).exists())

    def test_staff_remove_is_labelled_on_replies(self):
        self.client.force_login(self.staff)
        page = self.client.get(reverse("comment_thread", args=[self.comment.id]))
        self.assertContains(page, ">Remove<")
        self.assertContains(page, reverse("report_reply", args=[self.reply.id]))

    def test_a_member_can_report_someone_elses_post_once(self):
        url = reverse("report_comment", args=[self.comment.id])
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")
        self.assertRedirects(self.client.post(url, {"reason": "spam"}), f"/accounts/login/?next={url}")

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"reason": "spam"}).status_code, 404)

        self.client.force_login(self.other)
        page = self.client.get(url + "?next=/countries/france/")
        self.assertContains(page, "Spam")
        self.assertContains(page, "Offensive")
        self.assertContains(page, "Personal data")
        self.assertContains(page, "Other")
        self.assertEqual(ContentReport.objects.count(), 0)

        response = self.client.post(url, {"reason": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a reason.")
        self.assertEqual(ContentReport.objects.count(), 0)

        response = self.client.post(
            url,
            {"reason": "personal", "reporter": self.author.id, "comment": 999},
            follow=True,
        )
        self.assertContains(response, "review this report")
        report = ContentReport.objects.get()
        self.assertEqual(report.reporter, self.other)
        self.assertEqual(report.comment, self.comment)
        self.assertIsNone(report.reply)
        self.assertEqual(report.reason, "personal")
        self.assertFalse(report.resolved)

        again = self.client.post(url, {"reason": "spam"}, follow=True)
        self.assertContains(again, "You already reported this.")
        self.assertEqual(ContentReport.objects.count(), 1)
        page = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(page, "Reported")
        self.assertNotContains(page, ">Report<")

    def test_a_reply_report_is_separate_from_the_post(self):
        self.client.force_login(self.author)
        url = reverse("report_reply", args=[self.reply.id])
        self.assertEqual(self.client.get(reverse("report_reply", args=[self.reply.id])).status_code, 200)
        self.client.post(url, {"reason": "offensive"})
        report = ContentReport.objects.get()
        self.assertEqual(report.reply, self.reply)
        self.assertIsNone(report.comment)
        self.client.post(url, {"reason": "spam"})
        self.assertEqual(ContentReport.objects.count(), 1)

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"reason": "spam"}).status_code, 404)

    def test_helpful_returns_json_for_fetch_and_redirects_otherwise(self):
        url = reverse("toggle_like", args=[self.comment.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), f"/accounts/login/?next={url}")

        self.client.force_login(self.other)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"liked": True, "count": 1})
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"liked": False, "count": 0})

        response = self.client.post(url)
        self.assertRedirects(response, "/countries/france/")
        self.assertEqual(self.comment.likes.count(), 1)

        reply_url = reverse("toggle_reply_like", args=[self.reply.id])
        self.client.force_login(self.author)
        response = self.client.post(reply_url, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json(), {"liked": True, "count": 1})

    def test_hourly_limit_counts_comments_replies_and_openings(self):
        self.client.force_login(self.other)
        for i in range(8):
            Comment.objects.create(
                country=self.country,
                user=self.other,
                text=f"Question {i}",
                kind=Comment.KIND_QUESTION,
            )
        OpeningReport.objects.create(
            country=self.country,
            user=self.other,
            opened_on=timezone.localdate(),
        )
        self.assertEqual(
            Comment.objects.filter(user=self.other).count()
            + Reply.objects.filter(user=self.other).count()
            + OpeningReport.objects.filter(user=self.other).count(),
            10,
        )

        response = self.client.post(
            reverse("country_detail", args=["france"]),
            {"kind": "question", "text": "An eleventh post"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "10 posts in the last hour")
        self.assertFalse(Comment.objects.filter(text="An eleventh post").exists())

        response = self.client.post(
            reverse("create_reply", args=[self.comment.id]),
            {"text": "An eleventh reply"},
        )
        self.assertContains(response, "10 posts in the last hour")
        self.assertFalse(Reply.objects.filter(text="An eleventh reply").exists())

        response = self.client.post(
            reverse("report_opening", args=["france"]),
            {"opened_on": (timezone.localdate() - timedelta(days=1)).isoformat()},
        )
        self.assertContains(response, "10 posts in the last hour")
        self.assertEqual(OpeningReport.objects.filter(user=self.other).count(), 1)

        Comment.objects.filter(user=self.other).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        response = self.client.post(
            reverse("country_detail", args=["france"]),
            {"kind": "question", "text": "After the hour"},
            follow=True,
        )
        self.assertContains(response, "your post is live")
        self.assertTrue(Comment.objects.filter(text="After the hour").exists())


class StaticPageTests(TestCase):
    def test_guidelines_privacy_and_contact_are_linked(self):
        for name, text in (
            ("guidelines", "Leave out passport numbers"),
            ("privacy", "hashed password"),
            ("contact", "contact@visacommunity.example"),
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, text)
        home = self.client.get(reverse("home"))
        self.assertContains(home, reverse("guidelines"))
        self.assertContains(home, reverse("privacy"))
        self.assertContains(home, reverse("contact"))
        self.assertNotContains(home, 'href="#"')

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_missing_page_shows_buddy_and_a_way_back(self):
        response = self.client.get("/not-a-real-page/")
        self.assertContains(response, "Back to countries", status_code=404)
        self.assertContains(response, "Visa Buddy", status_code=404)
        self.assertContains(response, 'fill="#F9EEDB"', status_code=404)

    def test_server_error_page_shows_buddy_and_a_way_back(self):
        response = server_error(RequestFactory().get("/"))
        self.assertContains(response, "Back to countries", status_code=500)
        self.assertContains(response, "Visa Buddy", status_code=500)
        self.assertContains(response, 'fill="#F9EEDB"', status_code=500)
