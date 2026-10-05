from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from axes.backends import AxesStandaloneBackend


class QuietAxesBackend(AxesStandaloneBackend):
    """Axes lockout when a request exists. Calls without a request stay on the next backend."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is None:
            return None
        return super().authenticate(request, username, password, **kwargs)


class EmailOrUsernameBackend(ModelBackend):
    """Sign in with the username, or with the email address (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        user = _user_by_username_or_email(username)
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


def _user_by_username_or_email(identifier):
    User = get_user_model()
    user = User.objects.filter(username=identifier).first()
    if user is not None:
        return user

    # More than one account sharing an email is ambiguous — refuse the match.
    matches = list(User.objects.filter(email__iexact=identifier)[:2])
    if len(matches) == 1:
        return matches[0]
    return None
