from datetime import date, datetime, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.names import avatar_class
from core.models import Comment, Country, OpeningReport, Reply, earliest_opening_date, opening_date_problem
from core.predictions import predict_next_window

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


def _month_day(value):
    return date_format(value, "M j")


class PredictionTests(SimpleTestCase):
    def test_fewer_than_five_distinct_dates_is_not_a_window(self):
        day = date(2026, 3, 1)
        dates = [day + timedelta(days=10 * i) for i in range(4)]
        self.assertIsNone(predict_next_window(dates, today=day))
        self.assertIsNone(predict_next_window(dates + dates, today=day))
        self.assertIsNone(predict_next_window([], today=day))

    def test_equal_gaps_use_the_median_and_a_two_day_window(self):
        dates = [
            date(2026, 1, 1),
            date(2026, 1, 11),
            date(2026, 1, 21),
            date(2026, 1, 31),
            date(2026, 2, 10),
        ]
        result = predict_next_window(dates, today=date(2026, 2, 1))
        self.assertEqual(result["expected"], date(2026, 2, 20))
        self.assertEqual(result["start"], date(2026, 2, 18))
        self.assertEqual(result["end"], date(2026, 2, 22))
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["meter"], 40)
        self.assertEqual(result["reports"], 5)
        self.assertEqual(result["median_gap_days"], 10)

        # A window that still includes today stays where it is.
        same = predict_next_window(dates, today=date(2026, 2, 22))
        self.assertEqual(same["start"], date(2026, 2, 18))
        self.assertEqual(same["end"], date(2026, 2, 22))

    def test_a_window_already_in_the_past_rolls_forward_by_the_median_gap(self):
        dates = [
            date(2025, 11, 1),
            date(2025, 11, 11),
            date(2025, 11, 21),
            date(2025, 12, 1),
            date(2025, 12, 11),
        ]
        result = predict_next_window(dates, today=date(2026, 1, 15))
        self.assertEqual(result["expected"], date(2026, 1, 20))
        self.assertEqual(result["start"], date(2026, 1, 18))
        self.assertEqual(result["end"], date(2026, 1, 22))

    def test_duplicate_reports_raise_confidence_without_adding_gaps(self):
        dates = [
            date(2026, 1, 1),
            date(2026, 1, 11),
            date(2026, 1, 21),
            date(2026, 1, 31),
            date(2026, 2, 10),
        ]
        result = predict_next_window(dates + dates, today=date(2026, 2, 1))
        self.assertEqual(result["reports"], 10)
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(result["meter"], 60)
        self.assertEqual(result["expected"], date(2026, 2, 20))

    def test_confidence_bands_and_a_spread_that_lowers_one_step(self):
        start = date(2026, 1, 1)
        tight = [start + timedelta(days=7 * i) for i in range(10)]
        medium = predict_next_window(tight, today=start)
        self.assertEqual(medium["confidence"], "medium")
        self.assertEqual(medium["meter"], 60)

        twenty = [start + timedelta(days=3 * i) for i in range(20)]
        self.assertEqual(predict_next_window(twenty, today=start)["confidence"], "medium-high")
        self.assertEqual(predict_next_window(twenty, today=start)["meter"], 80)

        forty = [start + timedelta(days=3 * i) for i in range(40)]
        self.assertEqual(predict_next_window(forty, today=start)["confidence"], "high")
        self.assertEqual(predict_next_window(forty, today=start)["meter"], 95)

        gaps = [5, 10, 15, 20, 40, 60, 80, 100, 120]
        spread = [start]
        for gap in gaps:
            spread.append(spread[-1] + timedelta(days=gap))
        lowered = predict_next_window(spread, today=start)
        self.assertEqual(len(spread), 10)
        self.assertEqual(lowered["confidence"], "low")
        self.assertEqual(lowered["meter"], 40)

    def test_datetimes_are_read_as_calendar_dates(self):
        dates = [datetime(2026, 1, 1, 15, 30) + timedelta(days=10 * i) for i in range(5)]
        result = predict_next_window(dates, today=date(2026, 1, 1))
        self.assertEqual(result["expected"], date(2026, 2, 20))


class OpeningDateTests(SimpleTestCase):
    def test_one_year_is_allowed_and_older_or_future_dates_are_not(self):
        today = date(2026, 10, 5)
        self.assertIsNone(opening_date_problem(today, today=today))
        self.assertIsNone(opening_date_problem(date(2025, 10, 5), today=today))
        self.assertIn("future", opening_date_problem(date(2026, 10, 6), today=today))
        self.assertIn("year", opening_date_problem(date(2025, 10, 4), today=today))

    def test_a_leap_day_uses_28_february_as_the_oldest_accepted_date(self):
        today = date(2024, 2, 29)
        self.assertEqual(earliest_opening_date(today), date(2023, 2, 28))
        self.assertIsNone(opening_date_problem(date(2023, 2, 28), today=today))
        self.assertIsNotNone(opening_date_problem(date(2023, 2, 27), today=today))


class OpeningReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ayse", "ayse@example.com", PASSWORD)
        self.other = User.objects.create_user("mehmet", "mehmet@example.com", PASSWORD)
        self.country = Country.objects.create(name="France", slug="france", code="FR")
        self.spain = Country.objects.create(name="Spain", slug="spain", code="ES", is_active=False)
        self.url = reverse("report_opening", args=["france"])

    def test_opening_reports_are_registered_in_the_admin(self):
        self.assertIn(OpeningReport, admin.site._registry)

    def test_reporting_is_post_only_and_anonymous_posts_go_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()

        response = self.client.post(self.url, {"opened_on": timezone.localdate().isoformat()})
        self.assertRedirects(response, f"/accounts/login/?next={self.url}")

    def test_country_page_asks_visitors_to_sign_in_before_reporting(self):
        response = self.client.get(reverse("country_detail", args=["france"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Still waiting for enough appointment data.")
        self.assertContains(response, "0 of 5 openings reported")
        self.assertContains(response, "Community data. Not official information.")
        self.assertContains(response, "?next=/countries/france/")
        self.assertNotContains(response, "Coming soon")
        self.assertNotContains(response, "of 30 dated")

    def test_a_report_is_saved_for_the_signed_in_user_and_the_url_country(self):
        today = timezone.localdate()
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "opened_on": today.isoformat(),
                "city": "  Ankara  ",
                "user": self.other.id,
                "country": self.spain.id,
            },
            follow=True,
        )
        self.assertContains(response, "that opening is now part of the community outlook")
        report = OpeningReport.objects.get()
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.country, self.country)
        self.assertEqual(report.city, "Ankara")
        self.assertEqual(report.opened_on, today)
        self.assertContains(response, f"Last opening reported {_month_day(today)}")
        self.assertContains(response, "1 of 5 openings reported")

    def test_future_old_and_duplicate_dates_are_rejected(self):
        today = timezone.localdate()
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"opened_on": (today + timedelta(days=1)).isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "in the future")
        self.assertFalse(OpeningReport.objects.exists())

        too_old = earliest_opening_date(today) - timedelta(days=1)
        response = self.client.post(self.url, {"opened_on": too_old.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "more than a year ago")
        self.assertFalse(OpeningReport.objects.exists())

        response = self.client.post(self.url, {"opened_on": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

        self.client.post(self.url, {"opened_on": today.isoformat(), "city": "Istanbul"})
        response = self.client.post(self.url, {"opened_on": today.isoformat(), "city": "Istanbul"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already reported this opening date")
        self.assertEqual(OpeningReport.objects.count(), 1)

        self.client.force_login(self.other)
        response = self.client.post(self.url, {"opened_on": today.isoformat()})
        self.assertRedirects(response, reverse("country_detail", args=["france"]))
        self.assertEqual(OpeningReport.objects.count(), 2)

    def test_the_same_user_can_report_the_same_day_for_another_country(self):
        italy = Country.objects.create(name="Italy", slug="italy", code="IT")
        today = timezone.localdate()
        OpeningReport.objects.create(country=self.country, user=self.user, opened_on=today)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("report_opening", args=["italy"]),
            {"opened_on": today.isoformat()},
        )
        self.assertRedirects(response, reverse("country_detail", args=["italy"]))
        self.assertEqual(OpeningReport.objects.filter(user=self.user).count(), 2)

    def test_inactive_country_is_not_found(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("report_opening", args=["spain"]),
            {"opened_on": timezone.localdate().isoformat()},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(reverse("country_detail", args=["spain"])).status_code, 404)

    def test_model_rejects_a_future_date_and_a_repeated_report(self):
        today = timezone.localdate()
        report = OpeningReport(country=self.country, user=self.user, opened_on=today + timedelta(days=1))
        with self.assertRaises(ValidationError):
            report.full_clean()

        OpeningReport.objects.create(country=self.country, user=self.user, opened_on=today)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OpeningReport.objects.create(country=self.country, user=self.user, opened_on=today)

    def test_the_hero_chip_uses_the_newest_report(self):
        today = timezone.localdate()
        newer_opening = today - timedelta(days=3)
        older_opening = today - timedelta(days=12)
        OpeningReport.objects.create(country=self.country, user=self.user, opened_on=newer_opening)
        OpeningReport.objects.create(country=self.country, user=self.other, opened_on=older_opening)
        response = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(response, f"Last opening reported {_month_day(older_opening)}")
        self.assertNotContains(response, f"Last opening reported {_month_day(newer_opening)}")
        self.assertContains(response, "2 of 5 openings reported")
        self.assertContains(response, "Still waiting for enough appointment data.")
        self.assertNotContains(response, "Next opening window")

    def test_five_distinct_openings_show_the_community_window(self):
        today = timezone.localdate()
        for offset in range(4, -1, -1):
            OpeningReport.objects.create(
                country=self.country,
                user=self.user,
                opened_on=today - timedelta(days=10 * offset),
                city="Istanbul",
            )
        response = self.client.get(reverse("country_detail", args=["france"]))
        start = today + timedelta(days=8)
        end = today + timedelta(days=12)
        self.assertContains(response, "Next opening window · likely")
        self.assertContains(response, f"{_month_day(start)} – {_month_day(end)}")
        self.assertContains(response, "width:40%")
        self.assertContains(
            response,
            "Community data · low confidence · based on 5 openings reported by the community. Not official information.",
        )
        self.assertNotContains(response, "Still waiting for enough appointment data.")
        self.assertContains(response, f"Last opening reported {_month_day(today)}")

