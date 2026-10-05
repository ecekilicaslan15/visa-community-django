from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    redirect_to_login,
)
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from .forms import DeleteAccountForm, ProfileForm, SignUpForm
from .names import display_name


class InputClassMixin:
    """Give Django's auth widgets the same .input class as the rest of the site."""

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs["class"] = "input"
        return form


class CommunityPasswordResetView(InputClassMixin, PasswordResetView):
    def form_valid(self, form):
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
            login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
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
