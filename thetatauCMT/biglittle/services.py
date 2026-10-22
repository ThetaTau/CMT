"""Rules for recording Bigs and Littles.

Every way of recording a pairing (initiation report, Edit My Info, the chapter pages and
the CSV upload) goes through :func:`set_big`, so the rules live in one place.
"""

import csv
import hashlib
import html
import io
import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.utils import timezone

from core.models import ALL_ROLES, user_is_national_officer
from thetatauCMT.configs.models import Config
from thetatauCMT.users.models import User

from .models import BigLittle, PendingPairing
from .names import ROSTER_FIELDS, Roster, normalize_name

# The final Big is chosen at initiation, so these members cannot be a Big or a Little (Q9).
NOT_INITIATED_STATUSES = frozenset({"pnm", "depledge", "nonmember", "friend"})
MANAGER_ROLES_CONFIG_KEY = "BIG_LITTLE_MANAGER_ROLES"
DEFAULT_MANAGER_ROLES = frozenset({"pledge/new member educator"})
ROLE_LABELS = {"pledge/new member educator": "New Member Educator"}
NO_BADGE_NUMBER = 999999999
# Far deeper than any real family line; only bad data could reach it.
CYCLE_WALK_LIMIT = 500

CREATED = "created"
CHANGED = "changed"
UNCHANGED = "unchanged"
ERROR = "error"
REVIEW = "review"
SKIPPED = "skipped"

SIDES = ("big", "little")
CSV_HEADERS = ("badge_number_big", "badge_number_little")
NAME_CSV_HEADERS = ("little_full_name", "big_full_name")
BADGE_COLUMNS = {"big": "badge_number_big", "little": "badge_number_little"}
NAME_COLUMNS = {"big": ("big_full_name", "big_name"), "little": ("little_full_name", "little_name")}
HEADER_ERROR = (
    "The first row must name a Big column (badge_number_big or big_full_name) and a Little "
    "column (badge_number_little or little_full_name)."
)
MAX_UPLOAD_ROWS = 5000
# Nine digits covers every badge number and stays inside the integer column.
MAX_BADGE_DIGITS = 9


class BigLittleError(ValidationError):
    """A pairing the rules do not allow."""


@dataclass
class SetBigResult:
    link: BigLittle
    outcome: str
    previous_big: User | None = None


def is_initiated(user):
    return user.current_status not in NOT_INITIATED_STATUSES


def eligible_members(chapter):
    """The members of ``chapter`` who can be picked as a Big or a Little."""
    if chapter is None:
        return User.objects.none()
    return chapter.members.exclude(current_status__in=NOT_INITIATED_STATUSES).order_by("name")


def has_badge_number(user):
    return bool(user.badge_number) and user.badge_number < NO_BADGE_NUMBER


def member_label(user):
    return _label(user.name, user.badge_number)


def _label(name, badge_number):
    if badge_number and badge_number < NO_BADGE_NUMBER:
        return f"{name} (#{badge_number})"
    return name


def link_chapter_for(little):
    """The Little's initiation chapter, so a later transfer does not move the pairing (S1)."""
    initiation = getattr(little, "initiation", None)
    if initiation is not None and initiation.chapter_id:
        return initiation.chapter
    return little.chapter


def current_big_link(user):
    return user.links_as_little.current().select_related("big", "created_by").first()


def current_big(user):
    link = current_big_link(user)
    return link.big if link else None


def current_little_links(user):
    return (
        user.links_as_big.current()
        .select_related("little", "created_by")
        .order_by("little__badge_number", "little__name")
    )


def member_rows(chapter):
    """The chapter's eligible members, each with their current Big and Littles count."""
    current = BigLittle.objects.filter(little=OuterRef("pk"), ended__isnull=True)
    return eligible_members(chapter).annotate(
        link_pk=Subquery(current.values("pk")[:1]),
        big_name=Subquery(current.values("big__name")[:1]),
        big_username=Subquery(current.values("big__username")[:1]),
        little_count=Count("links_as_big", filter=Q(links_as_big__ended__isnull=True)),
        initiation_date=F("initiation__date"),
    )


