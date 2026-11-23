"""Rules and actions for the Case Competition (docs/specs/case-competition.md).

Every permission check goes through this module (NECCWI-2), never through templates alone.
Judging, scores and results are in ``judging.py``, the daily emails in ``reminders.py`` and
the emails themselves in ``notifications.py``.

Times: every rule takes an optional ``now`` (default ``timezone.now()``). Windows are stored
as aware datetimes; anything counted in days (reminders) uses the competition's time zone.
"""

import datetime
import re
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from core.models import ACTIVE_STATUSES, ALL_ROLES, NAT_OFFICERS, resolve_config_actor, user_is_national_officer

from .models import (
    Assignment,
    Competition,
    Entry,
    EntryFile,
    KeyDate,
    NotificationLog,
    Participant,
    Round,
    RubricCriterion,
    SubmissionItem,
)

MANAGERS_CONFIG_KEY = "CASE_COMPETITION_MANAGERS"
CHAPTER_ROLES_CONFIG_KEY = "CASE_COMPETITION_CHAPTER_ROLES"
CONTACT_CONFIG_KEY = "CASE_COMPETITION_CONTACT"
DEFAULT_MANAGER_ROLE = "professional development director"
DEFAULT_EMAIL_ROLES = frozenset({"pd chair"})
# "Members of the chapter" (Q6 B, S29): its current members and its PNMs, by their own chapter.
MEMBER_STATUSES = frozenset(ACTIVE_STATUSES) | {"pnm"}
CENTRAL_OFFICE_NAME = "Central Office"
CENTRAL_OFFICE_EMAIL = "central.office@thetatau.org"

# A round's state comes from its dates (Round lifecycle); nothing stores it.
UPCOMING, OPEN, JUDGING, PUBLISHED = "upcoming", "open", "judging", "published"
STATE_LABELS = {UPCOMING: "Not open yet", OPEN: "Open", JUDGING: "Closed: judging", PUBLISHED: "Results published"}

# Where an entry stands (S6): nothing yet, saved but missing something, or complete. Once the
# chapter's deadline has passed nothing more can be saved, so an unfinished entry is incomplete
# and a missing one not submitted (owner, 2026-11-20).
NOT_STARTED, IN_PROGRESS, SUBMITTED = "not_started", "in_progress", "submitted"
INCOMPLETE, NOT_SUBMITTED = "incomplete", "not_submitted"
ENTRY_STATUS_LABELS = {
    NOT_STARTED: "Not started",
    IN_PROGRESS: "In progress",
    SUBMITTED: "Submitted",
    INCOMPLETE: "Incomplete",
    NOT_SUBMITTED: "Not submitted",
}
# Statuses of an entry that has something in it, so it can be opened.
STARTED_STATUSES = frozenset({IN_PROGRESS, INCOMPLETE, SUBMITTED})


class CompetitionError(Exception):
    """An action was refused; the message says why, for the person who tried it."""


def _now(now=None):
    return now or timezone.now()


def is_signed_in(user):
    return user is not None and getattr(user, "is_authenticated", False) and getattr(user, "pk", None) is not None


# --- Settings (Q4, Q13) ------------------------------------------------------------------


def manager_ids():
    """Who manages the competition besides Admins (Q4).

    ``CASE_COMPETITION_MANAGERS`` lists usernames, emails or National Officer role names,
    separated by commas or new lines. Blank means the Professional Development Director.
    """
    from thetatauCMT.support.services import config_list
    from thetatauCMT.users.models import User

    values = config_list(MANAGERS_CONFIG_KEY) or [DEFAULT_MANAGER_ROLE]
    roles = {role.lower(): role for role in NAT_OFFICERS}
    ids = set()
    for value in values:
        role = roles.get(value.lower())
        if role is not None:
            ids.update(User.objects.filter(current_roles__contains=[role]).values_list("pk", flat=True))
        else:
            ids.update(
                User.objects.filter(Q(username__iexact=value) | Q(email__iexact=value)).values_list("pk", flat=True)
            )
    return ids


def can_manage(user):
    """Admins, plus the people named in ``CASE_COMPETITION_MANAGERS``; "view as member" turns it off."""
    if not is_signed_in(user):
        return False
    if getattr(user, "is_admin", False):
        return True
    if getattr(user, "natoff_hidden", False):
        return False
    return user.pk in manager_ids()


def can_view_status(user):
    """The participants status page: managers, and National Officers read only (S19)."""
    return can_manage(user) or user_is_national_officer(user)


