from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Country(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    # Two-letter code shown on the country "sticker" (FR, DE, PT...)
    code = models.CharField(max_length=3, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def sticker_code(self):
        return (self.code or self.name[:2]).upper()


class Comment(models.Model):
    # A comment is either a question or a shared visa experience.
    KIND_QUESTION = "question"
    KIND_EXPERIENCE = "experience"
    KIND_CHOICES = [
        (KIND_QUESTION, "Question"),
        (KIND_EXPERIENCE, "Experience"),
    ]

    OUTCOME_APPROVED = "approved"
    OUTCOME_REJECTED = "rejected"
    OUTCOME_CHOICES = [
        (OUTCOME_APPROVED, "Approved"),
        (OUTCOME_REJECTED, "Rejected"),
    ]

    country = models.ForeignKey(
        Country,
        related_name="comments",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default=KIND_QUESTION
    )
    # The fields below are only filled in for experiences.
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)
    appointment_city = models.CharField(max_length=100, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    wait_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days between the appointment and getting the passport back.",
    )

    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_comments",
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.country}"

    @property
    def is_experience(self):
        return self.kind == self.KIND_EXPERIENCE

    @property
    def is_question(self):
        return self.kind == self.KIND_QUESTION


class Reply(models.Model):
    """A response on a question or experience thread."""

    comment = models.ForeignKey(
        Comment,
        related_name="replies",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="replies",
        on_delete=models.CASCADE,
    )
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_replies",
        blank=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} on {self.comment_id}"


def earliest_opening_date(today):
    """The oldest opening date still accepted: one year before today."""
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        # 29 February has no match in the previous year.
        return date(today.year - 1, 2, 28)


def opening_date_problem(opened_on, today=None):
    """A message when the date is in the future or more than a year old."""
    if opened_on is None:
        return None
    today = today or timezone.localdate()
    if opened_on > today:
        return "The opening date can't be in the future."
    if opened_on < earliest_opening_date(today):
        return "The opening date can't be more than a year ago."
    return None


class OpeningReport(models.Model):
    """A traveler reporting that appointment slots opened on a given day."""

    country = models.ForeignKey(
        Country,
        related_name="opening_reports",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="opening_reports",
        on_delete=models.CASCADE,
    )
    city = models.CharField(max_length=100, blank=True)
    opened_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "country", "opened_on"],
                name="unique_opening_per_user_country_day",
            )
        ]

    def __str__(self):
        return f"{self.country} {self.opened_on}"

    def clean(self):
        super().clean()
        problem = opening_date_problem(self.opened_on)
        if problem:
            raise ValidationError({"opened_on": problem})


class StatsDataset(models.Model):
    """One published release of official Schengen visa statistics."""

    year = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=200)
    source_name = models.CharField(max_length=200)
    source_url = models.URLField()
    published_on = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-year"]

    def __str__(self):
        return f"{self.title} ({self.year})"


class CountryVisaStat(models.Model):
    """Applications lodged in Türkiye for one Schengen country."""

    dataset = models.ForeignKey(
        StatsDataset,
        related_name="country_stats",
        on_delete=models.CASCADE,
    )
    country_code = models.CharField(max_length=3)
    country_name = models.CharField(max_length=100)
    applications = models.PositiveIntegerField()
    issued = models.PositiveIntegerField()
    multiple_entry = models.PositiveIntegerField()
    refused = models.PositiveIntegerField()

    class Meta:
        ordering = ["country_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "country_code"],
                name="unique_country_stat_per_dataset",
            )
        ]

    def __str__(self):
        return f"{self.country_name} {self.dataset.year}"


class ConsulateVisaStat(models.Model):
    """Published refusal rate for one consulate in Türkiye."""

    dataset = models.ForeignKey(
        StatsDataset,
        related_name="consulate_stats",
        on_delete=models.CASCADE,
    )
    country_code = models.CharField(max_length=3)
    country_name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    applications = models.PositiveIntegerField()
    refusal_rate = models.DecimalField(max_digits=4, decimal_places=1)

    class Meta:
        ordering = ["-refusal_rate", "country_name", "city"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "country_code", "city"],
                name="unique_consulate_stat_per_dataset",
            )
        ]

    def __str__(self):
        return f"{self.country_name} {self.city} {self.refusal_rate}%"
