from django import forms

from .models import Comment, Reply, Reply


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = [
            "kind",
            "text",
            "outcome",
            "appointment_city",
            "appointment_date",
            "wait_days",
        ]
        widgets = {
            # The kind is chosen with the "Ask a question / Share an
            # experience" toggle; JS writes the value into this hidden input.
            "kind": forms.HiddenInput(attrs={"data-kind-input": ""}),
            "text": forms.Textarea(
                attrs={
                    "class": "input",
                    "maxlength": 2000,
                    "data-compose-text": "",
                }
            ),
            # Rendered by hand in the template as the stamp-style pills
            "outcome": forms.RadioSelect,
            "appointment_city": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Istanbul"}
            ),
            "appointment_date": forms.DateInput(
                attrs={"class": "input", "type": "date"}, format="%Y-%m-%d"
            ),
            "wait_days": forms.NumberInput(
                attrs={"class": "input", "min": 0, "placeholder": "e.g. 9"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")

        if kind == Comment.KIND_EXPERIENCE:
            if not cleaned.get("outcome"):
                self.add_error("outcome", "Please tell us whether the visa was approved or rejected.")
        else:
            # Questions don't carry experience details — drop anything that
            # was typed before switching back to "Ask a question".
            cleaned["outcome"] = ""
            cleaned["appointment_city"] = ""
            cleaned["appointment_date"] = None
            cleaned["wait_days"] = None
        return cleaned


class ReplyForm(forms.ModelForm):
    """Reply text only. The view sets the author and the thread."""

    class Meta:
        model = Reply
        fields = ["text"]
        labels = {"text": "Your reply"}
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "input",
                    "maxlength": 1000,
                    "rows": 4,
                    "data-compose-text": "",
                }
            ),
        }