def members_without_big(chapter):
    current = BigLittle.objects.filter(little=OuterRef("pk"), ended__isnull=True)
    return eligible_members(chapter).filter(~Exists(current))


def tree_members(chapter):
    """Everyone drawn in the chapter's family tree: both people in each current pairing."""
    links = BigLittle.objects.current().filter(chapter=chapter)
    return User.objects.filter(Q(pk__in=links.values("big")) | Q(pk__in=links.values("little")))


def search_members(queryset, term):
    """Members whose name contains ``term``, or whose badge number it is."""
    term = (term or "").strip()
    if not term:
        return queryset
    match = Q(name__icontains=term)
    if term.isdigit() and len(term) <= MAX_BADGE_DIGITS:
        match |= Q(badge_number=int(term))
    return queryset.filter(match)


def get_manager_roles():
    """Roles that may manage the whole chapter's pairings besides officers (Q4)."""
    raw = html.unescape(Config.get_value(MANAGER_ROLES_CONFIG_KEY))
    roles = {part.strip().lower() for part in raw.split(",")} & set(ALL_ROLES)
    return frozenset(roles) or DEFAULT_MANAGER_ROLES


def manager_roles_label():
    labels = [f"the {ROLE_LABELS.get(role, role.title())}" for role in sorted(get_manager_roles())]
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def can_manage(user, chapter):
    """Whether ``user`` may record or remove anyone's pairing in ``chapter`` (Q4).

    Only for the chapter the user is acting in, so National Officers and Admins manage
    another chapter through the chapter switcher, like every other chapter page.
    """
    if chapter is None or not getattr(user, "is_authenticated", False):
        return False
    if user.current_chapter.pk != chapter.pk:
        return False
    if user.is_admin or user.is_national_officer_group:
        return True
    if user.natoff_hidden:
        # Same rule as core.views.OfficerRequiredMixin while viewing as a member.
        if user.chapter_officer():
            return True
    elif user.is_chapter_officer_group:
        return True
    return bool(set(user.current_roles or []) & get_manager_roles())