def email_roles():
    """Chapter roles whose holders also get the chapter's competition emails (Q13 C).

    ``CASE_COMPETITION_CHAPTER_ROLES`` names roles from ``core.models.ALL_ROLES``; blank, or
    nothing known, means the PD Chair. It only adds email recipients and grants nothing.
    """
    from thetatauCMT.support.services import config_list

    roles = {value.lower() for value in config_list(CHAPTER_ROLES_CONFIG_KEY)} & set(ALL_ROLES)
    return frozenset(roles) or DEFAULT_EMAIL_ROLES


def _unique_emails(values):
    """Emails without blanks or repeats (ignoring capitals), in a stable order."""
    seen, emails = set(), []
    for value in values:
        email = (value or "").strip()
        if email and email.lower() not in seen:
            seen.add(email.lower())
            emails.append(email)
    return sorted(emails, key=str.lower)


@dataclass
class CompetitionContact:
    """Who answers questions about a competition (Q13): replies to its emails go to ``email``,
    and its page and the emails' footer name ``name`` (empty for a bare address).
    """

    name: str
    email: str
    user: object = None
    # Where it came from: the CASE_COMPETITION_CONTACT setting, the competition's own contact
    # email and role, or Central Office because nobody holds the role.
    source: str = "competition"


CONTACT_FROM_SETTING, CONTACT_FROM_COMPETITION, CONTACT_FROM_CENTRAL_OFFICE = "setting", "competition", "central_office"


def competition_contact(competition):
    """The competition contact: the ``CASE_COMPETITION_CONTACT`` setting when it names someone,
    else the competition's contact email and the holder of its contact role, else Central Office.

    The setting takes a username or email of a CMT account, a National Officer role or any email
    address, so replies reach someone while the contact role is vacant (owner, 2026-11-23). A
    setting that names a vacant role, or nothing usable, is skipped.
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    from thetatauCMT.support.services import config_list

    for value in config_list(CONTACT_CONFIG_KEY)[:1]:
        person = resolve_config_actor(value)
        if person is not None and person.email:
            return CompetitionContact(person.name, person.email, person, CONTACT_FROM_SETTING)
        try:
            validate_email(value)
        except ValidationError:
            continue
        return CompetitionContact("", value, None, CONTACT_FROM_SETTING)
    person = resolve_config_actor(competition.contact_role) if competition.contact_role else None
    if competition.contact_email:
        return CompetitionContact(
            person.name if person is not None else "", competition.contact_email, person, CONTACT_FROM_COMPETITION
        )
    if person is not None and person.email:
        return CompetitionContact(person.name, person.email, person, CONTACT_FROM_COMPETITION)
    return CompetitionContact(CENTRAL_OFFICE_NAME, CENTRAL_OFFICE_EMAIL, None, CONTACT_FROM_CENTRAL_OFFICE)


def reply_to(competition):
    """Replies to every competition email go to the competition contact (Q13)."""
    return [competition_contact(competition).email]


def chapter_recipients(chapter, competition=None):
    """Who gets a chapter's competition emails (Q13 A and C).

    The named contacts, the five chapter officers and the chapter's generic addresses
    (``Chapter.council_emails``), and the holders of :func:`email_roles` in the chapter.
    Never ``get_email_specific`` with a committee role (Gotchas 6).
    """
    emails = list(chapter.council_emails())
    emails += chapter.members.filter(current_roles__overlap=sorted(email_roles())).values_list("email", flat=True)
    if competition is not None:
        participant = Participant.objects.filter(competition=competition, chapter=chapter).first()
        if participant is not None:
            emails += participant.contacts.values_list("email", flat=True)
    return _unique_emails(emails)


def manager_emails(competition):
    """Who gets the managers' emails (E6): the people named as managers, else the contact."""
    from thetatauCMT.users.models import User

    emails = User.objects.filter(pk__in=manager_ids(), is_active=True).values_list("email", flat=True)
    return _unique_emails(emails) or reply_to(competition)


# --- Which competition -------------------------------------------------------------------


def visible_competitions(user):
    """Published competitions; managers also see unpublished ones (S3)."""
    if can_manage(user):
        return Competition.objects.all()
    return Competition.objects.published()


def can_view_competition(user, competition):
    return is_signed_in(user) and (competition.is_published or can_manage(user))


def current_competition(user=None):
    """The newest published competition; for a manager, the newest of all when none is published yet."""
    published = Competition.objects.published().first()
    if published is not None or user is None or not can_manage(user):
        return published
    return Competition.objects.first()


# --- Time (S4, S7, S14) ------------------------------------------------------------------


def grace(round_):
    return datetime.timedelta(minutes=round_.grace_minutes or 0)


