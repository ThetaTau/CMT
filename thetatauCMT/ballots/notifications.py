"""Email notifications for the ballots app (django-herald).

A ballot is emailed to every voter when it opens, then every 7 days until that
voter returns a ballot, and once more on the due date. National Officers are
emailed individually. A chapter gets one email, and the copy list widens the
longer the chapter sits on its vote:

===========  ===================================================
Days open    Chapter recipients
===========  ===================================================
0 (initial)  Regent and Scribe
7            Regent and Scribe
14           every chapter officer
21+          every chapter role holder + the Regional Director(s)
===========  ===================================================
"""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from herald import registry
from herald.base import EmailNotification

from core.models import CHAPTER_OFFICER

from .models import BALLOT_CHAPTER_ROLES

CENTRAL_OFFICE_EMAIL = "central.office@thetatau.org"

REMINDER_INTERVAL_DAYS = 7

LEVEL_VOTERS = "voters"
LEVEL_OFFICERS = "officers"
LEVEL_REGION = "region"

# Days a ballot has been open -> how wide the chapter's copy list gets.
ESCALATION_DAYS = ((21, LEVEL_REGION), (14, LEVEL_OFFICERS))


def ballot_vote_url(ballot):
    host = getattr(settings, "CURRENT_URL", "").rstrip("/")
    return f"{host}{reverse('ballots:vote', kwargs={'slug': ballot.slug})}"


def escalation_level(days_open):
    """Which chapter copy list a reminder sent after ``days_open`` days uses."""
    for threshold, level in ESCALATION_DAYS:
        if days_open >= threshold:
            return level
    return LEVEL_VOTERS


def chapter_reminder_emails(chapter, level):
    """Chapter addresses to copy at ``level``, widening as the ballot ages."""
    if level == LEVEL_VOTERS:
        emails = set(chapter.get_email_specific(roles=BALLOT_CHAPTER_ROLES))
    else:
        emails = set(chapter.get_email_specific(roles=sorted(CHAPTER_OFFICER)))
    if level == LEVEL_REGION:
        # Committee chairs and advisers too, not just the executive council.
        for member in chapter.get_current_officers():
            emails |= set(member.emails)
        region = chapter.region
        if region is not None:
            for director in region.directors.all():
                emails |= set(director.emails)
            emails.add(region.email)
    return {email for email in emails if email}


def chapter_addressee(chapter, level):
    if level == LEVEL_VOTERS:
        return f"{chapter.name} Regent and Scribe"
    if level == LEVEL_OFFICERS:
        return f"{chapter.name} Chapter Officers"
    region = chapter.region
    region_name = f" and {region.name} Regional Director" if region is not None else ""
    return f"{chapter.name} Chapter Officers{region_name}"


def outstanding_recipients(ballot, reminder=False):
    """Everyone who still owes a vote on ``ballot``.

    Returns a list of ``{"emails", "addressee", "chapter", "level"}`` dicts.
    Anyone without a usable email address is skipped rather than raising.
    """
    level = escalation_level(ballot.days_open) if reminder else LEVEL_VOTERS
    recipients = []
    for role_change in ballot.outstanding_national_voters().select_related("user"):
        user = role_change.user
        emails = {email for email in user.emails if email}
        if not emails:
            continue
        recipients.append(
            {
                "emails": emails,
                "addressee": f"{role_change.role.title()} {user.name}",
                "chapter": None,
                "level": LEVEL_VOTERS,
            }
        )
    for chapter in ballot.outstanding_chapters().select_related("region"):
        emails = chapter_reminder_emails(chapter, level)
        if not emails:
            continue
        recipients.append(
            {
                "emails": emails,
                "addressee": chapter_addressee(chapter, level),
                "chapter": chapter,
                "level": level,
            }
        )
    return recipients


def send_ballot_notifications(ballot, reminder=False, final=False):
    """Email every outstanding voter. Returns the number of emails sent."""
    sent = 0
    for recipient in outstanding_recipients(ballot, reminder=reminder):
        BallotVoteRequest(
            ballot,
            recipient["emails"],
            recipient["addressee"],
            reminder=reminder,
            chapter=recipient["chapter"],
            level=recipient["level"],
            final=final,
        ).send()
        sent += 1
    return sent


