from django import forms
from .models import DepledgeSurvey


class DepledgeSurveyForm(forms.ModelForm):
    class Meta:
        model = DepledgeSurvey
        fields = [
            "reason",
            "reason_other",
            "decided",
            "decided_other",
            "enjoyed",
            "improve",
            "extra_notes",
            "contact",
        ]

    def clean(self):
        super().clean()
        reason_other = self.cleaned_data.get("reason_other", "")
        if self.cleaned_data.get("reason") == "other" and reason_other == "":
            self.add_error(
                "reason_other",
                forms.ValidationError("Please provide other reason for depledging"),
            )
        decided_other = self.cleaned_data.get("decided_other")
        if self.cleaned_data.get("decided") == "other" and decided_other == "":
            self.add_error(
                "decided_other",
                forms.ValidationError("Please provide other depledging decided"),
            )