def deadline_for(round_, entry=None):
    """The chapter's deadline: the round's close, or a later extension on its entry (S7)."""
    override = getattr(entry, "deadline_override", None)
    if override is not None and override > round_.closes_at:
        return override
    return round_.closes_at


def round_state(round_, now=None):
    """``upcoming``, ``open``, ``judging`` or ``published``, as pages show it (no grace minutes)."""
    now = _now(now)
    if round_.is_published:
        return PUBLISHED
    if now < round_.opens_at:
        return UPCOMING
    if now < round_.closes_at:
        return OPEN
    return JUDGING


def window_open(round_, entry=None, now=None):
    """Whether the chapter's window is open, as pages show it: the close, or its extension."""
    now = _now(now)
    return not round_.is_published and round_.opens_at <= now < deadline_for(round_, entry)


def accepts_upload(round_, entry=None, now=None):
    """Whether a save arriving now is accepted: the window or extension, plus the grace minutes (S7)."""
    now = _now(now)
    return not round_.is_published and round_.opens_at <= now < deadline_for(round_, entry) + grace(round_)


def judging_started(round_, entry=None, now=None):
    """Judges see an entry once its window, or its extension, has fully closed (S14)."""
    return _now(now) >= deadline_for(round_, entry) + grace(round_)


def intent_open(competition, now=None):
    """The intent window needs both dates; it is open from the first until the second."""
    now = _now(now)
    opens, closes = competition.intent_opens_at, competition.intent_closes_at
    return bool(opens and closes and opens <= now < closes)


def participation_closes_at(competition):
    """Registered chapters change contacts, withdraw or rejoin until the last round closes (S31)."""
    closes = [round_.closes_at for round_ in competition.rounds.all()]
    return max(closes) if closes else competition.intent_closes_at


def open_round(competition, now=None):
    """The round whose window is open now, else the next one to open, else None."""
    now = _now(now)
    rounds = list(competition.rounds.all())
    for round_ in rounds:
        if window_open(round_, now=now):
            return round_
    upcoming = [round_ for round_ in rounds if now < round_.opens_at]
    return upcoming[0] if upcoming else None


# --- People (Q6 B, S29) ------------------------------------------------------------------


def is_chapter_member(user, chapter):
    """A current member or PNM of ``chapter``, by their own chapter (never the region bar, S29)."""
    chapter_id = getattr(chapter, "pk", chapter)
    return (
        is_signed_in(user)
        and chapter_id is not None
        and user.chapter_id == chapter_id
        and getattr(user, "current_status", "") in MEMBER_STATUSES
    )


def member_chapter(user):
    """The chapter ``user`` is a member of (S29), or None."""
    if is_signed_in(user) and getattr(user, "current_status", "") in MEMBER_STATUSES:
        return user.chapter
    return None


def panel_chapter(user):
    """The chapter the "Your chapter" panel shows: the one the viewer is looking at.

    Their own chapter; for a Chapter Support Specialist standing in, the assigned chapter they
    are viewing (S21); for a National Officer, the chapter chosen in the region bar, like every
    other page (owner, 2026-11-23). Looking at a chapter never makes anyone a member (S29).
    """
    if not is_signed_in(user):
        return None
    return user.current_chapter


def supports(user, chapter):
    from thetatauCMT.support.services import supports as css_supports

    return is_signed_in(user) and css_supports(user, chapter)


# --- Who takes part ----------------------------------------------------------------------


def participant_for(competition, chapter):
    if chapter is None:
        return None
    return Participant.objects.filter(competition=competition, chapter=chapter).first()


def previous_round(round_):
    return (
        Round.objects.filter(competition_id=round_.competition_id, number__lt=round_.number).order_by("-number").first()
    )


def next_round(round_):
    return (
        Round.objects.filter(competition_id=round_.competition_id, number__gt=round_.number).order_by("number").first()
    )


def withdrawn_chapter_ids(competition):
    return set(
        Participant.objects.filter(competition=competition, withdrawn_at__isnull=False).values_list(
            "chapter_id", flat=True
        )
    )


def qualifier_chapter_ids(round_):
    """For a round taking qualifiers: the previous round's, once its results are published."""
    previous = previous_round(round_)
    if previous is None or not previous.is_published:
        return set()
    qualifiers = set(previous.entries.filter(advanced=True, chapter__active=True).values_list("chapter_id", flat=True))
    return qualifiers - withdrawn_chapter_ids(round_.competition)


