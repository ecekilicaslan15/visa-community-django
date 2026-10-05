from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.cascade import cascade_eligibility
from core.community_stats import median_gap_days
from core.models import Comment, ConsulateVisaStat, Country, CountryVisaStat, OpeningReport, StatsDataset
from core.visa_stats import city_gap_sentence, country_stat_rows, dataset_totals, largest_city_gap, rate_band, refusal_rate

User = get_user_model()


class VisaRateTests(TestCase):
    def test_the_commission_formula_matches_the_turkiye_total(self):
        self.assertEqual(refusal_rate(1_072_054, 183_196), Decimal("14.6"))
        self.assertIsNone(refusal_rate(0, 0))
        self.assertEqual(rate_band(Decimal("20")), "reject")
        self.assertEqual(rate_band(Decimal("10")), "amber")
        self.assertEqual(rate_band(Decimal("9.9")), "approve")

    def test_loader_is_idempotent_and_germany_consulates_match_the_country_row(self):
        call_command("load_visa_stats")
        call_command("load_visa_stats")
        self.assertEqual(StatsDataset.objects.count(), 1)
        self.assertEqual(CountryVisaStat.objects.count(), 27)
        self.assertEqual(ConsulateVisaStat.objects.count(), 47)

        dataset = StatsDataset.objects.get(year=2025)
        totals = dataset_totals(dataset)
        self.assertEqual(totals["applications"], 1_268_376)
        self.assertEqual(totals["issued"], 1_072_054)
        self.assertEqual(totals["refused"], 183_196)
        self.assertEqual(totals["refusal_rate"], Decimal("14.6"))

        germany = CountryVisaStat.objects.get(dataset=dataset, country_code="DE")
        consulates = ConsulateVisaStat.objects.filter(dataset=dataset, country_code="DE")
        self.assertEqual(consulates.count(), 3)
        self.assertEqual(consulates.aggregate(total=Sum("applications"))["total"], germany.applications)
        self.assertEqual(germany.applications, 217_627)

        gap = largest_city_gap(dataset)
        self.assertEqual(
            city_gap_sentence(gap),
            "The same country can differ a lot between cities — e.g. Germany: Istanbul 15.5% vs Ankara 44.1%.",
        )

    def test_seed_creates_every_country_in_the_statistics_and_keeps_existing_rows(self):
        france = Country.objects.create(name="France", slug="france", description="Keep me")
        call_command("seed_countries")
        france.refresh_from_db()
        self.assertEqual(france.code, "FR")
        self.assertEqual(france.description, "Keep me")
        self.assertEqual(Country.objects.count(), 27)
        call_command("seed_countries")
        self.assertEqual(Country.objects.count(), 27)


class CascadeTests(TestCase):
    def test_each_step_and_each_reason_to_say_no(self):
        today = date(2026, 10, 5)
        recent = date(2026, 8, 1)
        self.assertEqual(
            cascade_eligibility("none", None, None, today=today)["reason"],
            "A cascade visa starts from a previous visa. With no earlier visa, this ladder does not start yet.",
        )
        self.assertIn("lawfully", cascade_eligibility("single", recent, False, today=today)["reason"])
        self.assertIn("expiry date", cascade_eligibility("single", None, True, today=today)["reason"])
        self.assertIn("lawfully", cascade_eligibility("single", recent, None, today=today)["reason"])

        single = cascade_eligibility("single", recent, True, today=today)
        self.assertTrue(single["eligible"])
        self.assertEqual(single["step"], "6 months")

        one_year = cascade_eligibility("6m", recent, True, today=today)
        self.assertEqual(one_year["step"], "1 year")
        self.assertEqual(cascade_eligibility("1y", recent, True, today=today)["step"], "3 years")
        self.assertEqual(cascade_eligibility("3y", recent, True, today=today)["step"], "5 years")

        too_old_for_single = cascade_eligibility("single", date(2025, 10, 4), True, today=today)
        self.assertFalse(too_old_for_single["eligible"])
        self.assertEqual(too_old_for_single["reason"], "more than 1 year since expiry")
        still_in_time = cascade_eligibility("single", date(2025, 10, 5), True, today=today)
        self.assertTrue(still_in_time["eligible"])

        too_old_for_longer = cascade_eligibility("6m", date(2024, 10, 4), True, today=today)
        self.assertEqual(too_old_for_longer["reason"], "more than 2 years since expiry")
        self.assertTrue(cascade_eligibility("1y", date(2024, 10, 5), True, today=today)["eligible"])
        self.assertEqual(
            cascade_eligibility("3y", date(2024, 10, 4), True, today=today)["reason"],
            "more than 2 years since expiry",
        )

        # A visa that has not expired yet is still inside the window.
        upcoming = cascade_eligibility("single", today + timedelta(days=20), True, today=today)
        self.assertEqual(upcoming["step"], "6 months")

    def test_a_leap_day_uses_28_february_as_the_edge_of_one_year(self):
        today = date(2024, 2, 29)
        self.assertTrue(cascade_eligibility("single", date(2023, 2, 28), True, today=today)["eligible"])
        self.assertFalse(cascade_eligibility("single", date(2023, 2, 27), True, today=today)["eligible"])


