import datetime

import pytest
from django.core.management import call_command

from core.models import month_period, previous_month_period
from thetatauCMT.announcements.models import Announcement
from thetatauCMT.awards.digest import digest_recipients, grants_in_period, send_award_digest
from thetatauCMT.awards.models import AwardDigestRun
from thetatauCMT.awards.notifications import (
    AwardDigestNotification,
    AwardGrantedNotification,
    AwardNominationSubmittedNotification,
    grant_notification_recipients,
)
from thetatauCMT.awards.services import direct_grant
from thetatauCMT.awards.tests._flow_helpers import start_award_nomination
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardGrantFactory, AwardTypeFactory
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _superuser():
    return UserFactory(is_superuser=True)


def _all_recipients(mailoutbox):
    recipients = set()
    for message in mailoutbox:
        recipients |= set(message.to)
    return recipients


# ---------------------------------------------------------------------------
# grant_notification_recipients helper
# ---------------------------------------------------------------------------
def test_grant_notification_recipients_member():
    grant = AwardGrantFactory()
    emails = grant_notification_recipients(grant)
    assert grant.recipient_member.email in emails


def test_grant_notification_recipients_chapter():
    chapter = ChapterFactory()
    active = UserFactory(chapter=chapter, status="active")
    grant = AwardGrantFactory(recipient_member=None, recipient_chapter=chapter)
    emails = grant_notification_recipients(grant)
    # A chapter award notifies the entire chapter, not just its officers.
    assert active.email in emails


def test_grant_notification_recipients_region():
    region = RegionFactory()
    director = UserFactory()
    region.directors.add(director)
    grant = AwardGrantFactory(recipient_member=None, recipient_region=region)
    assert director.email in grant_notification_recipients(grant)


# ---------------------------------------------------------------------------
# Acceptance: grant notification fires + announcement created on grant
# ---------------------------------------------------------------------------
def test_grant_notification_and_announcement_on_direct_grant(mailoutbox):
    award = AwardTypeFactory(grant_method="direct", level="member")
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    before = Announcement.objects.count()
    grant = direct_grant(award, cycle, member, _superuser())
    # announcement created
    assert Announcement.objects.count() == before + 1
    # notification sent to the recipient
    assert len(mailoutbox) >= 1
    assert member.email in _all_recipients(mailoutbox)
    assert str(grant.award_type) in mailoutbox[-1].subject


# ---------------------------------------------------------------------------
# Acceptance: nomination notification fires (to the configured approver)
# ---------------------------------------------------------------------------
def test_nomination_notification_to_approver(mailoutbox):
    approver = UserFactory(username="award.approver@example.com")
    Config.objects.create(key="AwardApprover", value="award.approver@example.com", description="approver")
    start_award_nomination()  # start -> notify_submitted -> review
    assert approver.emails & _all_recipients(mailoutbox)


def test_no_nomination_notification_without_approver(mailoutbox):
    start_award_nomination()  # no AwardApprover config -> approver None -> no email
    assert mailoutbox == []


# ---------------------------------------------------------------------------
# Acceptance: monthly digest aggregates the correct period
# ---------------------------------------------------------------------------
def test_digest_aggregates_correct_period(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    member = UserFactory(status="active")
    in_period = AwardGrantFactory(effective_date=datetime.date(2026, 3, 15))
    AwardGrantFactory(effective_date=datetime.date(2026, 4, 15))  # out of period
    run = send_award_digest(period_start, period_end)
    assert run is not None
    assert run.grant_count == 1
    assert list(grants_in_period(period_start, period_end)) == [in_period]
    assert member.email in _all_recipients(mailoutbox)


def test_digest_targets_active_and_alumni_excluding_opted_out(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 10))
    active = UserFactory(status="active")
    alumni = UserFactory(status="alumni")
    optout = UserFactory(status="active", unsubscribe_email=True)
    no_contact = UserFactory(status="active", no_contact=True)
    send_award_digest(period_start, period_end)
    recipients = _all_recipients(mailoutbox)
    assert active.email in recipients
    assert alumni.email in recipients
    assert optout.email not in recipients
    assert no_contact.email not in recipients


# ---------------------------------------------------------------------------
# Acceptance: digest idempotent / safe to re-run
# ---------------------------------------------------------------------------
def test_digest_idempotent(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    UserFactory(status="active")
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 15))
    run1 = send_award_digest(period_start, period_end)
    sent_after_first = len(mailoutbox)
    run2 = send_award_digest(period_start, period_end)  # re-run
    assert run1 is not None
    assert run2 is None  # skipped
    assert AwardDigestRun.objects.filter(period_start=period_start, period_end=period_end).count() == 1
    assert sent_after_first >= 1
    assert len(mailoutbox) == sent_after_first  # no additional emails on re-run


def test_digest_force_resends_without_duplicating_run(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    UserFactory(status="active")
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 15))
    send_award_digest(period_start, period_end)
    sent_after_first = len(mailoutbox)
    run2 = send_award_digest(period_start, period_end, force=True)
    assert run2 is not None
    assert AwardDigestRun.objects.filter(period_start=period_start, period_end=period_end).count() == 1
    assert sent_after_first >= 1
    assert len(mailoutbox) == 2 * sent_after_first


