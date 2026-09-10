"""TRWI-5: the compose form -- one dynamic field per resolved template prompt."""

from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from django import forms

from core.forms import DatePicker, ListSelect2Multiple, Select2ListCreateMultipleChoiceField

from .models import FieldType, ReportAttachment, ReportContact, ReportKeyDate, ReportTag, TransitionTag


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

    manual_tags = Select2ListCreateMultipleChoiceField(
        required=False,
        queryset=TransitionTag.objects.all(),
        label="Additional tags",
        help_text=(
            "Start typing to search existing tags, you do NOT have to pick from the list. "
            "If nothing matches, just type your own tag and press Enter (or Tab) to add it."
        ),
        widget=ListSelect2Multiple(url="transitions:tag-autocomplete"),
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
        # This form has no ``self.instance`` (it isn't a ModelForm), so
        # unlike jobs.forms.set_multiple_choices_initial, the already-selected
        # tag names come from initial_from_report's own initial= dict instead
        # of a real relation -- choices need those names too, or the widget
        # would not know they're valid/selected on first render.
        selected_tags = self.initial.get("manual_tags") or []
        if selected_tags:
            self.fields["manual_tags"].choices = [(name, name) for name in selected_tags]

    @staticmethod
    def _build_field(prompt):
        if prompt.field_type == FieldType.date.value[0]:
            field = forms.DateField(
                required=False,
                widget=DatePicker(options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"}),
            )
        else:
            attrs = {"rows": 4}
            if prompt.tag == "systems":
                # 2026-09 structured-content pass: real past transition docs
                # pasted actual account passwords into exactly this kind of
                # prompt despite the help text already saying not to (see
                # transitions-app.md TRWI-13) -- data-warn-credentials hooks
                # up static/js/transitions_compose.js's heuristic inline
                # warning, external/CSP-safe, never blocks submission.
                attrs["data-warn-credentials"] = "1"
            field = forms.CharField(required=False, widget=forms.Textarea(attrs=attrs))
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
        """``[tag_name, ...]`` ready for ``services.set_manual_tags`` (TRWI-11).

        ``Select2ListCreateMultipleChoiceField.to_python`` returns a mix of
        raw pks (values whose submitted ``<option>`` used the tag's id, e.g.
        one just created via the autocomplete, or re-picked from a search)
        and ``TransitionTag`` instances (values submitted by name, e.g. an
        untouched pre-selected option -- see the ``choices=`` set in
        ``__init__``), so both forms are normalized to their ``.name`` here.
        """
        values = self.cleaned_data.get("manual_tags") or []
        names = []
        for value in values:
            if isinstance(value, TransitionTag):
                names.append(value.name)
            else:
                names.append(TransitionTag.objects.get(pk=value).name)
        return names


class ReportAttachmentForm(forms.ModelForm):
    class Meta:
        model = ReportAttachment
        fields = ["file", "description", "category"]


class ReportContactForm(forms.ModelForm):
    """One row of the compose page's Contacts formset (TRWI-13 proposal).

    ``name`` is the only required field -- Django's own formset machinery
    (``empty_permitted`` on extra forms) already skips a row left entirely
    blank, so a row is only validated once SOMETHING in it changes.
    """

    class Meta:
        model = ReportContact
        fields = ["name", "role_or_context", "phone", "email", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class ReportKeyDateForm(forms.ModelForm):
    """One row of the compose page's Key Dates formset (TRWI-13 proposal)."""

    class Meta:
        model = ReportKeyDate
        fields = ["label", "timing", "lead_time_note"]


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
