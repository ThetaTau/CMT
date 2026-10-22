"""CSSWI-6: the Regent's chapter emails reach the chapter's Chapter Support Specialists.

One test per row of the spec's Email inventory, then the Config switch, the switcher not
mattering, the digests and the shingle sheet.
"""

import datetime
from email.mime.base import MIMEBase
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.ballots.notifications import BallotVoteDeleted, BallotVoteReceipt, BallotVoteRequest
from thetatauCMT.chapters.notifications import DuesReminder
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.forms.notifications import EmailProcessUpdate, EmailScribeExpulsion
from thetatauCMT.forms.views import BylawsCreateView, pledge_program_request_revision
from thetatauCMT.support.digests import send_daily_digests, send_monthly_digests
from thetatauCMT.support.emails import REALTIME_CONFIG_KEY, copy_to_support
from thetatauCMT.support.models import SupportDigestEntry
from thetatauCMT.transitions.models import ReportObligation
from thetatauCMT.transitions.notifications import TransitionReportDueReminder
from thetatauCMT.users.models import User, UserAlter
from thetatauCMT.users.notifications import OfficerMonthly, OfficerUpdateReminder
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, SupportDigestEntryFactory, make_css, make_regent

pytestmark = pytest.mark.django_db

Kind = SupportDigestEntry.Kind


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


@pytest.fixture
def alpha():
    return ChapterFactory(name="alpha")


@pytest.fixture
def css(alpha):
    person = make_css(email="css.alpha@example.com")
    ChapterSupportAssignmentFactory(user=person, chapter=alpha)
    return User.objects.get(pk=person.pk)


@pytest.fixture
def regent(alpha):
    return make_regent(chapter=alpha, email="regent.alpha@example.com")


def _entry(css, kind):
    (entry,) = SupportDigestEntry.objects.filter(user=css, kind=kind)
    return entry


def _assert_cc_as_sent(css, alpha, kind):
    assert any(css.email in message.cc for message in mail.outbox), [message.cc for message in mail.outbox]
    entry = _entry(css, kind)
    assert entry.realtime and entry.chapter == alpha and entry.body_html == ""


def _assert_digest_only(css, alpha, kind, text):
    assert not any(css.email in [*message.to, *message.cc] for message in mail.outbox)
    entry = _entry(css, kind)
    assert not entry.realtime and entry.chapter == alpha
    assert text in entry.body_html
    assert "<html" not in entry.body_html.lower()  # only the email's own content


def _process_update(alpha, regent, **kwargs):
    member = UserFactory(chapter=alpha, status="active")
    return EmailProcessUpdate(
        SimpleNamespace(chapter=alpha, user=member),
        "Submitted",
        "Review",
        "Pending",
        "The workflow message",
        [],
        process_title="Test Process",
        **kwargs,
    )


def _vote(alpha, regent):
    ballot = Ballot(name="Charter vote", type="other", description="d", due_date=_days(10), voters=["all_chapters"])
    ballot.save()
    vote = BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent", authority="chapter_vote")
    vote.save()
    return vote


def _messages_request(user, method="post", path="/"):
    request = getattr(RequestFactory(), method)(path)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


# --- the Email inventory, one row each -------------------------------------------------------


def test_e1_monthly_officer_email_goes_to_the_digest(alpha, css, regent):
    OfficerMonthly(alpha).send()
    _assert_digest_only(css, alpha, Kind.OFFICER_MONTHLY, alpha.name)


def test_e2_dues_reminder_goes_to_the_digest(alpha, css, regent):
    attachment = MIMEBase("application", "csv")
    attachment.add_header("Content-Disposition", "attachment", filename="dues.csv")
    attachment.set_payload("a,b")

    DuesReminder(alpha, attachment).send()

    _assert_digest_only(css, alpha, Kind.DUES, alpha.name)


