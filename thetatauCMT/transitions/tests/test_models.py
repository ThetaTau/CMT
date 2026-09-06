import datetime

import pytest
from django.db import IntegrityError

from core.models import ADVISOR_ROLES, CHAPTER_OFFICER_REQUIRED, COMMITTEE_CHAIR, COUNCIL, NATIONAL_OFFICER
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from ..models import (
    POSITION_KEY_CHOICES,
    HandoffNotice,
    PositionOverride,
    PositionType,
    ReportAcknowledgement,
    ReportAnswer,
    ReportAttachment,
    ReportObligation,
    ReportTag,
    ReportTemplate,
    TemplatePrompt,
    TransitionReport,
    position_type_for_key,
)

pytestmark = pytest.mark.django_db


def test_position_key_choices_excludes_advisor_roles():
    keys = {key for key, _label in POSITION_KEY_CHOICES}
    assert keys.isdisjoint(ADVISOR_ROLES)


def test_position_key_choices_count_matches_core_models():
    # 7 CHAPTER_OFFICER_REQUIRED + 8 COUNCIL + 10 NATIONAL_OFFICER + 18 remaining
    # COMMITTEE_CHAIR (20 total minus the 2 already in CHAPTER_OFFICER_REQUIRED).
    expected = len(CHAPTER_OFFICER_REQUIRED | COUNCIL | NATIONAL_OFFICER | COMMITTEE_CHAIR)
    assert len(POSITION_KEY_CHOICES) == expected


def test_position_type_for_key_chapter_officer_positions():
    for key in CHAPTER_OFFICER_REQUIRED:
        assert position_type_for_key(key) == PositionType.chapter_officer


def test_position_type_for_key_pledge_educator_and_risk_mgmt_chair_are_chapter_officer():
    # These two are in core.models.COMMITTEE_CHAIR too, but decision B5 puts
    # them in the chapter_officer bucket (required, core prompt set).
    assert position_type_for_key("pledge/new member educator") == PositionType.chapter_officer
    assert position_type_for_key("risk management chair") == PositionType.chapter_officer


def test_position_type_for_key_council_and_national_officer():
    assert position_type_for_key("grand regent") == PositionType.council
    assert position_type_for_key("regional director") == PositionType.national_officer


def test_position_type_for_key_remaining_committee_chair():
    assert position_type_for_key("committee chair") == PositionType.committee_chair


def test_position_type_for_key_advisor_roles_are_out_of_scope():
    for key in ADVISOR_ROLES:
        assert position_type_for_key(key) is None


def test_position_type_for_key_unknown_key():
    assert position_type_for_key("not a real position") is None


def test_position_override_str():
    override = PositionOverride.objects.create(position_key="treasurer", status="excluded")
    assert str(override) == "treasurer (excluded)"


def test_position_override_position_key_is_unique():
    PositionOverride.objects.create(position_key="treasurer", status="excluded")
    with pytest.raises(Exception):
        PositionOverride.objects.create(position_key="treasurer", status="optional")


# ---------------------------------------------------------------------------
# ReportTemplate / TemplatePrompt (TRWI-2)
# ---------------------------------------------------------------------------
def test_report_template_defaults_to_active_version_1():
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    assert template.is_active is True
    assert template.version == 1
    assert template.position_key == ""


def test_report_template_position_type_and_key_together_unique():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", position_key="", name="Chapter Officer Report")
    with pytest.raises(IntegrityError):
        ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", position_key="", name="Duplicate")


def test_report_template_allows_a_position_specific_override_alongside_the_type_default():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", position_key="", name="Chapter Officer Report")
    # Same type, but a specific position_key -- different resolution tier, allowed.
    override = ReportTemplate.objects.create(
        position_type="CHAPTER_OFFICER", position_key="treasurer", name="Treasurer Report"
    )
    assert override.pk is not None


def test_template_prompt_prompt_key_unique_within_template_only():
    template_a = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="A")
    template_b = ReportTemplate.objects.create(position_type="COUNCIL", name="B")
    TemplatePrompt.objects.create(template=template_a, prompt_key="successes", label="Successes?")
    # Same prompt_key on a DIFFERENT template is fine -- the key is reused by design.
    TemplatePrompt.objects.create(template=template_b, prompt_key="successes", label="Successes?")

    with pytest.raises(IntegrityError):
        TemplatePrompt.objects.create(template=template_a, prompt_key="successes", label="Duplicate")


def test_template_prompt_str():
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="A")
    prompt = TemplatePrompt.objects.create(template=template, prompt_key="successes", label="Successes?")
    assert str(prompt) == f"successes ({template})"


# ---------------------------------------------------------------------------
# TransitionReport / ReportAnswer / ReportAttachment (TRWI-5)
# ---------------------------------------------------------------------------
def _obligation(chapter, officer):
    due_date = datetime.date.today() + datetime.timedelta(days=16)
    return ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=officer,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=14),
        due_date=due_date,
        is_required=True,
        status="open",
    )


