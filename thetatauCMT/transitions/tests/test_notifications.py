import datetime

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

from ..models import ReportObligation, ReportTemplate, TransitionReport
from ..notifications import HandoffPacketAvailable, TransitionReportDueReminder, TransitionReportSeasonalReminder

pytestmark = pytest.mark.django_db


def _obligation(chapter, officer=None, position_key="treasurer", due_date=None):
    return ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        officer=officer,
        term_start=datetime.date.today() - datetime.timedelta(days=180),
        term_end=datetime.date.today() + datetime.timedelta(days=30),
        due_date=due_date or datetime.date.today() + datetime.timedelta(days=16),
        is_required=True,
        status="open",
    )


def _report(obligation, status):
    template = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    return TransitionReport.objects.create(
        obligation=obligation,
        chapter=obligation.chapter,
        position_type=obligation.position_type,
        position_key=obligation.position_key,
        author=obligation.officer,
        template=template,
        template_version=1,
        status=status,
    )


# ---------------------------------------------------------------------------
# TransitionReportDueReminder
# ---------------------------------------------------------------------------
def test_due_reminder_to_emails_set():
    chapter = ChapterFactory()
    obligation = _obligation(chapter)
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, False, False)
    assert notif.to_emails == {"officer@example.com"}


def test_due_reminder_drops_falsy_emails():
    chapter = ChapterFactory()
    obligation = _obligation(chapter)
    notif = TransitionReportDueReminder(obligation, {"officer@example.com", "", None}, False, False)
    assert notif.to_emails == {"officer@example.com"}


def test_due_reminder_subject_contains_position_and_chapter():
    chapter = ChapterFactory()
    obligation = _obligation(chapter, position_key="treasurer")
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, False, False)
    assert "Treasurer" in notif.subject
    assert chapter.name in notif.subject


def test_due_reminder_context_flags():
    chapter = ChapterFactory()
    obligation = _obligation(chapter)
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, True, True)
    assert notif.context["past_due"] is True
    assert notif.context["escalate_to_rd"] is True
    assert notif.context["due_date"] == obligation.due_date


def test_due_reminder_has_no_draft_when_nothing_was_started():
    chapter = ChapterFactory()
    obligation = _obligation(chapter, officer=UserFactory(chapter=chapter))
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, False, False)
    assert notif.context["has_draft"] is False


def test_due_reminder_flags_a_saved_but_unsubmitted_draft():
    chapter = ChapterFactory()
    obligation = _obligation(chapter, officer=UserFactory(chapter=chapter))
    _report(obligation, "draft")
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, False, False)
    assert notif.context["has_draft"] is True


def test_due_reminder_does_not_flag_a_submitted_report_as_a_draft():
    chapter = ChapterFactory()
    obligation = _obligation(chapter, officer=UserFactory(chapter=chapter))
    _report(obligation, "submitted")
    notif = TransitionReportDueReminder(obligation, {"officer@example.com"}, False, False)
    assert notif.context["has_draft"] is False


# ---------------------------------------------------------------------------
# TransitionReportSeasonalReminder
# ---------------------------------------------------------------------------
def test_seasonal_reminder_to_emails_from_user():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer=user)
    notif = TransitionReportSeasonalReminder(user, [obligation])
    assert notif.to_emails == set(user.emails)


def test_seasonal_reminder_context_lists_obligations():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    obligation = _obligation(chapter, officer=user)
    notif = TransitionReportSeasonalReminder(user, [obligation])
    assert notif.context["obligations"] == [obligation]


# ---------------------------------------------------------------------------
# HandoffPacketAvailable
# ---------------------------------------------------------------------------
def test_handoff_packet_available_to_emails_from_user():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    notif = HandoffPacketAvailable(user, "treasurer", chapter, 3)
    assert notif.to_emails == set(user.emails)


def test_handoff_packet_available_subject_contains_position_and_chapter():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    notif = HandoffPacketAvailable(user, "treasurer", chapter, 3)
    assert "Treasurer" in notif.subject
    assert chapter.name in notif.subject


def test_handoff_packet_available_context():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    notif = HandoffPacketAvailable(user, "treasurer", chapter, 3)
    assert notif.context["position_key"] == "treasurer"
    assert notif.context["chapter_pk"] == chapter.pk
    assert notif.context["report_count"] == 3


def test_handoff_packet_available_email_links_a_position_with_a_slash():
    from django.urls import reverse

    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    notif = HandoffPacketAvailable(user, "pledge/new member educator", chapter, 1)

    body = notif.render("html", notif.get_context_data())

    assert reverse("transitions:packet", args=[chapter.pk, "pledge/new member educator"]) in body
