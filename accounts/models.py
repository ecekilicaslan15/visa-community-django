from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Verification and privacy-consent state for one account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="profile",
        on_delete=models.CASCADE,
    )
    # Existing accounts are marked verified in the data migration.
    # Sign-up sets this back to False until the email link is used.
    email_verified = models.BooleanField(default=True)
    consent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile for {self.user}"


class VerificationResend(models.Model):
    """One press of the resend button. The first sign-up email is not counted."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="verification_resends",
        on_delete=models.CASCADE,
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]


class PasswordResetRequest(models.Model):
    """A password-reset form submit, counted per IP for the 30-minute throttle."""

    ip_address = models.CharField(max_length=45, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
