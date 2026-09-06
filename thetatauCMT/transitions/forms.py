"""TRWI-5: the compose form -- one dynamic field per resolved template prompt."""

from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from django import forms

from core.forms import DatePicker

from .models import TAG_CHOICES, FieldType, ReportAttachment, ReportTag


def _field_name(prompt):
    return f"prompt_{prompt.prompt_key}"


class ComposeReportForm(forms.Form):
    """Renders one field per ``TemplatePrompt`` on ``template``, plus a fixed
    ``manual_tags`` field (TRWI-11) -- the author's own tag additions on top
    of whatever ``services.derive_prompt_tags`` derives automatically from
    their answers on submit. ``manual_tags`` can never collide with a
    prompt's own generated field name (always ``prompt_<prompt_key>``, never
    a bare ``prompt_key`` value on its own).

    Required/min/max-chars are enforced only when ``submitting=True`` -- a
    draft save must accept an incomplete form (TRWI-5: "supports save as
    draft and submit").
    """

    manual_tags = forms.MultipleChoiceField(
        required=False, choices=TAG_CHOICES, label="Additional tags", widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, template, submitting=False, **kwargs):
        self.template = template
        self.submitting = submitting
        super().__init__(*args, **kwargs)
        for prompt in template.prompts.all():
            self.fields[_field_name(prompt)] = self._build_field(prompt)
        # Re-insert at the end: the loop above just added the prompt fields
        # to self.fields, and dict insertion order drives render order, so
        # without this manual_tags would render BEFORE the prompts it's
        # declared before them at the class level.
        self.fields["manual_tags"] = self.fields.pop("manual_tags")

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
        """``initial=`` data matching existing answers by ``prompt_key``, plus
        the report's existing manual tags (TRWI-11) -- prompt-derived tags are
        never shown/edited here; they're read-only, re-derived on submit.
        """
        initial = {f"prompt_{answer.prompt_key}": answer.value for answer in report.answers.all()}
        if report.pk:
            initial["manual_tags"] = list(
                report.tags.filter(source=ReportTag.Source.manual.value[0]).values_list("tag", flat=True)
            )
        return initial

    def fields_with_prior_answers(self, prior_answers):
        """``[(BoundField, ReportAnswer_or_None), ...]`` in prompt order
        (TRWI-8) -- ``prior_answers`` is ``services.get_prior_answers``'s
        ``{prompt_key: ReportAnswer}`` return shape; pairing them with this
        form's own fields lives here (not in services.py, which stays
        Django-form-agnostic) since this class already owns the prompt <->
        field-name mapping.
        """
        return [
            (self[_field_name(prompt)], prior_answers.get(prompt.prompt_key)) for prompt in self.template.prompts.all()
        ]

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

    def manual_tags_data(self):
        """``[tag, ...]`` ready for ``services.set_manual_tags`` (TRWI-11)."""
        return self.cleaned_data.get("manual_tags") or []


class ReportAttachmentForm(forms.ModelForm):
    class Meta:
        model = ReportAttachment
        fields = ["file", "description"]


class ComplianceFilterFormHelper(FormHelper):
    """Crispy helper for the chapter dashboard's obligation filter (TRWI-9).

    ``form_tag = False`` because ``_partials/collapsible_filter.html``
    supplies its own ``<form method="get">`` wrapper -- mirrors
    ``forms.forms.RoleChangeListFormHelper``'s exact style.
    """

    form_method = "GET"
    form_id = "compliance-filter-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False

    def __init__(self, form=None):
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter',
                Row(
                    InlineField("position_key"),
                    InlineField("status"),
                    InlineField("cycle"),
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        # NOT super().__init__(form=form): FormHelper.__init__ overwrites
        # self.layout with its own build_default_layout(form) whenever
        # form is not None -- calling it with no args keeps our own custom
        # Layout above intact while still initializing self.attrs/inputs.
        super().__init__()


class ComplianceRateFilterFormHelper(FormHelper):
    """Crispy helper for the regional/national rates dashboard filter
    (TRWI-9) -- no ``status`` field (there's no single obligation to show a
    status for; each row is a whole chapter's aggregate).
    """

    form_method = "GET"
    form_id = "compliance-rate-filter-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False

    def __init__(self, form=None):
        fields = [InlineField("position_key")]
        if form is not None and "region" in form.fields:
            fields.append(InlineField("region"))
        fields.append(InlineField("cycle"))
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter',
                Row(
                    *fields,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__()


class SearchFilterFormHelper(FormHelper):
    """Crispy helper for the search view's filter (TRWI-11) -- ``chapter``/
    ``region`` only appear for viewers whose search spans more than their
    own chapter (see ``filters.NationalSearchFilter``).
    """

    form_method = "GET"
    form_id = "search-filter-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False

    def __init__(self, form=None):
        fields = [InlineField("q"), InlineField("position_key")]
        if form is not None and "chapter" in form.fields:
            fields.append(InlineField("chapter"))
        if form is not None and "region" in form.fields:
            fields.append(InlineField("region"))
        fields.append(InlineField("tag"))
        fields.append(InlineField("cycle"))
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter',
                Row(
                    *fields,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__()


class TrendFilterFormHelper(FormHelper):
    """Crispy helper for the national trend view's filter (TRWI-11)."""

    form_method = "GET"
    form_id = "trend-filter-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False

    def __init__(self, form=None):
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter',
                Row(
                    InlineField("position_key"),
                    InlineField("region"),
                    InlineField("cycle"),
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__()