def can_remove(user, link):
    """The Little, the Big when they recorded it themselves, or a chapter manager (Q3)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.pk == link.little_id:
        return True
    if user.pk == link.big_id and user.pk == link.created_by_id:
        return True
    return can_manage(user, link.chapter)


def can_view_tree(user, chapter):
    """Members of the chapter, RDs of its region, National Officers and Admins (Q2)."""
    if chapter is None or not getattr(user, "is_authenticated", False):
        return False
    if chapter.pk in (user.chapter_id, user.current_chapter.pk):
        return True
    if user.is_admin or user_is_national_officer(user):
        return True
    if user.natoff_hidden or chapter.region_id is None:
        return False
    return user.regional_director.filter(pk=chapter.region_id).exists()


def would_create_cycle(little, big):
    """True when ``big`` already descends from ``little``."""
    node_id = big.pk
    seen = set()
    for _ in range(CYCLE_WALK_LIMIT):
        if node_id == little.pk:
            return True
        if node_id is None or node_id in seen:
            return False
        seen.add(node_id)
        node_id = BigLittle.objects.current().filter(little_id=node_id).values_list("big_id", flat=True).first()
    return True


def validate_pairing(little, big):
    if little.pk == big.pk:
        raise BigLittleError("A member cannot be their own Big.")
    if would_create_cycle(little, big):
        raise BigLittleError(
            f"{big} is one of {little}'s Littles, or further down {little}'s family line, "
            f"so {big} cannot also be {little}'s Big."
        )


def set_big(little, big, *, actor=None, source, chapter=None):
    """Make ``big`` the current Big of ``little``.

    A different Big ends the old pairing instead of editing it; ended pairings only show
    in Django admin (Q1). Recording the same Big again changes nothing.
    """
    validate_pairing(little, big)
    try:
        with transaction.atomic():
            current = (
                BigLittle.objects.select_for_update(of=("self",))
                .select_related("big")
                .filter(little=little, ended__isnull=True)
                .first()
            )
            if current is not None and current.big_id == big.pk:
                return SetBigResult(current, UNCHANGED)
            previous = current.big if current is not None else None
            if current is not None:
                current.ended = timezone.now()
                current.ended_by = actor
                current.save(update_fields=["ended", "ended_by", "modified"])
            link = BigLittle.objects.create(
                big=big,
                little=little,
                chapter=chapter or link_chapter_for(little),
                source=source,
                created_by=actor,
            )
    except IntegrityError as error:
        raise BigLittleError(
            f"Someone else just recorded a Big for {little}. Reload the page and try again."
        ) from error
    return SetBigResult(link, CHANGED if previous is not None else CREATED, previous)


def remove_link(link):
    """Delete a pairing entered by mistake (S2). A real change goes through :func:`set_big`."""
    link.delete()


@dataclass
class ImportRow:
    line: int
    big_badge: str = ""
    little_badge: str = ""
    big_name: str = ""
    little_name: str = ""
    big: User | None = None
    little: User | None = None
    outcome: str = ""
    message: str = ""

    @property
    def big_text(self):
        return self.big_badge or self.big_name

    @property
    def little_text(self):
        return self.little_badge or self.little_name


@dataclass
class ImportResult:
    rows: list = field(default_factory=list)
    error: str = ""

    def count(self, outcome):
        return sum(1 for row in self.rows if row.outcome == outcome)

    @property
    def review_count(self):
        return self.count(REVIEW)

    @property
    def summary(self):
        return (
            f"Processed {len(self.rows)} row(s): {self.count(CREATED)} recorded, "
            f"{self.count(CHANGED)} changed, {self.count(UNCHANGED)} unchanged, "
            f"{self.count(REVIEW)} waiting for review, {self.count(SKIPPED)} skipped, "
            f"{self.count(ERROR)} with errors."
        )


@dataclass
class _Found:
    """One side of a row: the member it names, a problem, or why a manager has to pick."""

    member_id: int | None = None
    error: str = ""
    unsure: str = ""
    suggestions: list = field(default_factory=list)


def _header_key(value):
    return re.sub(r"[\s-]+", "_", (value or "").strip().lower())


def _cell(cells, index):
    return cells[index].strip() if index is not None and index < len(cells) else ""


def _columns(headers):
    """Each side's badge and name column positions, or None when a side has neither."""
    columns = {}
    for side in SIDES:
        badge = headers.index(BADGE_COLUMNS[side]) if BADGE_COLUMNS[side] in headers else None
        name = next((headers.index(title) for title in NAME_COLUMNS[side] if title in headers), None)
        if badge is None and name is None:
            return None
        columns[side] = (badge, name)
    return columns


def _kind(badge_column, name_column):
    """What a side's cell holds, for the "is missing" message."""
    if name_column is None:
        return "badge number"
    if badge_column is None:
        return "name"
    return "badge number or name"


def _read_rows(file_bytes):
    """The upload's data rows and what each side holds, or why the whole file was refused."""
    reader = csv.reader(io.StringIO(file_bytes.decode("utf-8-sig", errors="replace")))
    columns = _columns([_header_key(cell) for cell in next(reader, [])])
    if columns is None:
        return [], {}, HEADER_ERROR
    rows = []
    for line, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) == MAX_UPLOAD_ROWS:
            return [], {}, f"The file has more than {MAX_UPLOAD_ROWS:,} rows. Split it into smaller files."
        values = {}
        for side, (badge, name) in columns.items():
            values[f"{side}_badge"] = _cell(cells, badge)
            values[f"{side}_name"] = _cell(cells, name)
        rows.append(ImportRow(line, **values))
    return rows, {side: _kind(*columns[side]) for side in SIDES}, ""


