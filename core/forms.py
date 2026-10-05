from django import forms

from .models import Comment, OpeningReport, Reply, opening_date_problem


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


class OpeningReportForm(forms.ModelForm):
    """City and opening date. The view sets the traveler and the country."""

    class Meta:
        model = OpeningReport
        fields = ["city", "opened_on"]
        labels = {
            "city": "City (optional)",
            "opened_on": "Date slots opened",
        }
        widgets = {
            "city": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Istanbul", "maxlength": 100}
            ),
            "opened_on": forms.DateInput(
                attrs={"class": "input", "type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, user=None, country=None, **kwargs):
        self.user = user
        self.country = country
        super().__init__(*args, **kwargs)
        self.fields["opened_on"].input_formats = ["%Y-%m-%d"]

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()

    def clean_opened_on(self):
        opened_on = self.cleaned_data["opened_on"]
        problem = opening_date_problem(opened_on)
        if problem:
            raise forms.ValidationError(problem)
        return opened_on

    def clean(self):
        cleaned = super().clean()
        opened_on = cleaned.get("opened_on")
        if (
            opened_on
            and self.user
            and self.country
            and OpeningReport.objects.filter(
                user=self.user,
                country=self.country,
                opened_on=opened_on,
            ).exists()
        ):
            self.add_error(
                "opened_on",
                "You already reported this opening date for this country.",
            )
        return cleaned