def eligible_chapter_ids(round_):
    """The chapters a round reminds (R11): registered and not withdrawn, or the qualifiers."""
    if round_.eligibility == Round.Eligibility.ADVANCED:
        return qualifier_chapter_ids(round_)
    return set(
        Participant.objects.active()
        .filter(competition_id=round_.competition_id, chapter__active=True)
        .values_list("chapter_id", flat=True)
    )


def chapter_may_enter(round_, chapter, qualifiers=None):
    """Whether ``chapter`` may have an entry: any active chapter (Q7 A), or a qualifier.

    ``qualifiers``: the round's qualifying chapter ids, when the caller already has them.
    """
    if chapter is None or not chapter.active:
        return False
    if round_.eligibility == Round.Eligibility.ADVANCED:
        if qualifiers is None:
            qualifiers = qualifier_chapter_ids(round_)
        return chapter.pk in qualifiers
    return True


def not_selected(round_, previous_entry, may_enter):
    """Whether a chapter that cannot enter ``round_`` had a complete entry in the previous round,
    whose results are out: it was not selected (owner, 2026-11-20: only qualifiers submit the final).
    """
    return (
        not may_enter
        and round_.eligibility == Round.Eligibility.ADVANCED
        and previous_entry is not None
        and previous_entry.round.is_published
        and previous_entry.submitted_at is not None
    )


def entry_round(competition):
    """The round any active chapter may enter, registered or not (Q7 A): the proposal.

    Later rounds take only the previous round's qualifiers (owner, 2026-11-20).
    """
    return competition.rounds.filter(eligibility=Round.Eligibility.PARTICIPANTS).order_by("number").first()


def late_entry_open(competition, now=None):
    """Whether a chapter that did not register can still take part, by uploading its proposal."""
    round_ = entry_round(competition)
    return round_ is not None and not round_.is_published and _now(now) < round_.closes_at


def can_register(user, competition, chapter, now=None):
    """Register the chapter (declare intent): a member of it, while the intent window is open (Q6 B)."""
    return (
        competition.is_published
        and chapter is not None
        and chapter.active
        and is_chapter_member(user, chapter)
        and intent_open(competition, now)
    )


def can_update_participation(user, participant, now=None):
    """Change contacts, team size and note, or withdraw and rejoin: a member, until the last round closes (S31)."""
    closes = participation_closes_at(participant.competition)
    return (
        participant.competition.is_published
        and participant.chapter.active
        and is_chapter_member(user, participant.chapter)
        and (closes is None or _now(now) < closes)
    )


@dataclass
class Registration:
    participant: Participant
    created: bool = False
    rejoined: bool = False


@transaction.atomic
def register(
    competition,
    chapter,
    by=None,
    source=Participant.Source.INTENT,
    contacts=None,
    team_size_estimate=None,
    note=None,
    welcome=True,
):
    """Register ``chapter``, or update its registration; registering twice changes nothing more.

    Undoes a withdrawal. ``contacts``, ``team_size_estimate`` and ``note`` are only changed
    when given. A chapter registering itself gets the welcome email (E1) once the request
    commits; chapters added in Django admin get the next reminder instead (S30).
    """
    participant, created = Participant.objects.get_or_create(
        competition=competition,
        chapter=chapter,
        defaults={
            "source": source,
            "declared_by": by,
            "team_size_estimate": team_size_estimate,
            "note": note or "",
        },
    )
    rejoined = False
    if not created:
        changed = []
        if team_size_estimate is not None or note is not None:
            participant.team_size_estimate = team_size_estimate
            participant.note = note or ""
            changed += ["team_size_estimate", "note"]
        if participant.withdrawn_at is not None:
            participant.withdrawn_at = None
            participant.withdrawn_by = None
            changed += ["withdrawn_at", "withdrawn_by"]
            rejoined = True
        if changed:
            participant.save(update_fields=[*changed, "modified"])
    if contacts is not None:
        participant.contacts.set(contacts)
    if created and welcome and source != Participant.Source.ADMIN:
        from .notifications import send_welcome

        transaction.on_commit(lambda: send_welcome(participant.pk))
    return Registration(participant=participant, created=created, rejoined=rejoined)


def withdraw(participant, by=None, now=None):
    """Withdraw the chapter, which stops its reminders (S23). Returns False when it already was."""
    if participant.withdrawn_at is not None:
        return False
    participant.withdrawn_at = _now(now)
    participant.withdrawn_by = by
    participant.save(update_fields=["withdrawn_at", "withdrawn_by", "modified"])
    return True


# --- Entries (S5, S6) ----------------------------------------------------------------------


def entry_for(round_, chapter):
    if chapter is None:
        return None
    return Entry.objects.filter(round=round_, chapter=chapter).first()