def _parse_badge(value):
    return int(value) if value.isdigit() and len(value) <= MAX_BADGE_DIGITS else None


def _roster(chapter):
    """Every member of the chapter in one query; only initiated members are suggested."""
    return Roster(
        chapter.members.values(*ROSTER_FIELDS),
        can_suggest=lambda member: member["current_status"] not in NOT_INITIATED_STATUSES,
    )


def _find(row, side, chapter, roster, kind):
    """Look one side up by badge number when the row has one, otherwise by name."""
    badge, name = getattr(row, f"{side}_badge"), getattr(row, f"{side}_name")
    if badge:
        number = _parse_badge(badge)
        if number is None:
            return _Found(error=f'"{badge}" is not a badge number.')
        members = roster.with_badge(number)
        if not members:
            return _Found(error=f"No member of {chapter} has badge number {number}.")
        if len(members) > 1:
            return _Found(error=f"More than one member of {chapter} has badge number {number}. Fix the roster first.")
        return _Found(member_id=members[0])
    if name:
        match = roster.match(name)
        if match.member_id is not None:
            return _Found(member_id=match.member_id)
        if match.exact_count:
            return _Found(unsure=f'More than one member of {chapter} is named "{name}".', suggestions=match.suggestions)
        return _Found(unsure=f'No member of {chapter} is named exactly "{name}".', suggestions=match.suggestions)
    return _Found(error=f"The {side.title()} {kind} is missing.")


def _load_members(member_ids):
    """The members found in the file, with what :func:`set_big` reads already loaded."""
    return User.objects.select_related("chapter", "initiation__chapter").in_bulk(member_ids)


def _row_problem(row, found, first_line_for_little):
    """Why the row cannot be saved or reviewed, checking the sides that were found."""
    for side in SIDES:
        if found[side].error:
            return found[side].error
    if row.big is not None and row.little is not None and row.big.pk == row.little.pk:
        return "A member cannot be their own Big."
    if row.little is not None and not is_initiated(row.little):
        return f"{row.little} is not initiated, so they cannot have a Big yet."
    if row.big is not None and not is_initiated(row.big):
        return f"{row.big} is not initiated, so they cannot be a Big."
    if row.little is not None:
        first_line = first_line_for_little.setdefault(row.little.pk, row.line)
        if first_line != row.line:
            return f"{row.little} is already listed on line {first_line}."
    return ""


def _save_row(row, actor):
    try:
        saved = set_big(row.little, row.big, actor=actor, source=BigLittle.Source.UPLOAD)
    except BigLittleError as problem:
        row.outcome, row.message = ERROR, problem.messages[0]
        return
    row.outcome = saved.outcome
    row.message = {
        CREATED: "Recorded",
        CHANGED: f"Changed (was {saved.previous_big})",
        UNCHANGED: "No change",
    }[saved.outcome]


def _fingerprint(chapter, row):
    text = f"{chapter.pk}|{normalize_name(row.little_text)}|{normalize_name(row.big_text)}"
    return hashlib.sha256(text.encode()).hexdigest()


def _send_to_review(row, found, chapter, actor):
    """Queue the row for the review page, or reuse the answer given there before."""
    latest = {
        "line": row.line,
        "little_text": row.little_text[:255],
        "big_text": row.big_text[:255],
        "little": row.little,
        "big": row.big,
        "little_suggestions": found["little"].suggestions,
        "big_suggestions": found["big"].suggestions,
        "uploaded_by": actor,
    }
    item, created = PendingPairing.objects.get_or_create(
        chapter=chapter, fingerprint=_fingerprint(chapter, row), defaults=latest
    )
    if item.status == PendingPairing.Status.DISMISSED:
        row.outcome, row.message = SKIPPED, "Skipped: this row was dismissed on the review page."
        return
    if item.status == PendingPairing.Status.SAVED and item.little_id and item.big_id:
        row.little, row.big = item.little, item.big
        _save_row(row, actor)
        if row.outcome != ERROR:
            row.message += ", using the members picked on the review page"
        return
    if not created:
        for name, value in latest.items():
            setattr(item, name, value)
        item.status = PendingPairing.Status.PENDING
        item.save()
    notes = [found[side].unsure for side in SIDES if found[side].unsure]
    ending = "Choose the members on the review page." if len(notes) > 1 else "Choose the member on the review page."
    row.outcome, row.message = REVIEW, " ".join([*notes, ending])