def test_transition_report_defaults_to_draft():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")

    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )

    assert report.status == "draft"
    assert report.submitted_at is None
    assert str(report) == f"treasurer ({chapter}) -- draft"


def test_transition_report_obligation_is_one_to_one():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )

    with pytest.raises(IntegrityError):
        TransitionReport.objects.create(
            obligation=obligation,
            chapter=chapter,
            position_type="CHAPTER_OFFICER",
            position_key="treasurer",
            author=officer,
            template=template,
            template_version=1,
        )


def test_report_answer_unique_per_prompt_key_within_report():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )
    ReportAnswer.objects.create(report=report, prompt_key="successes", prompt_label_snapshot="Successes?", value="a")

    with pytest.raises(IntegrityError):
        ReportAnswer.objects.create(
            report=report, prompt_key="successes", prompt_label_snapshot="Successes?", value="b"
        )


def test_report_answer_prompt_is_nullable():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )
    answer = ReportAnswer.objects.create(
        report=report, prompt=None, prompt_key="successes", prompt_label_snapshot="Successes?", value="a"
    )
    assert answer.prompt is None
    assert str(answer) == f"successes ({report})"


def test_report_attachment_rejects_disallowed_file_type():
    from django.core.exceptions import ValidationError
    from django.core.files.uploadedfile import SimpleUploadedFile

    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
    )
    attachment = ReportAttachment(
        report=report,
        file=SimpleUploadedFile("script.exe", b"not a real exe", content_type="application/x-msdownload"),
        uploaded_by=officer,
    )
    with pytest.raises(ValidationError):
        attachment.full_clean()


# ---------------------------------------------------------------------------
# ReportAcknowledgement / HandoffNotice (TRWI-7)
# ---------------------------------------------------------------------------
def _report(chapter, officer):
    obligation = _obligation(chapter, officer)
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    return TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=officer,
        template=template,
        template_version=1,
        status="submitted",
    )


def test_report_acknowledgement_unique_per_user_and_report():
    chapter = ChapterFactory()
    author = UserFactory(chapter=chapter)
    reader = UserFactory(chapter=chapter)
    report = _report(chapter, author)
    ReportAcknowledgement.objects.create(report=report, user=reader)

    with pytest.raises(IntegrityError):
        ReportAcknowledgement.objects.create(report=report, user=reader)


def test_report_acknowledgement_str():
    chapter = ChapterFactory()
    author = UserFactory(chapter=chapter)
    reader = UserFactory(chapter=chapter)
    report = _report(chapter, author)
    ack = ReportAcknowledgement.objects.create(report=report, user=reader)

    assert str(ack) == f"{reader} acknowledged {report}"


def test_handoff_notice_one_per_role_change():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    role_change = UserRoleChange.objects.create(
        user=officer,
        role="treasurer",
        start=datetime.date.today(),
        end=datetime.date.today() + datetime.timedelta(days=180),
    )
    HandoffNotice.objects.create(role_change=role_change)

    with pytest.raises(IntegrityError):
        HandoffNotice.objects.create(role_change=role_change)


def test_handoff_notice_str():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    role_change = UserRoleChange.objects.create(
        user=officer,
        role="treasurer",
        start=datetime.date.today(),
        end=datetime.date.today() + datetime.timedelta(days=180),
    )
    notice = HandoffNotice.objects.create(role_change=role_change)

    assert str(notice) == f"Handoff notice sent for {role_change}"


# ---------------------------------------------------------------------------
# ReportTag (TRWI-11)
# ---------------------------------------------------------------------------
def test_report_tag_unique_per_report_and_tag():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    report = _report(chapter, officer)
    ReportTag.objects.create(report=report, tag="risk", source="manual")

    with pytest.raises(IntegrityError):
        ReportTag.objects.create(report=report, tag="risk", source="prompt")


def test_report_tag_str():
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    report = _report(chapter, officer)
    tag = ReportTag.objects.create(report=report, tag="risk", source="manual")

    assert str(tag) == f"risk ({report})"


def test_report_tag_allows_the_same_tag_on_different_reports():
    chapter = ChapterFactory()
    other_chapter = ChapterFactory()
    report_1 = _report(chapter, UserFactory(chapter=chapter))
    other_obligation = _obligation(other_chapter, UserFactory(chapter=other_chapter))
    # Reuses report_1's template (rather than a second _report() call) --
    # ReportTemplate has a unique (position_type, position_key) constraint,
    # and _report() always creates a fresh blank-position_key template.
    report_2 = TransitionReport.objects.create(
        obligation=other_obligation,
        chapter=other_chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=other_obligation.officer,
        template=report_1.template,
        template_version=1,
        status="submitted",
    )
    ReportTag.objects.create(report=report_1, tag="risk", source="manual")

    ReportTag.objects.create(report=report_2, tag="risk", source="manual")  # must not raise

    assert ReportTag.objects.filter(tag="risk").count() == 2