def test_e3_workflow_updates_go_to_the_digest_and_escalations_are_cc(alpha, css, regent):
    _process_update(alpha, regent, email_officers=True).send()
    _assert_digest_only(css, alpha, Kind.WORKFLOW_UPDATE, "The workflow message")

    mail.outbox = []
    _process_update(alpha, regent, email_officers=True, support_kind=Kind.WORKFLOW_ESCALATION).send()
    _assert_cc_as_sent(css, alpha, Kind.WORKFLOW_ESCALATION)


def test_e3_an_email_only_to_the_form_owner_is_not_copied(alpha, css, regent):
    _process_update(alpha, regent).send()

    assert not SupportDigestEntry.objects.exists()
    assert not any(css.email in message.cc for message in mail.outbox)


def test_e4_award_granted_goes_to_the_digest(alpha, css, regent):
    from thetatauCMT.awards.notifications import AwardGrantedNotification
    from thetatauCMT.awards.tests.factories import AwardGrantFactory

    grant = AwardGrantFactory(recipient_member=UserFactory(chapter=alpha, status="active"))
    SupportDigestEntry.objects.all().delete()
    mail.outbox = []

    AwardGrantedNotification(grant).send()

    _assert_digest_only(css, alpha, Kind.AWARD, str(grant.award_type))


def test_e5_nme_revision_request_goes_to_the_digest(alpha, css, regent):
    natoff = UserFactory(status="alumni")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(natoff)
    process = SimpleNamespace(chapter=alpha, approval_comments="Please add week 3.")
    request = _messages_request(natoff)

    with mock.patch("thetatauCMT.forms.views.PledgeProgramProcess") as model:
        model.objects.filter.return_value.select_related.return_value.first.return_value = process
        pledge_program_request_revision(request, process_pk=1)

    _assert_digest_only(css, alpha, Kind.NME_REVISION, "Please add week 3.")


def test_e6_bylaws_update_goes_to_the_digest(alpha, css, regent):
    view = BylawsCreateView()
    view.request = _messages_request(regent)
    view.object = SimpleNamespace(
        chapter=alpha,
        changes="Renamed the treasurer's committee",
        bylaws=SimpleUploadedFile("bylaws.pdf", b"%PDF-1.4", content_type="application/pdf"),
    )

    view.get_success_url()

    _assert_digest_only(css, alpha, Kind.BYLAWS, "Renamed the treasurer")


def test_e7_ballot_requests_and_reminders_are_cc(alpha, css, regent):
    ballot = _vote(alpha, regent).ballot

    BallotVoteRequest(ballot, {regent.email}, "Alpha Regent and Scribe", reminder=True, chapter=alpha).send()

    _assert_cc_as_sent(css, alpha, Kind.BALLOT)


def test_e8_ballot_vote_receipt_is_cc(alpha, css, regent):
    BallotVoteReceipt(_vote(alpha, regent)).send()
    _assert_cc_as_sent(css, alpha, Kind.BALLOT_RECEIPT)


def test_e9_ballot_vote_removed_is_cc(alpha, css, regent):
    BallotVoteDeleted(_vote(alpha, regent), UserFactory(), reason="Too early").send()
    _assert_cc_as_sent(css, alpha, Kind.BALLOT_VOTE_REMOVED)


def test_e10_expulsion_notice_is_cc(alpha, css, regent):
    EmailScribeExpulsion(UserFactory(chapter=alpha, status="active"), timezone.localdate()).send()
    _assert_cc_as_sent(css, alpha, Kind.EXPULSION)


def test_e11_disciplinary_email_to_the_regent_is_cc(alpha, css, regent):
    _process_update(alpha, regent, direct_user=regent, support_kind=Kind.DISCIPLINARY).send()
    _assert_cc_as_sent(css, alpha, Kind.DISCIPLINARY)


def test_e12_officer_update_reminder_is_cc(alpha, css, regent):
    OfficerUpdateReminder(alpha, {regent.email}, ["scribe"]).send()
    _assert_cc_as_sent(css, alpha, Kind.OFFICER_UPDATE)


def test_e13_pnm_and_initiation_reminder_goes_to_the_digest(alpha, css, regent):
    call_command("chapter_pledges_check", "-override", "-chapter", alpha.slug)
    _assert_digest_only(css, alpha, Kind.PNM_INITIATION, "potential new members")


