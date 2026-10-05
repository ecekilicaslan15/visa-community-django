from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.urls import reverse
from django.utils.safestring import mark_safe

User = get_user_model()


def _style_inputs(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            continue
        field.widget.attrs["class"] = "input"


class SignUpForm(UserCreationForm):
    """Username, required unique email, password, and optional name."""

    email = forms.EmailField(label="Email", required=True)
    privacy_accepted = forms.BooleanField(
        required=True,
        error_messages={"required": "Please read and accept the Privacy Notice."},
    )
    first_name = forms.CharField(
        label="First name (optional)",
        required=False,
        max_length=150,
    )
    last_name = forms.CharField(
        label="Last name (optional)",
        required=False,
        max_length=150,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    field_order = [
        "username",
        "email",
        "first_name",
        "last_name",
        "password1",
        "password2",
        "privacy_accepted",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        notice = reverse("privacy")
        self.fields["privacy_accepted"].label = mark_safe(
            'I have read the <a href="%s">Privacy Notice (KVKK Aydınlatma Metni)</a>'
            % notice
        )
        _style_inputs(self)
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """Same login form, labelled for username or email."""

    remember_me = forms.BooleanField(required=False, label="Remember me")

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Please enter a correct username or email and password.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        _style_inputs(self)


class ProfileForm(forms.ModelForm):
    """Edit the name and email stored on the signed-in user."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_email = (self.instance.email or "") if self.instance.pk else ""
        self.fields["email"].required = True
        _style_inputs(self)
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    @property
    def email_changed(self):
        new_email = self.cleaned_data.get("email", "")
        return new_email.casefold() != self._original_email.casefold()


class DeleteAccountForm(forms.Form):
    """The member must retype their username before the account is removed."""

    username = forms.CharField(
        label="Type your username to confirm",
        widget=forms.TextInput(attrs={"class": "input", "autocomplete": "off"}),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username != self.user.get_username():
            raise forms.ValidationError("Type your username exactly to confirm.")
        return username