def import_big_little_csv(file_bytes, chapter, actor):
    """Record the pairings in an uploaded CSV of badge numbers or names (BLWI-7, BLWI-12).

    Badge numbers and names only identify a member within a chapter, so every one is
    looked up in ``chapter``. All rows are checked before any is saved; good rows are then
    saved one at a time, so a row with a problem never blocks the rest of the file. A name
    that does not match exactly one member sends its row to the review page instead.
    """
    rows, kinds, error = _read_rows(file_bytes)
    result = ImportResult(rows=rows, error=error)
    if error:
        return result
    roster = _roster(chapter)
    found = [{side: _find(row, side, chapter, roster, kinds[side]) for side in SIDES} for row in rows]
    members = _load_members({match.member_id for sides in found for match in sides.values()} - {None})
    first_line_for_little = {}
    for row, sides in zip(rows, found):
        row.big, row.little = (members.get(sides[side].member_id) for side in SIDES)
        row.message = _row_problem(row, sides, first_line_for_little)
        if row.message:
            row.outcome = ERROR
    for row, sides in zip(rows, found):
        if row.outcome == ERROR:
            continue
        if any(sides[side].unsure for side in SIDES):
            _send_to_review(row, sides, chapter, actor)
        else:
            _save_row(row, actor)
    return result


def pending_rows(chapter):
    """Uploaded rows waiting on the review page."""
    return PendingPairing.objects.filter(chapter=chapter, status=PendingPairing.Status.PENDING)


def review_choices(items, chapter):
    """Choices for each waiting row and side: the member matched on upload, else the suggestions.

    Keyed by ``(item.pk, side)``. Members who can no longer be picked, such as one who left
    the chapter since the upload, are left out.
    """
    wanted = set()
    for item in items:
        for side in SIDES:
            wanted.add(getattr(item, f"{side}_id"))
            wanted.update(suggestion["pk"] for suggestion in getattr(item, f"{side}_suggestions"))
    labels = {
        member["pk"]: _label(member["name"], member["badge_number"])
        for member in eligible_members(chapter).filter(pk__in=wanted - {None}).values("pk", "name", "badge_number")
    }
    choices = {}
    for item in items:
        for side in SIDES:
            matched = getattr(item, f"{side}_id")
            if matched is not None:
                options = [(matched, f"{labels[matched]}, matched in the file")] if matched in labels else []
            else:
                options = [
                    (suggestion["pk"], f"{labels[suggestion['pk']]}, {suggestion['score']:.0%} match")
                    for suggestion in getattr(item, f"{side}_suggestions")
                    if suggestion["pk"] in labels
                ]
            choices[item.pk, side] = options
    return choices


def _close(item, status, actor, **members):
    for name, member in members.items():
        setattr(item, name, member)
    item.status, item.resolved_by, item.resolved_at = status, actor, timezone.now()
    item.save(update_fields=["status", "resolved_by", "resolved_at", "modified", *members])


def save_pending(item, little, big, actor):
    """Record the pairing a manager picked for an uploaded row, and close the row."""
    with transaction.atomic():
        saved = set_big(little, big, actor=actor, source=BigLittle.Source.UPLOAD)
        _close(item, PendingPairing.Status.SAVED, actor, little=little, big=big)
    return saved


def dismiss_pending(item, actor):
    """Close an uploaded row without saving it, for example a name nobody recognizes."""
    _close(item, PendingPairing.Status.DISMISSED, actor)