@registry.register_decorator()
class BallotVoteRequest(EmailNotification):
    """Ask a voter to return their ballot, initially and then every 7 days."""

    render_types = ["html"]
    template_name = "ballot_vote_request"

    def __init__(self, ballot, emails, addressee, reminder=False, chapter=None, level=LEVEL_VOTERS, final=False):
        self.to_emails = sorted({email for email in emails if email})
        self.cc = []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        if final:
            prefix = "Final reminder: "
        elif reminder:
            prefix = "Reminder: "
        else:
            prefix = ""
        self.subject = f"{prefix}Theta Tau ballot: {ballot.name}"
        if final:
            self.subject += f" closes today at {ballot.closes_time_display}"
        self.context = {
            "ballot": ballot,
            "addressee": addressee,
            "chapter": chapter,
            "reminder": reminder,
            "final": final,
            "copied_officers": level in (LEVEL_OFFICERS, LEVEL_REGION),
            "copied_region": level == LEVEL_REGION,
            "days_open": ballot.days_open,
            "closes_display": ballot.closes_display,
            "days_left": (ballot.due_date - timezone.localdate()).days,
            "vote_url": ballot_vote_url(ballot),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from .models import Ballot

        ballot = Ballot.objects.order_by("-due_date").first()
        return [ballot, {CENTRAL_OFFICE_EMAIL}, "Grand Regent", True, None]


def grand_officer_emails():
    """Current Grand Regent and Grand Scribe addresses."""
    from thetatauCMT.users.models import UserRoleChange

    from .models import BALLOT_RESULT_ROLES

    emails = set()
    for role_change in UserRoleChange.get_current_natoff().filter(role__in=BALLOT_RESULT_ROLES):
        emails |= set(role_change.user.emails)
    return {email for email in emails if email}


@registry.register_decorator()
class BallotVoteReceipt(EmailNotification):
    """Confirm that a ballot was recorded, never how it was voted.

    A chapter's receipt goes to both the Regent and the Scribe: they were both
    asked for this ballot and either of them can cast it, so both are told it
    is in rather than only whoever happened to submit it.
    """

    render_types = ["html"]
    template_name = "ballot_vote_receipt"

    def __init__(self, vote):
        chapter = vote.user.chapter if vote.is_chapter_vote else None
        emails = {email for email in vote.user.emails if email}
        if chapter is not None:
            emails |= chapter_reminder_emails(chapter, LEVEL_VOTERS)
        self.to_emails = sorted({email for email in emails if email})
        self.cc = []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"Ballot submitted: {vote.ballot.name}"
        self.context = {
            "vote": vote,
            "ballot": vote.ballot,
            "voter": vote.user,
            "role": vote.role.title(),
            "chapter": chapter,
            "addressee": f"{chapter.name} Regent and Scribe" if chapter else vote.user.name,
            "authority": vote.get_authority_display() if vote.authority else "",
            "closes_display": vote.ballot.closes_display,
            "vote_url": ballot_vote_url(vote.ballot),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from .models import BallotComplete

        return [BallotComplete.objects.order_by("-id").first()]


@registry.register_decorator()
class BallotVoteDeleted(EmailNotification):
    """Tell everyone concerned that a submitted ballot was removed.

    Goes to the voter, the chapter's officers when it was a chapter vote, and
    the Grand Regent and Grand Scribe, who are the only people who can do this.
    """

    render_types = ["html"]
    template_name = "ballot_vote_deleted"

    def __init__(self, vote, removed_by, reason=""):
        chapter = vote.user.chapter if vote.is_chapter_vote else None
        emails = {email for email in vote.user.emails if email}
        if chapter is not None:
            emails |= set(chapter.get_email_specific(roles=sorted(CHAPTER_OFFICER)))
        emails |= grand_officer_emails()
        self.to_emails = sorted({email for email in emails if email})
        self.cc = []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"Ballot submission removed: {vote.ballot.name}"
        self.context = {
            "ballot": vote.ballot,
            "voter": vote.user,
            "role": vote.role.title(),
            "chapter": chapter,
            "removed_by": removed_by,
            "reason": reason,
            "ballot_open": vote.ballot.is_open,
            "closes_display": vote.ballot.closes_display,
            "vote_url": ballot_vote_url(vote.ballot),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from thetatauCMT.users.models import User

        from .models import BallotComplete

        vote = BallotComplete.objects.order_by("-id").first()
        return [vote, User.objects.order_by("?").first(), "Submitted by mistake"]
