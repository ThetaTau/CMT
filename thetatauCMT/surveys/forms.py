from django import forms
from django.urls import reverse
from survey.forms import ResponseForm
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


class ResponseForm(ResponseForm):
    def has_next_step(self):
        if not self.survey.is_all_in_one_page():
            if self.step is not None and self.step < self.steps_count - 1:
                return True
        return False

    def next_step_url(self):
        if self.step is not None and self.has_next_step():
            context = {"slug": self.survey.slug, "step": self.step + 1}
            return reverse("surveys:survey-detail-step", kwargs=context)

    def current_step_url(self):
        return reverse(
            "surveys:survey-detail-step",
            kwargs={"slug": self.survey.slug, "step": self.step},
        )
