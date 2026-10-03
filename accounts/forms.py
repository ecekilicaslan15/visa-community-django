from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    """Django's built-in sign-up form, with the design's input styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
