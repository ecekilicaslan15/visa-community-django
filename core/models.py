from django.conf import settings
from django.db import models


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