# ---------------------------------------------------------------------------
# Digest command
# ---------------------------------------------------------------------------
def test_digest_command_sends(mailoutbox):
    UserFactory(status="active")
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 10))
    call_command("award_digest", year=2026, month=3)
    assert AwardDigestRun.objects.filter(period_start=datetime.date(2026, 3, 1)).exists()
    assert len(mailoutbox) >= 1


def test_digest_command_dry_run_sends_nothing(mailoutbox):
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 10))
    call_command("award_digest", year=2026, month=3, dry_run=True)
    assert mailoutbox == []
    assert not AwardDigestRun.objects.exists()


def test_previous_month_period():
    start, end = previous_month_period(datetime.date(2026, 3, 15))
    assert start == datetime.date(2026, 2, 1)
    assert end == datetime.date(2026, 2, 28)


# ---------------------------------------------------------------------------
# Digest recipients + per-user unsubscribe (active + alumni)
# ---------------------------------------------------------------------------
def test_digest_recipients_active_and_alumni_only():
    active = UserFactory(status="active")
    alumni = UserFactory(status="alumni")
    pnm = UserFactory(status="pnm")
    optout = UserFactory(status="active", unsubscribe_email=True)
    pks = set(digest_recipients().values_list("pk", flat=True))
    assert {active.pk, alumni.pk} <= pks
    assert pnm.pk not in pks
    assert optout.pk not in pks


def test_digest_recipients_excludes_category_optout():
    member = UserFactory(status="active", unsubscribe_categories=["award_digest"])
    assert member.pk not in set(digest_recipients().values_list("pk", flat=True))


def test_digest_email_includes_unsubscribe_link(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    UserFactory(status="active")
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 10))
    send_award_digest(period_start, period_end)
    assert mailoutbox
    msg = mailoutbox[0]
    html = " ".join(content for content, _mime in getattr(msg, "alternatives", []))
    assert "unsubscribe" in (msg.body + html).lower()


def test_digest_email_is_celebratory_without_award_period(mailoutbox):
    period_start, period_end = month_period(2026, 3)
    UserFactory(status="active")
    AwardGrantFactory(effective_date=datetime.date(2026, 3, 10))
    send_award_digest(period_start, period_end)
    assert mailoutbox
    msg = mailoutbox[0]
    html = " ".join(content for content, _mime in getattr(msg, "alternatives", []))
    body = msg.body + html
    assert "congratulat" in body.lower()
    assert "Award Period" not in body


# ---------------------------------------------------------------------------
# Award description (AWI request 5) + reviewer review link (request 4)
# ---------------------------------------------------------------------------
def test_granted_email_includes_award_description(mailoutbox):
    award = AwardTypeFactory(grant_method="direct", level="member", description="For outstanding service.")
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    direct_grant(award, cycle, member, _superuser())
    msgs = [m for m in mailoutbox if member.email in m.to]
    assert msgs
    msg = msgs[0]
    html = " ".join(content for content, _mime in getattr(msg, "alternatives", []))
    assert "For outstanding service." in (msg.body + html)


def test_granted_email_names_the_recipient(mailoutbox):
    # The award recipient must be named in the notification body (request 2).
    award = AwardTypeFactory(grant_method="direct", level="member")
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    direct_grant(award, cycle, member, _superuser())
    msgs = [m for m in mailoutbox if member.email in m.to]
    assert msgs
    msg = msgs[0]
    html = " ".join(content for content, _mime in getattr(msg, "alternatives", []))
    assert member.name in (msg.body + html)


def test_nomination_email_has_review_link(mailoutbox):
    approver = UserFactory(username="rev.approver@example.com")
    Config.objects.create(key="AwardApprover", value="rev.approver@example.com", description="approver")
    start_award_nomination()
    msgs = [m for m in mailoutbox if set(m.to) & approver.emails]
    assert msgs
    msg = msgs[0]
    html = " ".join(content for content, _mime in getattr(msg, "alternatives", []))
    assert "Review this nomination" in (msg.body + html)


# ---------------------------------------------------------------------------
# Notification examples for the herald preview -- get_demo_args
# ---------------------------------------------------------------------------
def test_award_granted_get_demo_args_returns_latest_grant():
    grant = AwardGrantFactory()
    args = AwardGrantedNotification.get_demo_args()
    assert args == [grant]
    AwardGrantedNotification(*args)  # instantiates cleanly


def test_award_nomination_submitted_get_demo_args_returns_process():
    nomination = start_award_nomination()
    UserFactory()
    args = AwardNominationSubmittedNotification.get_demo_args()
    assert args[0] == nomination
    AwardNominationSubmittedNotification(*args)  # instantiates cleanly


def test_award_digest_get_demo_args_instantiates():
    UserFactory(status="active")
    AwardGrantFactory()
    args = AwardDigestNotification.get_demo_args()
    assert len(args) == 4
    AwardDigestNotification(*args)  # instantiates cleanly
