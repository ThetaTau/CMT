"""Tests for the ballot emails and the 7 day reminder ladder."""

import datetime
from datetime import timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.ballots.notifications import escalation_level, outstanding_recipients, send_ballot_notifications
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _create_ballot(**kwargs):
    defaults = dict(
        name=f"Notify Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test ballot description",
        due_date=datetime.date.today() + timedelta(days=30),
        voters=["all_chapters"],
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


def _age_ballot(ballot, days):
    """Backdate ``created`` so the ballot looks ``days`` old to the ladder."""
    ballot.created = timezone.now() - timedelta(days=days)
    ballot.save(update_fields=["created"])
    ballot.refresh_from_db()
    return ballot


def _officer(chapter, role):
    user = UserFactory.create(chapter=chapter)
    UserRoleChangeFactory.create(user=user, role=role, current=True, officer=role)
    user.refresh_from_db()
    return user


def _chapter_with_roles():
    """A chapter staffed at every tier of the escalation ladder."""
    chapter = ChapterFactory.create()
    people = {
        role: _officer(chapter, role)
        for role in ["regent", "scribe", "treasurer", "vice regent", "service chair", "adviser"]
    }
    director = UserFactory.create(chapter=chapter)
    chapter.region.email = "region@example.com"
    chapter.region.save()
    chapter.region.directors.add(director)
    people["director"] = director
    return chapter, people


@pytest.mark.django_db
def test_outstanding_recipients_includes_chapters_and_national():
    chapter = ChapterFactory.create(email_regent="regent@example.com")
    grand_regent = _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["all_chapters", "grand regent"])
    recipients = outstanding_recipients(ballot)
    addressees = [recipient["addressee"] for recipient in recipients]
    assert any(grand_regent.name in addressee for addressee in addressees)
    assert any(chapter.name in addressee for addressee in addressees)


@pytest.mark.django_db
def test_outstanding_recipients_drops_chapter_once_voted():
    chapter = ChapterFactory.create(email_regent="regent@example.com")
    regent = _officer(chapter, "regent")
    ballot = _create_ballot(voters=["all_chapters"])
    assert any(chapter.name in r["addressee"] for r in outstanding_recipients(ballot))
    BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent").save()
    assert not any(chapter.name in r["addressee"] for r in outstanding_recipients(ballot))


@pytest.mark.django_db
def test_outstanding_recipients_drops_national_officer_once_voted():
    chapter = ChapterFactory.create()
    grand_scribe = _officer(chapter, "grand scribe")
    ballot = _create_ballot(voters=["grand scribe"])
    assert len(outstanding_recipients(ballot)) == 1
    BallotComplete(ballot=ballot, user=grand_scribe, motion="nay", role="grand scribe").save()
    assert outstanding_recipients(ballot) == []


@pytest.mark.django_db
def test_send_ballot_notifications_sends_one_email_per_voter():
    chapter = ChapterFactory.create(email_regent="regent@example.com")
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["all_chapters", "grand regent"])
    mail.outbox = []
    sent = send_ballot_notifications(ballot)
    assert sent == len(mail.outbox) >= 2
    assert all(ballot.name in message.subject for message in mail.outbox)
    assert not any(message.subject.startswith("Reminder") for message in mail.outbox)


@pytest.mark.django_db
def test_reminder_subject_is_marked_as_a_reminder():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"])
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True)
    assert mail.outbox[0].subject.startswith("Reminder: ")


@pytest.mark.django_db
def test_ballot_reminders_command_dry_run_sends_nothing():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"])
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--dry-run", "--ballot", ballot.slug, stdout=out)
    assert mail.outbox == []
    assert "would remind 1 voter" in out.getvalue()


@pytest.mark.django_db
def test_ballot_reminders_command_emails_outstanding_voters():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"])
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--override", "--ballot", ballot.slug, stdout=out)
    assert len(mail.outbox) == 1
    assert "reminded 1 voter" in out.getvalue()


@pytest.mark.django_db
def test_ballot_reminders_command_skips_closed_ballots():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=datetime.date.today() - timedelta(days=1))
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--override", "--ballot", ballot.slug, stdout=out)
    assert mail.outbox == []
    assert "No open ballots" in out.getvalue()


@pytest.mark.django_db
def test_ballot_reminders_command_respects_the_seven_day_cadence():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"])
    _age_ballot(ballot, 3)
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--ballot", ballot.slug, stdout=out)
    assert mail.outbox == []
    assert "no reminder due" in out.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("days_open", [7, 14, 21, 28])
