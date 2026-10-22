"""Tests for forms/management/commands/badge_pnm_notify.py."""

import datetime

import pytest
from django.core.management import call_command
from herald.models import SentNotification

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.notifications import BadgePNMNotify
from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory

TODAY = datetime.date.today()


def _make_pnm(chapter, start, end):
    pledge = UserFactory.create(chapter=chapter)
    UserStatusChangeFactory.create(user=pledge, status="pnm", start=start, end=end)
    return pledge


@pytest.mark.django_db
def test_badge_pnm_notify_sends_to_pledge_past_four_weeks(mailoutbox):
    chapter = ChapterFactory.create(active=True, candidate_chapter=False)
    pledge = _make_pnm(
        chapter,
        start=TODAY - datetime.timedelta(weeks=5),
        end=TODAY + datetime.timedelta(weeks=1),
    )
    call_command("badge_pnm_notify")
    match_mails = [m for m in mailoutbox if pledge.email in m.to]
    assert len(match_mails) == 1


@pytest.mark.django_db
def test_badge_pnm_notify_skips_pledge_under_four_weeks(mailoutbox):
    chapter = ChapterFactory.create(active=True, candidate_chapter=False)
    pledge = _make_pnm(
        chapter,
        start=TODAY - datetime.timedelta(weeks=1),
        end=TODAY + datetime.timedelta(weeks=3),
    )
    call_command("badge_pnm_notify")
    match_mails = [m for m in mailoutbox if pledge.email in m.to]
    assert match_mails == []


@pytest.mark.django_db
def test_badge_pnm_notify_records_sent_notification_with_real_class_path(mailoutbox):
    """Regression test: herald records ``notification_class`` using the real
    module path (``thetatauCMT.forms.notifications.BadgePNMNotify``). The
    command used to hardcode ``"forms.notifications.BadgePNMNotify"`` (missing
    the ``thetatauCMT.`` prefix), so the "already notified" lookup never
    matched and the email went out again on every run.
    """
    chapter = ChapterFactory.create(active=True, candidate_chapter=False)
    pledge = _make_pnm(
        chapter,
        start=TODAY - datetime.timedelta(weeks=5),
        end=TODAY + datetime.timedelta(weeks=1),
    )
    call_command("badge_pnm_notify")
    assert SentNotification.objects.filter(
        notification_class=BadgePNMNotify.get_class_path(),
        recipients__icontains=pledge.email,
    ).exists()


@pytest.mark.django_db
def test_badge_pnm_notify_does_not_resend_once_already_notified(mailoutbox):
    chapter = ChapterFactory.create(active=True, candidate_chapter=False)
    pledge = _make_pnm(
        chapter,
        start=TODAY - datetime.timedelta(weeks=5),
        end=TODAY + datetime.timedelta(weeks=1),
    )
    call_command("badge_pnm_notify")
    call_command("badge_pnm_notify")
    call_command("badge_pnm_notify")
    match_mails = [m for m in mailoutbox if pledge.email in m.to]
    assert len(match_mails) == 1
