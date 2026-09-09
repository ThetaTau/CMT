import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .. import services
from ..models import ReportAttachment, ReportObligation, ReportTemplate, TemplatePrompt, TransitionReport

pytestmark = pytest.mark.django_db


def _empty_formsets_data():
    """Zero-row management-form data for the compose view's Contacts/Key
    Dates formsets (TRWI-13 proposal) -- every POST to ``transitions:compose``
    must include this, or ``formset.is_valid()`` raises inside the
    ``management_form`` property instead of just failing validation.
    """
    data = {}
    for prefix in ("contacts", "key_dates"):
        data[f"{prefix}-TOTAL_FORMS"] = "0"
        data[f"{prefix}-INITIAL_FORMS"] = "0"
        data[f"{prefix}-MIN_NUM_FORMS"] = "0"
        data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    return data


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


def _report(chapter, position_key, author, status="submitted", due_date=None):
    due_date = due_date or datetime.date.today() + datetime.timedelta(days=10)
    obligation = ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        officer=author,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=14),
        due_date=due_date,
        is_required=True,
        status="open",
    )
    template, _created = ReportTemplate.objects.get_or_create(
        position_type="CHAPTER_OFFICER", position_key=position_key, defaults={"name": f"{position_key} report"}
    )
    return TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        author=author,
        template=template,
        template_version=1,
        status=status,
        # Matches submit_report's own invariant -- see the identical comment
        # on test_services.py's own _report() helper.
        submitted_at=timezone.now() if status == "submitted" else None,
    )


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
# TransitionsListView -- readable_reports / scope filter (TRWI-6)
# ---------------------------------------------------------------------------
def test_transitions_list_shows_readable_reports_for_a_successor(auto_login_user):
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter))

    response = client.get(reverse("transitions:list"))

    body = response.content.decode()
    assert "Reports you can read" in body
    assert "<td>Treasurer</td>" in body


def test_transitions_list_hides_someone_elses_draft_from_a_successor(auto_login_user):
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter), status="draft")

    response = client.get(reverse("transitions:list"))

    assert "No other Transition Reports are visible to you yet." in response.content.decode()


def test_transitions_list_hides_scope_filter_for_a_regent(auto_login_user):
    client, regent = auto_login_user()
    regent.current_roles = ["regent"]
    regent.save(update_fields=["current_roles"])

    response = client.get(reverse("transitions:list"))

    assert "My chapter only" not in response.content.decode()


def test_transitions_list_scope_filter_shown_and_narrows_an_rds_view(auto_login_user):
    client, rd = auto_login_user()
    other_chapter = ChapterFactory()
    other_chapter.region.directors.add(rd)
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))

    response = client.get(reverse("transitions:list"))
    body = response.content.decode()
    assert "My chapter only" in body
    assert "<td>Treasurer</td>" in body

    response = client.get(reverse("transitions:list"), {"scope": "chapter"})
    assert "<td>Treasurer</td>" not in response.content.decode()


def test_transitions_list_shows_handoff_packet_link_for_a_held_position(auto_login_user):
    client, treasurer = auto_login_user()
    treasurer.current_roles = ["treasurer"]
    treasurer.save(update_fields=["current_roles"])

    response = client.get(reverse("transitions:list"))

    assert "Treasurer handoff packet" in response.content.decode()


def test_transitions_list_hides_handoff_packet_link_when_holding_no_in_scope_position(auto_login_user):
    client, member = auto_login_user()

    response = client.get(reverse("transitions:list"))

    assert "handoff packet" not in response.content.decode()


# ---------------------------------------------------------------------------
# HandoffPacketView
# ---------------------------------------------------------------------------
def test_handoff_packet_view_requires_login(client):
    chapter = ChapterFactory()
    response = client.get(reverse("transitions:packet", args=[chapter.pk, "treasurer"]))
    assert response.status_code == 302


def test_handoff_packet_view_shows_predecessor_reports(auto_login_user):
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter))

    response = client.get(reverse("transitions:packet", args=[successor.chapter.pk, "treasurer"]))

    assert response.status_code == 200
    assert "Mark as read" in response.content.decode()


def test_handoff_packet_view_shows_a_report_submitted_many_years_ago(auto_login_user):
    # TRWI-10: full history, no retention window -- a decade-old report is
    # still shown, not hidden by any time-based cutoff.
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    old_report = _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter))
    old_report.submitted_at = timezone.now() - datetime.timedelta(days=3650)
    old_report.save(update_fields=["submitted_at"])

    response = client.get(reverse("transitions:packet", args=[successor.chapter.pk, "treasurer"]))

    assert response.status_code == 200
    assert "Mark as read" in response.content.decode()


