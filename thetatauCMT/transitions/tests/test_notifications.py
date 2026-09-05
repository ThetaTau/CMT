import datetime

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

from ..models import ReportObligation
from ..notifications import TransitionReportDueReminder, TransitionReportSeasonalReminder

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
