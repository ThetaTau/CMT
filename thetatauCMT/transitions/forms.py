"""TRWI-5: the compose form -- one dynamic field per resolved template prompt."""

from django import forms

from core.forms import DatePicker

from .models import FieldType, ReportAttachment


def _field_name(prompt):
    return f"prompt_{prompt.prompt_key}"


class ComposeReportForm(forms.Form):
    """Renders one field per ``TemplatePrompt`` on ``template``.

    Required/min/max-chars are enforced only when ``submitting=True`` -- a
    draft save must accept an incomplete form (TRWI-5: "supports save as
    draft and submit").
    """

    def __init__(self, *args, template, submitting=False, **kwargs):
        self.template = template
        self.submitting = submitting
        super().__init__(*args, **kwargs)
        for prompt in template.prompts.all():
            self.fields[_field_name(prompt)] = self._build_field(prompt)

    @staticmethod
    def _build_field(prompt):
        if prompt.field_type == FieldType.date.value[0]:
            field = forms.DateField(
                required=False,
                widget=DatePicker(options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"}),
            )
        else:
            field = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
        field.label = prompt.label
        field.help_text = prompt.help_text
        return field

    @classmethod
    def initial_from_report(cls, report):
        """``initial=`` data matching existing answers by ``prompt_key``."""
        return {f"prompt_{answer.prompt_key}": answer.value for answer in report.answers.all()}

    def clean(self):
        cleaned_data = super().clean()
        if self.submitting:
            for prompt in self.template.prompts.all():
                field_name = _field_name(prompt)
                value = (cleaned_data.get(field_name) or "").strip()
                if prompt.is_required and not value:
                    self.add_error(field_name, "This field is required.")
                    continue
                if value and prompt.min_chars and len(value) < prompt.min_chars:
                    self.add_error(field_name, f"Please write at least {prompt.min_chars} characters.")
                if value and prompt.max_chars and len(value) > prompt.max_chars:
                    self.add_error(field_name, f"Please keep this under {prompt.max_chars} characters.")
        return cleaned_data

    def answers_data(self):
        """``[(prompt, value), ...]`` in prompt order, ready to save."""
        return [
            (prompt, (self.cleaned_data.get(_field_name(prompt)) or "").strip())
            for prompt in self.template.prompts.all()
        ]


class ReportAttachmentForm(forms.ModelForm):
    class Meta:
        model = ReportAttachment
        fields = ["file", "description"]
