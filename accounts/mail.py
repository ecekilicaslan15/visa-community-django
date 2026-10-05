from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import PasswordResetRequest, VerificationResend

VERIFY_SUBJECT = "Confirm your VisaCommunity email"
RESEND_LIMIT = 3
RESEND_WINDOW = timedelta(hours=1)
RESEND_LIMIT_MESSAGE = "You can resend the confirmation email 3 times an hour."
RESET_LIMIT = 5
RESET_WINDOW = timedelta(minutes=30)
RESET_LIMIT_MESSAGE = "Too many reset requests. Please wait 30 minutes and try again."
CONFIRM_BEFORE_POSTING = "Please confirm your email before posting."


def email_is_confirmed(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.email_verified)


def verification_url(user, request):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("accounts:verify_email", kwargs={"uidb64": uid, "token": token})
    return request.build_absolute_uri(path)


def send_account_email(subject, text_template, html_template, context, to_email):
    """Plain text plus an HTML alternative in the site colours."""
    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()


def send_verification_email(user, request):
    send_account_email(
        VERIFY_SUBJECT,
        "registration/verify_email.txt",
        "registration/verify_email.html",
        {"user": user, "verify_url": verification_url(user, request)},
        user.email,
    )


def resend_is_limited(user):
    since = timezone.now() - RESEND_WINDOW
    sent = VerificationResend.objects.filter(user=user, sent_at__gte=since).count()
    return sent >= RESEND_LIMIT


def note_resend(user):
    VerificationResend.objects.create(user=user)


def client_ip(request):
    return (request.META.get("REMOTE_ADDR") or "")[:45]


def reset_is_limited(request):
    since = timezone.now() - RESET_WINDOW
    sent = PasswordResetRequest.objects.filter(
        ip_address=client_ip(request),
        created_at__gte=since,
    ).count()
    return sent >= RESET_LIMIT


def note_reset_request(request):
    PasswordResetRequest.objects.create(ip_address=client_ip(request))