def test_e14_transition_report_past_due_is_cc_but_not_before(alpha, css, regent):
    obligation = ReportObligation.objects.create(
        chapter=alpha,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        term_start=_days(-180),
        term_end=_days(-5),
        due_date=_days(-1),
        is_required=True,
        status="open",
    )

    TransitionReportDueReminder(obligation, {"treasurer@example.com"}, False, False).send()
    assert not SupportDigestEntry.objects.exists()

    TransitionReportDueReminder(obligation, {"treasurer@example.com"}, True, False).send()
    _assert_cc_as_sent(css, alpha, Kind.TRANSITION_PAST_DUE)


# --- who gets them ------------------------------------------------------------------------------


def test_nothing_once_the_assignment_has_ended(alpha, css, regent):
    css.support_assignments.update(start=_days(-30), end=_days(-1))

    OfficerUpdateReminder(alpha, {regent.email}, ["scribe"]).send()
    OfficerMonthly(alpha).send()

    assert not SupportDigestEntry.objects.exists()
    assert not any(css.email in message.cc for message in mail.outbox)


def test_emails_follow_assignments_not_the_switcher(alpha, css, regent):
    beta = ChapterFactory(name="beta")
    ChapterSupportAssignmentFactory(user=css, chapter=beta)
    UserAlter.objects.create(user=css, chapter=beta)

    OfficerUpdateReminder(alpha, {regent.email}, ["scribe"]).send()
    OfficerUpdateReminder(beta, {"regent.beta@example.com"}, ["scribe"]).send()

    assert all(css.email in message.cc for message in mail.outbox) and len(mail.outbox) == 2
    assert set(SupportDigestEntry.objects.values_list("chapter__name", flat=True)) == {"alpha", "beta"}


def test_the_config_setting_moves_an_email_between_cc_and_the_digest(alpha, css, regent):
    setting = Config.objects.create(key=REALTIME_CONFIG_KEY, value="<p>officer_monthly</p><p>dues</p>", description="t")

    OfficerMonthly(alpha).send()
    OfficerUpdateReminder(alpha, {regent.email}, ["scribe"]).send()

    _assert_cc_as_sent(css, alpha, Kind.OFFICER_MONTHLY)
    entry = _entry(css, Kind.OFFICER_UPDATE)
    assert not entry.realtime and entry.body_html

    setting.value = "none"
    setting.save()
    mail.outbox = []
    BallotVoteReceipt(_vote(alpha, regent)).send()
    assert not _entry(css, Kind.BALLOT_RECEIPT).realtime


def test_a_failed_copy_never_stops_the_email(alpha, css, regent):
    with mock.patch("thetatauCMT.support.emails.notify_support", side_effect=RuntimeError("boom")):
        assert copy_to_support(mock.Mock(), alpha, Kind.BYLAWS) == []
        OfficerUpdateReminder(alpha, {regent.email}, ["scribe"]).send()

    assert [message.to for message in mail.outbox] == [[regent.email]]


# --- the daily digest (Q25 C, S17) --------------------------------------------------------------


def _entry_for(css, chapter, kind, subject, realtime=False, body="<p>Body text</p>", created=None):
    entry = SupportDigestEntryFactory(
        user=css, chapter=chapter, kind=kind, subject=subject, realtime=realtime, body_html="" if realtime else body
    )
    if created:
        SupportDigestEntry.objects.filter(pk=entry.pk).update(created=created)
    return entry


def test_the_daily_digest_carries_emails_in_full_by_chapter_and_lists_the_cc_ones(alpha, css):
    beta = ChapterFactory(name="beta")
    _entry_for(css, beta, Kind.DUES, "Beta dues roster", body="<p>Beta dues body</p>")
    _entry_for(css, alpha, Kind.OFFICER_MONTHLY, "Alpha monthly update", body="<p>Alpha monthly body</p>")
    _entry_for(css, alpha, Kind.BALLOT_RECEIPT, "Ballot submitted: Charter vote", realtime=True)

    assert send_daily_digests() == 1

    (digest,) = mail.outbox
    html = digest.alternatives[0][0]
    assert digest.to == [css.email]
    assert html.index("Alpha monthly body") < html.index("Beta dues body")
    already = html.split("Already sent to you")[1]
    assert "Ballot submitted: Charter vote" in already and "Alpha monthly update" not in already
    assert not SupportDigestEntry.objects.filter(daily_sent_at__isnull=True).exists()

    assert send_daily_digests() == 0
    assert len(mail.outbox) == 1