def current_files(entry):
    """``{item id: EntryFile}`` for the entry's current files.

    Uses ``entry.current_file_list`` when a page prefetched it (see :func:`entries_with_files`).
    """
    if entry is None or entry.pk is None:
        return {}
    rows = getattr(entry, "current_file_list", None)
    if rows is None:
        rows = entry.files.filter(replaced_at__isnull=True)
    return {entry_file.item_id: entry_file for entry_file in rows}


def entries_with_files(queryset):
    """Entries with their current files (and their round's items) prefetched, for pages listing many."""
    from django.db.models import Prefetch

    return queryset.select_related("chapter", "chapter__region", "round", "round__competition").prefetch_related(
        "round__items",
        Prefetch(
            "files",
            queryset=EntryFile.objects.filter(replaced_at__isnull=True).select_related("item"),
            to_attr="current_file_list",
        ),
    )


def round_progress(round_):
    """For the managers (E6 and the status page): complete entries, the eligible chapters still
    without one, and the incomplete entries with an extension.
    """
    from thetatauCMT.chapters.models import Chapter

    entries = list(entries_with_files(round_.entries.order_by("chapter__name")))
    complete = [entry for entry in entries if entry_is_complete(entry)]
    complete_ids = {entry.chapter_id for entry in complete}
    waiting = list(
        Chapter.objects.filter(pk__in=eligible_chapter_ids(round_) - complete_ids)
        .select_related("region")
        .order_by("name")
    )
    extended = [
        entry
        for entry in entries
        if entry.chapter_id not in complete_ids and deadline_for(round_, entry) != round_.closes_at
    ]
    return complete, waiting, extended


def missing_items(entry, round_=None):
    """What the entry still needs to count as submitted (S6), as labels."""
    round_ = round_ or entry.round
    missing = []
    if entry is None or not (entry.title or "").strip():
        missing.append("Project title")
    if entry is None or not (entry.summary or "").strip():
        missing.append("Summary")
    files = current_files(entry)
    missing += [item.label for item in round_.items.all() if item.required and item.pk not in files]
    return missing


def entry_is_complete(entry):
    return entry is not None and not missing_items(entry)


def past_due(round_, entry=None, now=None):
    """Whether the chapter's deadline (the close, or its extension) has passed, or the results are out."""
    return round_.is_published or _now(now) >= deadline_for(round_, entry)


def entry_status(entry, round_=None, now=None):
    """``submitted`` once complete; before the chapter's deadline ``in_progress`` or
    ``not_started``; after it ``incomplete`` or ``not_submitted``, since nothing can change.
    """
    if entry is not None and entry_is_complete(entry):
        return SUBMITTED
    started = entry is not None and bool(
        (entry.title or "").strip() or (entry.summary or "").strip() or current_files(entry)
    )
    round_ = round_ or getattr(entry, "round", None)
    if round_ is not None and past_due(round_, entry, now):
        return INCOMPLETE if started else NOT_SUBMITTED
    return IN_PROGRESS if started else NOT_STARTED


def can_submit(user, round_, chapter, now=None, posting=False):
    """Save the chapter's entry: any member of the chapter (Q6 B, Q26 A) while its window is open.

    ``posting`` adds the grace minutes, for a save already under way at the close (S7).
    """
    if not (round_.competition.is_published and is_chapter_member(user, chapter)):
        return False
    if not chapter_may_enter(round_, chapter):
        return False
    entry = entry_for(round_, chapter)
    return accepts_upload(round_, entry, now) if posting else window_open(round_, entry, now)


def can_submit_on_behalf(user, round_, chapter):
    """Managers upload for a chapter at any time until results are published (S7)."""
    return can_manage(user) and not round_.is_published and chapter_may_enter(round_, chapter)


def is_showcased(entry):
    """Visible to every signed-in member after results (Q22 A).

    The qualifiers' proposals once a round's results are published; for a round awarding
    places, every complete final submission once the winners are announced.
    """
    round_ = entry.round
    if not round_.is_published or not entry.eligible:
        return False
    if round_.selection == Round.Selection.ADVANCE:
        return bool(entry.advanced)
    return entry.submitted_at is not None


def judge_can_open(user, entry, now=None):
    """A judge of the round with an assignment for the entry, once judging has started for it (S14)."""
    if not is_signed_in(user):
        return False
    assigned = Assignment.objects.filter(entry=entry, judge__user=user, judge__removed_at__isnull=True).exists()
    return assigned and judging_started(entry.round, entry, now)


