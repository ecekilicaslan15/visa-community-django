from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    redirect_to_login,
)
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.http import require_GET

from .forms import (
    DeleteAccountForm,
    EmailOrUsernameAuthenticationForm,
    ProfileForm,
    SignUpForm,
)
from .mail import (
    RESET_LIMIT_MESSAGE,
    RESEND_LIMIT_MESSAGE,
    email_is_confirmed,
    note_resend,
    note_reset_request,
    resend_is_limited,
    reset_is_limited,
    send_verification_email,
)
from .names import display_name

User = get_user_model()


class InputClassMixin:
    """Give Django's auth widgets the same .input class as the rest of the site."""

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs["class"] = "input"
        return form


class CommunityLoginView(LoginView):
    authentication_form = EmailOrUsernameAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        return response


class CommunityPasswordResetView(InputClassMixin, PasswordResetView):
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"

    def form_valid(self, form):
        if reset_is_limited(self.request):
            form.add_error(None, RESET_LIMIT_MESSAGE)
            return self.form_invalid(form)
        note_reset_request(self.request)
        messages.success(
            self.request,
            "If an account exists for that email, a reset link is on its way.",
        )
        return super().form_valid(form)


class CommunityPasswordResetConfirmView(InputClassMixin, PasswordResetConfirmView):
    def form_valid(self, form):
        messages.success(self.request, "Your password was reset. You can sign in now.")
        return super().form_valid(form)


class CommunityPasswordChangeView(InputClassMixin, PasswordChangeView):
    def form_valid(self, form):
        messages.success(self.request, "Your password was changed.")
        return super().form_valid(form)


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = user.profile
            profile.email_verified = False
            profile.consent_at = timezone.now()
            profile.save(update_fields=["email_verified", "consent_at"])
            # login() sets last_login, and the token includes that timestamp.
            login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
            send_verification_email(user, request)
            messages.success(request, f"Welcome aboard, {display_name(user)}!")
            return redirect("home")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def account_settings(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            if form.email_changed:
                profile = request.user.profile
                profile.email_verified = False
                profile.save(update_fields=["email_verified"])
                send_verification_email(request.user, request)
                messages.success(
                    request,
                    "Your profile was updated. Please confirm your new email.",
                )
            else:
                messages.success(request, "Your profile was updated.")
            return redirect("accounts:settings")
    else:
        form = ProfileForm(instance=request.user)

    return render(
        request,
        "accounts/settings.html",
        {"form": form, "delete_form": DeleteAccountForm(user=request.user)},
    )


def delete_account(request):
    """POST only. The signed-in member must retype their username."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    delete_form = DeleteAccountForm(request.POST, user=request.user)
    if not delete_form.is_valid():
        messages.error(request, "Type your username exactly to confirm account deletion.")
        return render(
            request,
            "accounts/settings.html",
            {
                "form": ProfileForm(instance=request.user),
                "delete_form": delete_form,
            },
        )

    user = request.user
    # logout() flushes the session, so the goodbye message is stored after it.
    logout(request)
    user.delete()
    messages.success(request, "Your account was deleted.")
    return redirect("home")


def verify_email(request, uidb64, token):
    """The link in the confirmation email. A bad or old link stays a normal page."""
    user = _user_from_uid(uidb64)
    valid = user is not None and default_token_generator.check_token(user, token)
    if not valid:
        return render(request, "accounts/verify_email.html", {"valid": False})

    profile = user.profile
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    messages.success(request, "Your email is confirmed.")
    return redirect("home")


def resend_verification(request):
    """POST only. At most three confirmation emails per account per hour."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    destination = _safe_next(request) or "/"
    if email_is_confirmed(request.user):
        messages.info(request, "Your email is already confirmed.")
        return redirect(destination)
    if resend_is_limited(request.user):
        messages.error(request, RESEND_LIMIT_MESSAGE)
        return redirect(destination)

    send_verification_email(request.user, request)
    note_resend(request.user)
    messages.success(request, "Confirmation email sent.")
    return redirect(destination)


@require_GET
@login_required
def download_data(request):
    """JSON of this account only: profile, posts, replies, and opening reports."""
    user = request.user
    profile = user.profile
    payload = {
        "account": {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined.isoformat(),
            "email_verified": profile.email_verified,
            "privacy_consent_at": (
                profile.consent_at.isoformat() if profile.consent_at else None
            ),
        },
        "posts": [
            {
                "id": comment.id,
                "country": comment.country.name,
                "kind": comment.kind,
                "text": comment.text,
                "created_at": comment.created_at.isoformat(),
            }
            for comment in user.comment_set.select_related("country").order_by("id")
        ],
        "replies": [
            {
                "id": reply.id,
                "text": reply.text,
                "created_at": reply.created_at.isoformat(),
            }
            for reply in user.replies.order_by("id")
        ],
        "opening_reports": [
            {
                "id": report.id,
                "country": report.country.name,
                "city": report.city,
                "opened_on": report.opened_on.isoformat(),
            }
            for report in user.opening_reports.select_related("country").order_by("id")
        ],
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = 'attachment; filename="visacommunity-data.json"'
    return response


def _user_from_uid(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None