def test_a_day_with_only_cc_emails_sends_no_digest(alpha, css):
    _entry_for(css, alpha, Kind.BALLOT, "Theta Tau ballot: Charter vote", realtime=True)

    assert send_daily_digests() == 0

    assert mail.outbox == []
    assert not SupportDigestEntry.objects.filter(daily_sent_at__isnull=True).exists()


# --- the monthly digest (Q14) ---------------------------------------------------------------------


def test_the_monthly_digest_covers_each_chapter_once(alpha, css):
    first_of_month = timezone.localdate().replace(day=1)
    last_month = timezone.make_aware(
        datetime.datetime.combine(first_of_month - datetime.timedelta(days=3), datetime.time(9))
    )
    _entry_for(css, alpha, Kind.OFFICER_UPDATE, "CMT Officer update Alpha", realtime=True, created=last_month)
    _entry_for(css, alpha, Kind.DUES, "This month's email")

    assert send_monthly_digests(today=first_of_month) == 1

    (digest,) = mail.outbox
    html = digest.alternatives[0][0]
    assert "CMT Officer update Alpha" in html and "This month's email" not in html
    assert "Officers missing on the CMT" in html and "Regent" in html
    assert SupportDigestEntry.objects.get(subject="CMT Officer update Alpha").monthly_sent_at is not None

    assert send_monthly_digests(today=first_of_month) == 0
    assert send_monthly_digests(today=first_of_month, force=True) == 1


def test_the_command_sends_the_monthly_digest_only_on_its_day(alpha, css, capsys):
    with mock.patch("thetatauCMT.support.management.commands.send_css_digests.timezone") as clock:
        clock.localdate.return_value = datetime.date(2026, 10, 2)
        call_command("send_css_digests", "--period", "monthly")
    assert "Not the scheduled day" in capsys.readouterr().out
    assert mail.outbox == []

    call_command("send_css_digests", "--period", "monthly", "--override")
    assert "Sent 1 monthly digest(s)." in capsys.readouterr().out


# --- lists that are not emails (Q16) ----------------------------------------------------------------


def test_only_the_shingle_sheet_lists_the_css_with_the_officers(alpha, css, regent):
    assert css.email not in alpha.council_emails()
    assert css.email in alpha.council_emails(include_support=True)

    worksheet = mock.MagicMock()
    worksheet.row_values.return_value = ["Chapter Code", "Notify"]
    worksheet.find.return_value.address = "B1"
    with mock.patch("thetatauCMT.chapters.management.commands.update_shingle_contacts.gspread") as gspread:
        gspread.service_account.return_value.open_by_key.return_value.worksheet.return_value = worksheet
        call_command("update_shingle_contacts")

    rows = worksheet.update.call_args[0][1]
    (alpha_row,) = [row for row in rows[1:] if row[0] == f"{alpha.pk:03d}"]
    assert css.email in alpha_row[1] and regent.email in alpha_row[1]


def test_the_digest_emails_have_demo_args(alpha, css):
    from thetatauCMT.support.notifications import EmailSupportDailyDigest, EmailSupportMonthlyDigest

    _entry_for(css, alpha, Kind.DUES, "Dues")

    user, entries, when = EmailSupportDailyDigest.get_demo_args()
    assert user == css and entries
    assert EmailSupportDailyDigest(user, entries, when).subject.startswith("Chapter Support Specialist digest")
    user, start, sections = EmailSupportMonthlyDigest.get_demo_args()
    assert user == css and sections[0]["chapter"] == alpha
    assert reverse("chapters:detail", kwargs={"slug": alpha.slug}) in sections[0]["url"]