def test_handoff_packet_view_excludes_the_viewers_own_report(auto_login_user):
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    _report(successor.chapter, "treasurer", successor)

    response = client.get(reverse("transitions:packet", args=[successor.chapter.pk, "treasurer"]))

    assert "No Transition Reports are available to read" in response.content.decode()


def test_handoff_packet_view_empty_when_not_entitled(auto_login_user):
    client, member = auto_login_user()
    other_chapter = ChapterFactory()
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))

    response = client.get(reverse("transitions:packet", args=[other_chapter.pk, "treasurer"]))

    assert response.status_code == 200
    assert "No Transition Reports are available to read" in response.content.decode()


def test_handoff_packet_view_shows_read_badge_after_acknowledging(auto_login_user):
    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    report = _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter))

    client.post(reverse("transitions:acknowledge", args=[report.public_id]))
    response = client.get(reverse("transitions:packet", args=[successor.chapter.pk, "treasurer"]))

    body = response.content.decode()
    assert "Read</span>" in body
    assert "Mark as read" not in body


# ---------------------------------------------------------------------------
# AcknowledgeReportView
# ---------------------------------------------------------------------------
def test_acknowledge_view_records_acknowledgment_for_an_entitled_reader(auto_login_user):
    from ..models import ReportAcknowledgement

    client, successor = auto_login_user()
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    report = _report(successor.chapter, "treasurer", UserFactory(chapter=successor.chapter))

    response = client.post(reverse("transitions:acknowledge", args=[report.public_id]))

    assert response.status_code == 302
    assert ReportAcknowledgement.objects.filter(report=report, user=successor).exists()


def test_acknowledge_view_denies_an_unentitled_user(auto_login_user):
    from ..models import ReportAcknowledgement

    client, member = auto_login_user()
    other_chapter = ChapterFactory()
    report = _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))

    response = client.post(reverse("transitions:acknowledge", args=[report.public_id]))

    assert response.status_code == 302
    assert not ReportAcknowledgement.objects.filter(report=report, user=member).exists()


# ---------------------------------------------------------------------------
# ComposeReportView
# ---------------------------------------------------------------------------
def test_compose_view_get_renders_form_for_assigned_officer(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 200
    assert TransitionReport.objects.filter(obligation=obligation, author=officer).exists()


def test_compose_view_blocks_a_different_user(auto_login_user):
    client, other_user = auto_login_user()
    _template()
    chapter = ChapterFactory()
    officer = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 302
    assert not TransitionReport.objects.filter(obligation=obligation).exists()


def test_compose_view_save_draft_does_not_require_fields(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {"action": "draft", "prompt_successes": "", "prompt_pitfalls": "", **_empty_formsets_data()},
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.status == "draft"


def test_compose_view_submit_enforces_required_fields(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {"action": "submit", "prompt_successes": "", "prompt_pitfalls": "", **_empty_formsets_data()},
    )

    assert response.status_code == 200
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.status == "draft"


def test_compose_view_submit_closes_obligation(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "submit",
            "prompt_successes": "we did well this term",
            "prompt_pitfalls": "",
            **_empty_formsets_data(),
        },
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
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "submit",
            "prompt_successes": "we did well this term",
            "prompt_pitfalls": "",
            **_empty_formsets_data(),
        },
    )

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "submit",
            "prompt_successes": "an updated answer here",
            "prompt_pitfalls": "",
            **_empty_formsets_data(),
        },
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.answers.get(prompt_key="successes").value == "an updated answer here"


# ---------------------------------------------------------------------------
# ComposeReportView -- prior answers while composing (TRWI-8)
# ---------------------------------------------------------------------------
def _predecessor_report(chapter, template, answer_value="ask the RD"):
    # A distinct, already-elapsed term -- _obligation()'s fixed due_date
    # would otherwise collide with the successor's own (chapter, position_key,
    # term_start, term_end) unique constraint.
    past_due_date = datetime.date.today() - datetime.timedelta(days=200)
    obligation = ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=UserFactory(chapter=chapter),
        term_start=past_due_date - datetime.timedelta(days=166),
        term_end=past_due_date + datetime.timedelta(days=14),
        due_date=past_due_date,
        is_required=True,
        status="submitted",
    )
    report = TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        author=obligation.officer,
        template=template,
        template_version=1,
        status="submitted",
    )
    report.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value=answer_value)
    return report