class StatsPageTests(TestCase):
    def test_statistics_pages_load_before_the_figures_are_imported(self):
        for name in (
            "stats_overview",
            "stats_refusals",
            "stats_cascade",
            "stats_appointments",
            "insights",
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
        home = self.client.get(reverse("home"))
        self.assertContains(home, "Statistics")
        self.assertContains(home, reverse("stats_overview"))

    def test_overview_refusals_filters_and_the_country_card(self):
        call_command("seed_countries")
        call_command("load_visa_stats")
        overview = self.client.get(reverse("stats_overview"))
        self.assertContains(overview, "1,268,376")
        self.assertContains(overview, "1,072,054")
        self.assertContains(overview, "183,196")
        self.assertContains(overview, "14.6%")
        self.assertContains(overview, "2nd-largest applicant country")
        self.assertContains(overview, "Applications lodged in Türkiye, short-stay (type C) visas.")
        self.assertContains(overview, "Official EU statistics — not a prediction for your application.")
        self.assertContains(overview, "28 May 2026")

        by_rate = self.client.get(reverse("stats_refusals"))
        rows = country_stat_rows(StatsDataset.objects.get(), sort="rate")
        body = by_rate.content.decode()
        self.assertLess(body.find(rows[0]["name"]), body.find(rows[-1]["name"]))
        self.assertContains(by_rate, "Germany: Istanbul 15.5% vs Ankara 44.1%.")
        self.assertContains(by_rate, ">Edirne<")

        by_applications = self.client.get(reverse("stats_refusals") + "?sort=applications")
        ordered = by_applications.content.decode()
        self.assertLess(ordered.find("Greece"), ordered.find("Latvia"))

        ankara = self.client.get(reverse("stats_refusals") + "?city=Ankara")
        self.assertContains(ankara, "Germany Ankara refusal rate 44.1 percent")
        self.assertNotContains(ankara, "Italy Izmir")
        self.assertNotContains(ankara, "Greece Edirne")

        izmir = self.client.get(reverse("stats_refusals") + "?city=Izmir")
        self.assertContains(izmir, "Italy Izmir refusal rate 8.8 percent")
        self.assertNotContains(izmir, "Germany Ankara")

        france = self.client.get(reverse("country_detail", args=["france"]))
        self.assertContains(france, "Official 2025 data")
        self.assertContains(france, "15.5% refusal rate")
        self.assertContains(france, "143,379")
        self.assertContains(france, "Ankara")
        self.assertContains(france, "16.1%")
        self.assertContains(france, "Official EU statistics — not a prediction for your application.")

    def test_cascade_page_answers_without_storing_anything(self):
        response = self.client.get(reverse("stats_cascade"))
        self.assertContains(response, "Commission Implementing Decision C(2025) 4694")
        self.assertContains(response, "Consulates can still decide differently — this is not a guarantee.")
        self.assertContains(response, "Within 1 year of a lawfully used previous visa")
        self.assertEqual(StatsDataset.objects.count(), 0)

        today = timezone.localdate()
        answer = self.client.get(
            reverse("stats_cascade"),
            {"previous": "6m", "expired_on": today.isoformat(), "lawful": "yes"},
        )
        self.assertContains(answer, "1 year")
        self.assertContains(answer, "You may be eligible for a 1-year multiple-entry visa.")
        self.assertContains(answer, "not a guarantee")

        refused = self.client.get(
            reverse("stats_cascade"),
            {"previous": "single", "expired_on": "2020-01-01", "lawful": "yes"},
        )
        self.assertContains(refused, "more than 1 year since expiry")

    def test_appointments_come_from_community_reports_only(self):
        call_command("seed_countries")
        call_command("load_visa_stats")
        user = User.objects.create_user("ayse", "ayse@example.com", "Traveler-pass-2026")
        france = Country.objects.get(slug="france")
        italy = Country.objects.get(slug="italy")
        today = timezone.localdate()
        for offset in (0, 10, 20):
            OpeningReport.objects.create(
                country=france, user=user, opened_on=today - timedelta(days=offset)
            )
        OpeningReport.objects.create(country=italy, user=user, opened_on=today)
        for wait in (12, 18):
            Comment.objects.create(
                country=france,
                user=user,
                text="Passport came back.",
                kind=Comment.KIND_EXPERIENCE,
                wait_days=wait,
            )

        self.assertEqual(median_gap_days([today - timedelta(days=20), today - timedelta(days=10), today]), 10)
        response = self.client.get(reverse("stats_appointments"))
        self.assertContains(response, "Community data")
        self.assertContains(response, "A slot opens about every 10 days.")
        self.assertContains(response, "Median wait from appointment to passport: 15 days.")
        self.assertContains(response, "Not enough reports yet")
        self.assertContains(response, "These are refusal rates, not appointment availability.")
        self.assertContains(response, reverse("country_detail", args=["italy"]) + "#report-opening")