def can_view_entry(user, entry, now=None):
    """The permission matrix: managers; members of the chapter and its CSSs; the round's judges
    after the close; everyone signed in once the entry is showcased.
    """
    if not is_signed_in(user):
        return False
    if can_manage(user):
        return True
    if not entry.round.competition.is_published:
        return False
    if is_chapter_member(user, entry.chapter) or supports(user, entry.chapter):
        return True
    return is_showcased(entry) or judge_can_open(user, entry, now)


def can_view_file(user, entry_file, now=None):
    """As :func:`can_view_entry`; replaced files are for managers only (S5)."""
    if entry_file.replaced_at is not None:
        return can_manage(user)
    return can_view_entry(user, entry_file.entry, now)


@dataclass
class SaveResult:
    entry: Entry
    complete: bool = False
    first_complete: bool = False
    registered: bool = False
    added: list = field(default_factory=list)


def _retire_current(entry, item, now):
    entry.files.filter(item=item, replaced_at__isnull=True).update(replaced_at=now, modified=now)


@transaction.atomic
def save_entry(round_, chapter, by, *, title, summary, uploads=None, links=None, on_behalf=False, now=None):
    """Save a chapter's entry: its details, plus any new file or link for each item.

    ``uploads`` maps items to uploaded files and ``links`` items to addresses. A new file or
    link replaces the item's current one, which is kept for managers (S5). The first save
    from an unregistered chapter registers it (Q7 A). Every save that leaves the entry
    complete sends the receipt (E5) once the request commits; the first one sets
    ``submitted_at`` (S6). Callers check the permission first.
    """
    now = _now(now)
    entry, _ = Entry.objects.select_for_update().get_or_create(round=round_, chapter=chapter)
    entry.title = (title or "").strip()
    entry.summary = (summary or "").strip()
    added = []
    for item, upload in (uploads or {}).items():
        _retire_current(entry, item, now)
        EntryFile.objects.create(
            entry=entry,
            item=item,
            file=upload,
            original_name=(upload.name or "")[:255],
            size=upload.size,
            uploaded_by=by,
        )
        added.append(item.label)
    current = current_files(entry)
    for item, link in (links or {}).items():
        existing = current.get(item.pk)
        if existing is not None and existing.link == link:
            continue
        if not link:
            # An emptied link removes the current one, which is kept for managers like a replaced file.
            if existing is not None:
                _retire_current(entry, item, now)
            continue
        _retire_current(entry, item, now)
        EntryFile.objects.create(entry=entry, item=item, link=link, uploaded_by=by)
        added.append(item.label)
    entry.last_saved_at = now
    entry.last_saved_by = by
    entry.last_saved_on_behalf = on_behalf
    complete = entry_is_complete(entry)
    first_complete = complete and entry.submitted_at is None
    if first_complete:
        entry.submitted_at = now
    entry.save()
    registered = False
    if round_.eligibility == Round.Eligibility.PARTICIPANTS:
        registration = register(
            round_.competition, chapter, by=by, source=Participant.Source.SUBMISSION, welcome=not on_behalf
        )
        registered = registration.created or registration.rejoined
    if complete:
        from .notifications import send_receipt

        saved_by_id = getattr(by, "pk", None)
        transaction.on_commit(lambda: send_receipt(entry.pk, saved_by_id))
    return SaveResult(entry=entry, complete=complete, first_complete=first_complete, registered=registered, added=added)


def extend_deadline(round_, chapter, until, by=None):
    """Give one chapter its own later deadline for the round (S7); ``None`` removes it."""
    if not chapter_may_enter(round_, chapter):
        raise CompetitionError(f"The {chapter.full_name} cannot enter the {round_.name}.")
    if until is not None and until <= round_.closes_at:
        raise CompetitionError("An extension must end after the window closes.")
    entry, _ = Entry.objects.get_or_create(round=round_, chapter=chapter)
    entry.deadline_override = until
    entry.save(update_fields=["deadline_override", "modified"])
    return entry


# --- The "Your chapter" panel and the home page card (NECCWI-4, S24) ---------------------------


@dataclass
class RoundPanel:
    round: Round
    state: str
    state_label: str
    opens: str
    due: str
    extended: bool
    may_enter: bool
    entry: object
    status: str
    status_label: str
    missing: list
    can_submit: bool
    can_view: bool
    result: object
    not_selected: bool = False


@dataclass
class ChapterPanel:
    chapter: object
    is_member: bool
    view_only: bool
    # Why a non-member sees the chapter's progress: as its CSS (VIEWING_AS_CSS) or as someone who
    # sees every chapter's status (VIEWING_AS_NATIONAL); empty for members and everyone else.
    viewing_as: str = ""
    own: bool = True
    region_bar: bool = False
    participant: object = None
    registered: bool = False
    withdrawn: bool = False
    can_register: bool = False
    can_update: bool = False
    intent_open: bool = False
    entry_round: object = None
    late_entry_open: bool = False
    rounds: list = field(default_factory=list)


