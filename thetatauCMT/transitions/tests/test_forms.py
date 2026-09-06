import datetime

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

from ..forms import ComposeReportForm
from ..models import ReportAnswer, ReportObligation, ReportTemplate, TemplatePrompt, TransitionReport

pytestmark = pytest.mark.django_db


def _template_with_prompts():
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    TemplatePrompt.objects.create(
        template=template, order=1, prompt_key="successes", label="Successes?", is_required=True, min_chars=5
    )
    TemplatePrompt.objects.create(
        template=template, order=2, prompt_key="pitfalls", label="Pitfalls?", is_required=False, max_chars=10
    )
    TemplatePrompt.objects.create(
        template=template, order=3, prompt_key="key_dates", label="Key dates?", field_type="date", is_required=False
    )
    return template


def test_compose_form_builds_one_field_per_prompt():
    template = _template_with_prompts()
    form = ComposeReportForm(template=template)
    assert set(form.fields) == {"prompt_successes", "prompt_pitfalls", "prompt_key_dates"}


def test_compose_form_date_field_type_uses_date_field():
    from django import forms as django_forms

    template = _template_with_prompts()
    form = ComposeReportForm(template=template)
    assert isinstance(form.fields["prompt_key_dates"], django_forms.DateField)
    assert isinstance(form.fields["prompt_successes"], django_forms.CharField)


def test_compose_form_draft_save_skips_required_and_bounds():
    template = _template_with_prompts()
    form = ComposeReportForm(data={"prompt_successes": "", "prompt_pitfalls": ""}, template=template, submitting=False)
    assert form.is_valid()


def test_compose_form_submit_enforces_required():
    template = _template_with_prompts()
    form = ComposeReportForm(data={"prompt_successes": "", "prompt_pitfalls": ""}, template=template, submitting=True)
    assert not form.is_valid()
    assert "prompt_successes" in form.errors


def test_compose_form_submit_enforces_min_chars():
    template = _template_with_prompts()
    form = ComposeReportForm(data={"prompt_successes": "hi", "prompt_pitfalls": ""}, template=template, submitting=True)
    assert not form.is_valid()
    assert "prompt_successes" in form.errors


def test_compose_form_submit_enforces_max_chars():
    template = _template_with_prompts()
    form = ComposeReportForm(
        data={"prompt_successes": "long enough answer", "prompt_pitfalls": "way too long for the limit"},
        template=template,
        submitting=True,
    )
    assert not form.is_valid()
    assert "prompt_pitfalls" in form.errors


def test_compose_form_submit_passes_with_valid_data():
    template = _template_with_prompts()
    form = ComposeReportForm(
        data={"prompt_successes": "long enough answer", "prompt_pitfalls": "short"},
        template=template,
        submitting=True,
    )
    assert form.is_valid()


def test_compose_form_answers_data_returns_stripped_values_in_order():
    template = _template_with_prompts()
    form = ComposeReportForm(
        data={"prompt_successes": "  padded  ", "prompt_pitfalls": ""}, template=template, submitting=False
    )
    assert form.is_valid()
    data = form.answers_data()
    assert [prompt.prompt_key for prompt, _value in data] == ["successes", "pitfalls", "key_dates"]
    assert dict((p.prompt_key, v) for p, v in data)["successes"] == "padded"


def test_compose_form_initial_from_report_matches_by_prompt_key():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    template = _template_with_prompts()
    due_date = datetime.date.today() + datetime.timedelta(days=10)
    obligation = ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=officer,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=14),
        due_date=due_date,
        status="open",
    )
    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="did well")

    initial = ComposeReportForm.initial_from_report(report)

    assert initial == {"prompt_successes": "did well"}


def test_compose_form_fields_with_prior_answers_pairs_by_prompt_key():
    template = _template_with_prompts()
    form = ComposeReportForm(template=template)
    prior_answer = ReportAnswer(prompt_key="successes", value="ask the RD")

    paired = dict((field.name, prior) for field, prior in form.fields_with_prior_answers({"successes": prior_answer}))

    assert paired["prompt_successes"] is prior_answer
    assert paired["prompt_pitfalls"] is None
    assert paired["prompt_key_dates"] is None


def test_compose_form_fields_with_prior_answers_empty_dict_pairs_everything_with_none():
    template = _template_with_prompts()
    form = ComposeReportForm(template=template)

    paired = form.fields_with_prior_answers({})

    assert all(prior is None for _field, prior in paired)
    assert [field.name for field, _prior in paired] == ["prompt_successes", "prompt_pitfalls", "prompt_key_dates"]
