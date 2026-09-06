import datetime

import pytest
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

from ..models import ReportAttachment, ReportObligation, ReportTemplate, TemplatePrompt, TransitionReport

pytestmark = pytest.mark.django_db


def _obligation(chapter, officer, position_key="treasurer"):
    due_date = datetime.date.today() + datetime.timedelta(days=16)
    return ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        officer=officer,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=14),
        due_date=due_date,
        is_required=True,
        status="open",
    )


def _template():
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    TemplatePrompt.objects.create(
        template=template, order=1, prompt_key="successes", label="Successes?", is_required=True, min_chars=5
    )
    TemplatePrompt.objects.create(
        template=template, order=2, prompt_key="pitfalls", label="Pitfalls?", is_required=False
    )
    return template


# ---------------------------------------------------------------------------
# TransitionsListView
# ---------------------------------------------------------------------------
def test_transitions_list_requires_login(client):
    response = client.get(reverse("transitions:list"))
    assert response.status_code == 302


def test_transitions_list_shows_my_obligations(auto_login_user):
    client, user = auto_login_user()
    chapter = user.chapter
    _obligation(chapter, user)

    response = client.get(reverse("transitions:list"))

    assert response.status_code == 200
    assert "treasurer" in response.content.decode().lower()


def test_transitions_list_does_not_show_someone_elses_obligation(auto_login_user):
    client, user = auto_login_user()
    other_chapter = ChapterFactory()
    other_officer = UserFactory(chapter=other_chapter)
    _obligation(other_chapter, other_officer, position_key="scribe")

    response = client.get(reverse("transitions:list"))

    assert "scribe" not in response.content.decode().lower()


def test_transitions_list_position_filter(auto_login_user):
    client, user = auto_login_user()
    chapter = user.chapter
    _obligation(chapter, user, position_key="treasurer")
    _obligation(chapter, user, position_key="scribe")

    response = client.get(reverse("transitions:list"), {"position_key": "treasurer"})

    # The position dropdown itself always lists every position the viewer
    # holds (including "scribe", so they can switch filters) -- assert on the
    # TABLE CELL specifically, not the whole page body.
    body = response.content.decode()
    assert "<td>Treasurer</td>" in body
    assert "<td>Scribe</td>" not in body


def test_transitions_list_shows_vacant_obligations_to_regent(auto_login_user):
    client, regent = auto_login_user()
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    _obligation(regent.chapter, None, position_key="scribe")

    response = client.get(reverse("transitions:list"))

    assert "Vacant positions" in response.content.decode()


def test_transitions_list_hides_vacant_obligations_from_a_plain_member(auto_login_user):
    client, member = auto_login_user()
    _obligation(member.chapter, None, position_key="scribe")

    response = client.get(reverse("transitions:list"))

    assert "Vacant positions" not in response.content.decode()


# ---------------------------------------------------------------------------
# ComposeReportView
# ---------------------------------------------------------------------------
def test_compose_view_get_renders_form_for_assigned_officer(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.pk}))

    assert response.status_code == 200
    assert TransitionReport.objects.filter(obligation=obligation, author=officer).exists()


def test_compose_view_blocks_a_different_user(auto_login_user):
    client, other_user = auto_login_user()
    _template()
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.pk}))

    assert response.status_code == 302
    assert not TransitionReport.objects.filter(obligation=obligation).exists()


def test_compose_view_save_draft_does_not_require_fields(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {"action": "draft", "prompt_successes": "", "prompt_pitfalls": ""},
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.status == "draft"


def test_compose_view_submit_enforces_required_fields(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {"action": "submit", "prompt_successes": "", "prompt_pitfalls": ""},
    )

    assert response.status_code == 200
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.status == "draft"


def test_compose_view_submit_closes_obligation(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {"action": "submit", "prompt_successes": "we did well this term", "prompt_pitfalls": ""},
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    obligation.refresh_from_db()
    assert report.status == "submitted"
    assert obligation.status == "submitted"


def test_compose_view_editable_after_submission(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {"action": "submit", "prompt_successes": "we did well this term", "prompt_pitfalls": ""},
    )

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {"action": "submit", "prompt_successes": "an updated answer here", "prompt_pitfalls": ""},
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.answers.get(prompt_key="successes").value == "an updated answer here"


def test_compose_view_add_attachment(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {
            "action": "add_attachment",
            "file": SimpleUploadedFile("budget.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            "description": "Budget spreadsheet",
        },
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.attachments.count() == 1


# ---------------------------------------------------------------------------
# AttachmentDeleteView
# ---------------------------------------------------------------------------
def test_attachment_delete_by_author(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {
            "action": "add_attachment",
            "file": SimpleUploadedFile("budget.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            "description": "",
        },
    )
    attachment = ReportAttachment.objects.get()

    response = client.post(reverse("transitions:attachment-delete", kwargs={"pk": attachment.pk}))

    assert response.status_code == 302
    assert not ReportAttachment.objects.filter(pk=attachment.pk).exists()


def test_attachment_delete_blocked_for_non_author(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.pk}),
        {
            "action": "add_attachment",
            "file": SimpleUploadedFile("budget.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            "description": "",
        },
    )
    attachment = ReportAttachment.objects.get()
    client.logout()
    other_client_user = UserFactory(chapter=ChapterFactory())
    client.force_login(other_client_user)

    response = client.post(reverse("transitions:attachment-delete", kwargs={"pk": attachment.pk}))

    assert response.status_code == 302
    assert ReportAttachment.objects.filter(pk=attachment.pk).exists()


# ---------------------------------------------------------------------------
# CloseNAVacantView
# ---------------------------------------------------------------------------
def test_close_na_vacant_by_regent(auto_login_user):
    client, regent = auto_login_user()
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])
    obligation = _obligation(regent.chapter, None, position_key="scribe")

    response = client.post(reverse("transitions:close-vacant", kwargs={"pk": obligation.pk}))

    assert response.status_code == 302
    obligation.refresh_from_db()
    assert obligation.status == "na_vacant"


def test_close_na_vacant_blocked_for_plain_member(auto_login_user):
    client, member = auto_login_user()
    obligation = _obligation(member.chapter, None, position_key="scribe")

    response = client.post(reverse("transitions:close-vacant", kwargs={"pk": obligation.pk}))

    assert response.status_code == 302
    obligation.refresh_from_db()
    assert obligation.status == "open"