VIEWING_AS_CSS, VIEWING_AS_NATIONAL = "css", "national"


def chapter_panel(user, competition, now=None):
    """What the "Your chapter" panel shows; None when the viewer has no active chapter.

    A member of the chapter gets its state and buttons. A CSS standing in, and anyone who sees
    every chapter's status (National Officers through the region bar, S19), see the same view
    only, opening an entry only where :func:`can_view_entry` allows (S29). Anyone else (an
    alumnus, an advisor) gets the panel without them.
    """
    from .judging import result_label

    now = _now(now)
    chapter = panel_chapter(user)
    if chapter is None or not chapter.active:
        return None
    is_member = is_chapter_member(user, chapter)
    viewing_as = ""
    if not is_member and supports(user, chapter):
        viewing_as = VIEWING_AS_CSS
    elif not is_member and can_view_status(user):
        viewing_as = VIEWING_AS_NATIONAL
    panel = ChapterPanel(
        chapter=chapter,
        is_member=is_member,
        view_only=bool(viewing_as),
        viewing_as=viewing_as,
        own=chapter.pk == user.chapter_id,
        region_bar=user.in_national_officer_group,
    )
    if not (is_member or panel.view_only):
        return panel
    participant = participant_for(competition, chapter)
    panel.participant = participant
    panel.registered = participant is not None and participant.withdrawn_at is None
    panel.withdrawn = participant is not None and participant.withdrawn_at is not None
    panel.intent_open = intent_open(competition, now)
    panel.can_register = not panel.registered and can_register(user, competition, chapter, now)
    panel.can_update = participant is not None and can_update_participation(user, participant, now)
    panel.entry_round = entry_round(competition)
    panel.late_entry_open = late_entry_open(competition, now)
    earlier_entry = None
    for round_ in competition.rounds.all():
        entry = entry_for(round_, chapter)
        status = entry_status(entry, round_, now)
        may_enter = chapter_may_enter(round_, chapter)
        state = round_state(round_, now)
        deadline = deadline_for(round_, entry)
        panel.rounds.append(
            RoundPanel(
                round=round_,
                state=state,
                state_label=STATE_LABELS[state],
                opens=competition.format_time(round_.opens_at),
                due=competition.format_time(deadline),
                extended=deadline != round_.closes_at,
                may_enter=may_enter,
                entry=entry,
                status=status,
                status_label=ENTRY_STATUS_LABELS[status],
                missing=missing_items(entry, round_) if may_enter else [],
                can_submit=can_submit(user, round_, chapter, now),
                can_view=(
                    entry is not None and status in STARTED_STATUSES and (is_member or can_view_entry(user, entry, now))
                ),
                result=result_label(entry) if entry is not None else None,
                not_selected=not_selected(round_, earlier_entry, may_enter),
            )
        )
        earlier_entry = entry
    return panel


def home_items(user, now=None):
    """The home page card (S24): what the viewer's chapter has to do now.

    Registering while the intent window is open, and each open window the chapter takes part
    in until its entry is complete. Chapters not taking part see only the first. A judge's
    scorecards have their own nudge at the top of the home page (``judging.scorecards_to_do``).
    """
    from django.urls import reverse

    now = _now(now)
    items = []
    competition = Competition.objects.published().first()
    chapter = member_chapter(user)
    if competition is not None and chapter is not None and chapter.active:
        rounds = [round_ for round_ in competition.rounds.all() if window_open(round_, now=now)]
        if rounds or intent_open(competition, now):
            participant = participant_for(competition, chapter)
            registered = participant is not None and participant.withdrawn_at is None
            if not registered and can_register(user, competition, chapter, now):
                items.append(
                    {
                        "text": f"Register the {chapter.full_name} for the {competition.name} by "
                        f"{competition.format_time(competition.intent_closes_at)}.",
                        "url": reverse("competitions:intent", args=[competition.slug]),
                        "action": "Register",
                    }
                )
            for round_ in rounds:
                if round_.eligibility == Round.Eligibility.PARTICIPANTS and not registered:
                    continue
                if not chapter_may_enter(round_, chapter):
                    continue
                entry = entry_for(round_, chapter)
                if entry_is_complete(entry):
                    continue
                items.append(
                    {
                        "text": f"The {chapter.full_name}'s {round_.name} is due "
                        f"{competition.format_time(deadline_for(round_, entry))}. "
                        f"Status: {ENTRY_STATUS_LABELS[entry_status(entry, round_, now)]}.",
                        "url": reverse("competitions:submit", args=[competition.slug, round_.number]),
                        "action": f"Open the {round_.name}",
                    }
                )
    return items