def test_ballot_reminders_command_sends_on_every_seventh_day(days_open):
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=datetime.date.today() + timedelta(days=60))
    _age_ballot(ballot, days_open)
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--ballot", ballot.slug, stdout=out)
    assert len(mail.outbox) == 1
    assert f"(day {days_open})" in out.getvalue()


# ---------------------------------------------------------------------------
# Chapter escalation ladder: 7 -> voters, 14 -> officers, 21 -> region
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "days_open,expected",
    [(0, "voters"), (7, "voters"), (13, "voters"), (14, "officers"), (20, "officers"), (21, "region"), (28, "region")],
)
def test_escalation_level_by_day(days_open, expected):
    assert escalation_level(days_open) == expected


@pytest.mark.django_db
def test_day_seven_reminder_goes_to_the_regent_and_scribe_only():
    chapter, people = _chapter_with_roles()
    ballot = _create_ballot(voters=["all_chapters"])
    _age_ballot(ballot, 7)
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True)
    recipients = set(mail.outbox[0].to)
    assert people["regent"].email in recipients
    assert people["scribe"].email in recipients
    assert people["treasurer"].email not in recipients
    assert people["director"].email not in recipients


@pytest.mark.django_db
def test_day_fourteen_reminder_adds_every_chapter_officer():
    chapter, people = _chapter_with_roles()
    ballot = _create_ballot(voters=["all_chapters"])
    _age_ballot(ballot, 14)
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True)
    recipients = set(mail.outbox[0].to)
    assert people["regent"].email in recipients
    assert people["treasurer"].email in recipients
    assert people["vice regent"].email in recipients
    # Not yet: committee chairs, advisers and the Regional Director.
    assert people["service chair"].email not in recipients
    assert people["director"].email not in recipients


@pytest.mark.django_db
def test_day_twenty_one_reminder_adds_the_region_and_every_chapter_role():
    chapter, people = _chapter_with_roles()
    ballot = _create_ballot(voters=["all_chapters"])
    _age_ballot(ballot, 21)
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True)
    recipients = set(mail.outbox[0].to)
    assert people["regent"].email in recipients
    assert people["treasurer"].email in recipients
    assert people["service chair"].email in recipients
    assert people["adviser"].email in recipients
    assert people["director"].email in recipients
    assert chapter.region.email in recipients


@pytest.mark.django_db
def test_the_initial_email_never_escalates():
    """A ballot created against an old record still opens with Regent + Scribe."""
    chapter, people = _chapter_with_roles()
    ballot = _create_ballot(voters=["all_chapters"])
    _age_ballot(ballot, 30)
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=False)
    recipients = set(mail.outbox[0].to)
    assert people["regent"].email in recipients
    assert people["treasurer"].email not in recipients


@pytest.mark.django_db
def test_escalation_does_not_widen_the_national_officer_email():
    chapter = ChapterFactory.create()
    grand_regent = _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"])
    _age_ballot(ballot, 21)
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True)
    assert set(mail.outbox[0].to) <= {email for email in grand_regent.emails if email}


# ---------------------------------------------------------------------------
# Final reminder on the due date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_final_reminder_goes_out_on_the_due_date(freeze_close):
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=timezone.localdate())
    _age_ballot(ballot, 3)  # not a multiple of 7, so only the due date can fire it
    mail.outbox = []
    out = StringIO()
    with freeze_close(ballot, minutes_before=30):
        call_command("ballot_reminders", "--ballot", ballot.slug, stdout=out)
    assert len(mail.outbox) == 1
    assert "'final' level" in out.getvalue()


@pytest.mark.django_db
def test_no_reminder_once_the_five_pm_cutoff_has_passed(freeze_close):
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=timezone.localdate())
    mail.outbox = []
    out = StringIO()
    with freeze_close(ballot, minutes_after=30):
        call_command("ballot_reminders", "--ballot", ballot.slug, stdout=out)
    assert mail.outbox == []
    assert "No open ballots" in out.getvalue()


@pytest.mark.django_db
def test_final_reminder_subject_names_the_close_time():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=timezone.localdate())
    mail.outbox = []
    send_ballot_notifications(ballot, reminder=True, final=True)
    subject = mail.outbox[0].subject
    assert subject.startswith("Final reminder: ")
    assert "closes today at 5:00 pm" in subject


@pytest.mark.django_db
def test_final_reminder_is_not_sent_before_the_due_date():
    chapter = ChapterFactory.create()
    _officer(chapter, "grand regent")
    ballot = _create_ballot(voters=["grand regent"], due_date=timezone.localdate() + timedelta(days=1))
    _age_ballot(ballot, 3)
    mail.outbox = []
    out = StringIO()
    call_command("ballot_reminders", "--ballot", ballot.slug, stdout=out)
    assert mail.outbox == []
    assert "no reminder due" in out.getvalue()