def test_compose_view_shows_predecessors_answer_inline(auto_login_user):
    client, successor = auto_login_user()
    template = _template()
    _predecessor_report(successor.chapter, template)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    obligation = _obligation(successor.chapter, successor)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    body = response.content.decode()
    assert "What your predecessor said" in body
    assert "ask the RD" in body


def test_compose_view_hides_prior_answer_section_when_no_predecessor(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert "What your predecessor said" not in response.content.decode()


def test_compose_view_never_prefills_the_field_with_the_predecessors_answer(auto_login_user):
    client, successor = auto_login_user()
    template = _template()
    _predecessor_report(successor.chapter, template)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    obligation = _obligation(successor.chapter, successor)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    # The predecessor's text appears (in the collapsible display), but never
    # as the actual textarea CONTENT for the successor's own blank field.
    assert ">ask the RD</textarea>" not in response.content.decode()


def test_compose_view_prior_answer_is_collapsed_by_default(auto_login_user):
    client, successor = auto_login_user()
    template = _template()
    _predecessor_report(successor.chapter, template)
    successor.current_roles = ["treasurer"]
    successor.save(update_fields=["current_roles"])
    obligation = _obligation(successor.chapter, successor)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert '<details class="mb-3 text-muted">' in response.content.decode()


def test_compose_view_add_attachment(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
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
# ComposeReportView -- contacts / key dates formsets (TRWI-13 proposal)
# ---------------------------------------------------------------------------
def test_compose_view_get_shows_one_blank_row_and_an_empty_form_template(auto_login_user):
    """extra=1 always; the page's own JS clones the rendered empty_form
    (asserted here via its __prefix__ placeholder) to add further rows, so
    there is no fixed limit on how many contacts/dates can be entered.
    """
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 200
    assert len(response.context["contacts_formset"].forms) == 1
    assert len(response.context["key_dates_formset"].forms) == 1
    body = response.content.decode()
    assert 'id="contacts-empty-form"' in body
    assert 'id="key_dates-empty-form"' in body
    assert "contacts-__prefix__-name" in body


def test_compose_view_saves_contacts_and_key_dates(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "draft",
            "prompt_successes": "",
            "prompt_pitfalls": "",
            "contacts-TOTAL_FORMS": "1",
            "contacts-INITIAL_FORMS": "0",
            "contacts-MIN_NUM_FORMS": "0",
            "contacts-MAX_NUM_FORMS": "1000",
            "contacts-0-name": "Joe Krauskopf",
            "contacts-0-phone": "(650)575-4242",
            "contacts-0-notes": "Holds the tabling stuff",
            "key_dates-TOTAL_FORMS": "1",
            "key_dates-INITIAL_FORMS": "0",
            "key_dates-MIN_NUM_FORMS": "0",
            "key_dates-MAX_NUM_FORMS": "1000",
            "key_dates-0-label": "IFC dues",
            "key_dates-0-timing": "Oct 1",
            "key_dates-0-lead_time_note": "Start collecting Sept 1",
        },
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.contacts.count() == 1
    assert report.contacts.get().name == "Joe Krauskopf"
    assert report.key_dates.count() == 1
    assert report.key_dates.get().label == "IFC dues"


def test_compose_view_invalid_contact_blocks_the_whole_save(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "draft",
            "prompt_successes": "should not be saved",
            "prompt_pitfalls": "",
            "contacts-TOTAL_FORMS": "1",
            "contacts-INITIAL_FORMS": "0",
            "contacts-MIN_NUM_FORMS": "0",
            "contacts-MAX_NUM_FORMS": "1000",
            "contacts-0-name": "",
            "contacts-0-phone": "(650)575-4242",
            "key_dates-TOTAL_FORMS": "0",
            "key_dates-INITIAL_FORMS": "0",
            "key_dates-MIN_NUM_FORMS": "0",
            "key_dates-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 200
    report = TransitionReport.objects.get(obligation=obligation)
    assert report.contacts.count() == 0
    assert not report.answers.filter(prompt_key="successes", value="should not be saved").exists()


def test_compose_view_deletes_an_existing_contact(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    report = services.get_or_create_report(obligation)
    contact = report.contacts.create(name="Old Contact")

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "draft",
            "prompt_successes": "",
            "prompt_pitfalls": "",
            "contacts-TOTAL_FORMS": "1",
            "contacts-INITIAL_FORMS": "1",
            "contacts-MIN_NUM_FORMS": "0",
            "contacts-MAX_NUM_FORMS": "1000",
            "contacts-0-id": str(contact.pk),
            "contacts-0-name": "Old Contact",
            "contacts-0-DELETE": "on",
            "key_dates-TOTAL_FORMS": "0",
            "key_dates-INITIAL_FORMS": "0",
            "key_dates-MIN_NUM_FORMS": "0",
            "key_dates-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 302
    assert not report.contacts.filter(pk=contact.pk).exists()


# ---------------------------------------------------------------------------
# AttachmentDeleteView
# ---------------------------------------------------------------------------
def test_attachment_delete_by_author(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "add_attachment",
            "file": SimpleUploadedFile("budget.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            "description": "",
        },
    )
    attachment = ReportAttachment.objects.get()

    response = client.post(reverse("transitions:attachment-delete", kwargs={"pk": attachment.public_id}))

    assert response.status_code == 302
    assert not ReportAttachment.objects.filter(pk=attachment.pk).exists()


def test_attachment_delete_blocked_for_non_author(auto_login_user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
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

    response = client.post(reverse("transitions:attachment-delete", kwargs={"pk": attachment.public_id}))

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

    response = client.post(reverse("transitions:close-vacant", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 302
    obligation.refresh_from_db()
    assert obligation.status == "na_vacant"


def test_close_na_vacant_blocked_for_plain_member(auto_login_user):
    client, member = auto_login_user()
    obligation = _obligation(member.chapter, None, position_key="scribe")

    response = client.post(reverse("transitions:close-vacant", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 302
    obligation.refresh_from_db()
    assert obligation.status == "open"


# ---------------------------------------------------------------------------
# ReportSearchView's dashboard section, reached via the chapter-dashboard URL
# (TRWI-9; merged into ReportSearchView 2026-09 -- see the ReportSearchView
# section below for the rest of its own tests)
# ---------------------------------------------------------------------------
def _role_change(chapter, role, end, start=None, user=None):
    user = user or UserFactory(chapter=chapter)
    start = start or end - datetime.timedelta(days=180)
    return UserRoleChange.objects.create(user=user, role=role, start=start, end=end)


def test_chapter_dashboard_requires_login(client):
    chapter = ChapterFactory()
    response = client.get(reverse("transitions:chapter-dashboard", args=[chapter.pk]))
    assert response.status_code == 302


def test_chapter_dashboard_denies_an_unrelated_member(auto_login_user):
    client, member = auto_login_user()
    other_chapter = ChapterFactory()

    response = client.get(reverse("transitions:chapter-dashboard", args=[other_chapter.pk]))

    assert response.status_code == 302


def test_chapter_dashboard_shown_to_the_chapters_own_officer(auto_login_user):
    client, officer = auto_login_user()
    _role_change(officer.chapter, "treasurer", datetime.date.today() + datetime.timedelta(days=180), user=officer)
    _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:chapter-dashboard", args=[officer.chapter.pk]))

    assert response.status_code == 200
    assert "Treasurer" in response.content.decode()


def test_chapter_dashboard_denied_for_a_plain_member_of_their_own_chapter(auto_login_user):
    client, member = auto_login_user()

    response = client.get(reverse("transitions:chapter-dashboard", args=[member.chapter.pk]))

    assert response.status_code == 302


def test_chapter_dashboard_highlights_missed_obligations(auto_login_user):
    client, officer = auto_login_user()
    _role_change(officer.chapter, "treasurer", datetime.date.today() + datetime.timedelta(days=180), user=officer)
    ReportObligation.objects.create(
        chapter=officer.chapter,
        position_type="CHAPTER_OFFICER",
        position_key="scribe",
        officer=None,
        term_start=datetime.date.today() - datetime.timedelta(days=200),
        term_end=datetime.date.today() - datetime.timedelta(days=20),
        due_date=datetime.date.today() - datetime.timedelta(days=5),
        is_required=True,
        status="missed",
    )

    response = client.get(reverse("transitions:chapter-dashboard", args=[officer.chapter.pk]))

    assert "table-danger" in response.content.decode()


def test_chapter_dashboard_shown_to_the_chapters_rd(auto_login_user):
    client, rd = auto_login_user()
    chapter = ChapterFactory()
    chapter.region.directors.add(rd)

    response = client.get(reverse("transitions:chapter-dashboard", args=[chapter.pk]))

    assert response.status_code == 200


def test_chapter_dashboard_shown_to_a_national_officer(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    chapter = ChapterFactory()

    response = client.get(reverse("transitions:chapter-dashboard", args=[chapter.pk]))

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# ComplianceRatesView (TRWI-9)
# ---------------------------------------------------------------------------
def test_rates_dashboard_requires_login(client):
    response = client.get(reverse("transitions:rates-dashboard"))
    assert response.status_code == 302


def test_rates_dashboard_denied_for_a_plain_officer(auto_login_user):
    client, officer = auto_login_user()

    response = client.get(reverse("transitions:rates-dashboard"))

    assert response.status_code == 302


def test_rates_dashboard_shown_to_rd_scoped_to_their_own_region(auto_login_user):
    client, rd = auto_login_user()
    chapter = ChapterFactory(name="alpha")
    chapter.region.directors.add(rd)
    _obligation(chapter, UserFactory(chapter=chapter))

    response = client.get(reverse("transitions:rates-dashboard"))

    assert response.status_code == 200
    assert chapter.name in response.content.decode()


def test_rates_dashboard_shown_to_national_officer(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    chapter = ChapterFactory()
    _obligation(chapter, UserFactory(chapter=chapter))

    response = client.get(reverse("transitions:rates-dashboard"))

    assert response.status_code == 200
    assert chapter.name in response.content.decode()


def test_rates_dashboard_national_officer_can_narrow_by_region(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    chapter = ChapterFactory(name="alpha")
    other_chapter = ChapterFactory(name="beta")
    _obligation(chapter, UserFactory(chapter=chapter))
    _obligation(other_chapter, UserFactory(chapter=other_chapter))

    response = client.get(reverse("transitions:rates-dashboard"), {"region": other_chapter.region_id})

    # django_tables2's default cell markup is "<td >value</td>" (note the
    # space before ">"); the region FILTER DROPDOWN still legitimately lists
    # both regions (so the viewer can switch), so assert on the table cell
    # specifically, not whole-page text.
    body = response.content.decode()
    assert f"<td >{other_chapter.name}</td>" in body
    assert f"<td >{chapter.name}</td>" not in body


# ---------------------------------------------------------------------------
# ComposeReportView manual tags (TRWI-11)
# ---------------------------------------------------------------------------
def test_compose_view_submit_saves_manual_tags(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "submit",
            "prompt_successes": "we did well this term",
            "prompt_pitfalls": "",
            "manual_tags": ["risk", "advice"],
            **_empty_formsets_data(),
        },
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert set(report.tags.filter(source="manual").values_list("tag", flat=True)) == {"risk", "advice"}


def test_compose_view_draft_save_also_saves_manual_tags(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)

    response = client.post(
        reverse("transitions:compose", kwargs={"pk": obligation.public_id}),
        {
            "action": "draft",
            "prompt_successes": "",
            "prompt_pitfalls": "",
            "manual_tags": ["risk"],
            **_empty_formsets_data(),
        },
    )

    assert response.status_code == 302
    report = TransitionReport.objects.get(obligation=obligation)
    assert set(report.tags.filter(source="manual").values_list("tag", flat=True)) == {"risk"}


def test_compose_view_get_prefills_existing_manual_tags(auto_login_user):
    client, officer = auto_login_user()
    _template()
    obligation = _obligation(officer.chapter, officer)
    report = services.get_or_create_report(obligation)
    report.tags.create(tag="risk", source="manual")

    response = client.get(reverse("transitions:compose", kwargs={"pk": obligation.public_id}))

    assert response.status_code == 200
    assert response.context["form"].initial.get("manual_tags") == ["risk"]


# ---------------------------------------------------------------------------
# ReportSearchView (TRWI-11)
# ---------------------------------------------------------------------------
def test_search_view_requires_login(client):
    response = client.get(reverse("transitions:search"))
    assert response.status_code == 302


def test_search_view_shows_a_readable_report(auto_login_user):
    client, author = auto_login_user()
    _report(author.chapter, "treasurer", author)

    response = client.get(reverse("transitions:search"))

    assert response.status_code == 200
    body = response.content.decode()
    assert author.chapter.name in body
    assert "Treasurer" in body


def test_search_view_hides_an_unrelated_chapters_report(auto_login_user):
    client, member = auto_login_user()
    other_chapter = ChapterFactory()
    _report(other_chapter, "treasurer", UserFactory(chapter=other_chapter))

    response = client.get(reverse("transitions:search"))

    assert response.status_code == 200
    assert other_chapter.name not in response.content.decode()


def test_search_view_filters_by_query_text(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.current_roles = ["grand regent"]
    natoff.save(update_fields=["current_roles"])
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    chapter = ChapterFactory()
    matching = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    matching.answers.create(prompt_key="successes", prompt_label_snapshot="Successes?", value="a zorblatt printer")
    matching.save()
    other = _report(chapter, "scribe", UserFactory(chapter=chapter))
    other.answers.create(prompt_key="notes", prompt_label_snapshot="Notes?", value="nothing special")
    other.save()

    response = client.get(reverse("transitions:search"), {"q": "zorblatt", "cycle": "all"})

    body = response.content.decode()
    assert matching.chapter.name in body


def test_search_view_national_officer_sees_chapter_and_region_filters(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    response = client.get(reverse("transitions:search"))

    body = response.content.decode()
    assert 'name="chapter"' in body
    assert 'name="region"' in body


def test_search_view_non_national_does_not_see_chapter_and_region_filters(auto_login_user):
    client, officer = auto_login_user()

    response = client.get(reverse("transitions:search"))

    body = response.content.decode()
    assert 'name="chapter"' not in body
    assert 'name="region"' not in body


def test_search_view_shows_dashboard_section_for_the_viewers_own_chapter(auto_login_user):
    """2026-09 merge: "My chapter dashboard" and "Search reports" were
    condensed to one page -- /transitions/search/ (no explicit chapter_pk)
    also shows the obligation dashboard for a chapter officer's own chapter.
    """
    client, officer = auto_login_user()
    _role_change(officer.chapter, "treasurer", datetime.date.today() + datetime.timedelta(days=180), user=officer)
    _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:search"))

    assert response.status_code == 200
    assert response.context["chapter"] == officer.chapter
    assert "Treasurer" in response.content.decode()


def test_search_view_hides_dashboard_section_for_a_plain_member(auto_login_user):
    client, member = auto_login_user()

    response = client.get(reverse("transitions:search"))

    assert response.status_code == 200
    assert response.context.get("chapter") is None


def test_chapter_dashboard_url_reaches_the_same_merged_page(auto_login_user):
    """The old dashboard/chapter/<pk>/ URL keeps working (RD/national officer
    direct navigation, plus the access-control tests above) and routes to
    the exact same merged view/template as /transitions/search/.
    """
    client, officer = auto_login_user()
    _role_change(officer.chapter, "treasurer", datetime.date.today() + datetime.timedelta(days=180), user=officer)
    _obligation(officer.chapter, officer)

    response = client.get(reverse("transitions:chapter-dashboard", args=[officer.chapter.pk]))

    assert response.status_code == 200
    assert "Search reports" in response.content.decode()


# ---------------------------------------------------------------------------
# TrendView (TRWI-11)
# ---------------------------------------------------------------------------
def test_trends_view_requires_login(client):
    response = client.get(reverse("transitions:trends"))
    assert response.status_code == 302


def test_trends_view_denied_for_a_plain_officer(auto_login_user):
    client, officer = auto_login_user()

    response = client.get(reverse("transitions:trends"))

    assert response.status_code == 302


def test_trends_view_denied_for_an_rd(auto_login_user):
    client, rd = auto_login_user()
    chapter = ChapterFactory()
    chapter.region.directors.add(rd)

    response = client.get(reverse("transitions:trends"))

    assert response.status_code == 302


def test_trends_view_shown_to_national_officer(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])

    response = client.get(reverse("transitions:trends"))

    assert response.status_code == 200


def test_trends_view_shows_tag_frequency(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    chapter = ChapterFactory()
    report = _report(chapter, "treasurer", UserFactory(chapter=chapter))
    report.tags.create(tag="risk", source="manual")

    response = client.get(reverse("transitions:trends"))

    body = response.content.decode()
    assert "Risk" in body


def test_trends_view_shows_chapters_with_no_submissions(auto_login_user):
    from django.contrib.auth.models import Group

    client, natoff = auto_login_user()
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    silent_chapter = ChapterFactory()

    response = client.get(reverse("transitions:trends"))

    assert silent_chapter.name in response.content.decode()