# --- The email log -------------------------------------------------------------------------


def already_sent(key):
    return NotificationLog.objects.filter(key=key).exists()


def record_sent(key, kind, competition, round_=None, chapter=None, user=None, recipients=(), now=None):
    """Log one email sent. Returns False when the key was already there (never sent twice)."""
    _, created = NotificationLog.objects.get_or_create(
        key=key,
        defaults={
            "kind": kind,
            "competition": competition,
            "round": round_,
            "chapter": chapter,
            "user": user,
            "recipients": ", ".join(recipients),
            "sent_at": _now(now),
        },
    )
    return created


# --- Copying a year's setup (NECCWI-1) -----------------------------------------------------


COMPETITION_FIELDS_NOT_COPIED = {
    "created",
    "modified",
    "year_label",
    "slug",
    "announcement",
    "is_published",
    "created_by",
    "intent_opens_at",
    "intent_closes_at",
}
# What happened during the year, rather than its setup, starts empty in a copy.
ROUND_FIELDS_NOT_COPIED = {
    "competition",
    "created",
    "modified",
    "results_published_at",
    "results_published_by",
    "rubric_locked_at",
}
ROUND_TIMES = ("opens_at", "closes_at", "judging_closes_at")
CHILD_FIELDS_NOT_COPIED = {"round", "competition", "created", "modified"}


def next_year_label(label):
    """``2026-2027`` becomes ``2027-2028`` and ``2027`` becomes ``2028``; anything else gains "(copy)"."""
    text = (label or "").strip()
    match = re.fullmatch(r"(\d{4})-(\d{4})", text)
    if match:
        return f"{int(match[1]) + 1}-{int(match[2]) + 1}"
    if re.fullmatch(r"\d{4}", text):
        return str(int(text) + 1)
    return f"{text} (copy)".strip()


def a_year_later(value, zone=None):
    """The same date, and wall-clock time in ``zone``, one year later. February 29 becomes the 28th."""
    if value is None:
        return None
    if zone is not None:
        value = timezone.localtime(value, zone)
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def _copied_fields(obj, exclude):
    return {
        field.attname: getattr(obj, field.attname)
        for field in obj._meta.concrete_fields
        if not field.primary_key and field.name not in exclude
    }


def _unique_slug(base):
    slug, number = base, 2
    while Competition.objects.filter(slug=slug).exists():
        slug = f"{base}-{number}"
        number += 1
    return slug


@transaction.atomic
def copy_to_next_year(competition, by=None):
    """Copy a competition's setup one year later: the case, key dates, rounds, rubrics and items.

    Never chapters, entries, judges, scores or results. Every date moves one year and keeps its
    time of day in the competition's time zone. The copy is not published.
    """
    zone = competition.zone
    year_label = next_year_label(competition.year_label)
    copy = Competition.objects.create(
        **_copied_fields(competition, COMPETITION_FIELDS_NOT_COPIED),
        year_label=year_label,
        slug=_unique_slug(slugify(f"{competition.short_name}-{year_label}") or "competition"),
        is_published=False,
        created_by=by,
        intent_opens_at=a_year_later(competition.intent_opens_at, zone),
        intent_closes_at=a_year_later(competition.intent_closes_at, zone),
    )
    KeyDate.objects.bulk_create(
        KeyDate(
            **_copied_fields(key_date, CHILD_FIELDS_NOT_COPIED | {"date"}),
            competition=copy,
            date=a_year_later(key_date.date),
        )
        for key_date in competition.key_dates.all()
    )
    for old_round in competition.rounds.all():
        new_round = Round.objects.create(
            **_copied_fields(old_round, ROUND_FIELDS_NOT_COPIED | set(ROUND_TIMES)),
            **{name: a_year_later(getattr(old_round, name), zone) for name in ROUND_TIMES},
            competition=copy,
        )
        RubricCriterion.objects.bulk_create(
            RubricCriterion(**_copied_fields(criterion, CHILD_FIELDS_NOT_COPIED), round=new_round)
            for criterion in old_round.criteria.all()
        )
        SubmissionItem.objects.bulk_create(
            SubmissionItem(**_copied_fields(item, CHILD_FIELDS_NOT_COPIED), round=new_round)
            for item in old_round.items.all()
        )
    return copy
