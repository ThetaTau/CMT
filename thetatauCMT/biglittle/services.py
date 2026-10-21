"""Rules for recording Bigs and Littles.

Every way of recording a pairing (initiation report, Edit My Info, the chapter pages and
the CSV upload) goes through :func:`set_big`, so the rules live in one place.
"""

import csv
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

from .models import BigLittle

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

CSV_HEADERS = ("badge_number_big", "badge_number_little")
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
    if has_badge_number(user):
        return f"{user.name} (#{user.badge_number})"
    return user.name


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
    big_badge: str
    little_badge: str
    big: User | None = None
    little: User | None = None
    outcome: str = ""
    message: str = ""


@dataclass
class ImportResult:
    rows: list = field(default_factory=list)
    error: str = ""

    def count(self, outcome):
        return sum(1 for row in self.rows if row.outcome == outcome)

    @property
    def summary(self):
        return (
            f"Processed {len(self.rows)} row(s): {self.count(CREATED)} recorded, "
            f"{self.count(CHANGED)} changed, {self.count(UNCHANGED)} unchanged, "
            f"{self.count(ERROR)} with errors."
        )


def _header_key(value):
    return re.sub(r"[\s-]+", "_", (value or "").strip().lower())


def _cell(cells, index):
    return cells[index].strip() if index < len(cells) else ""


def _read_rows(file_bytes):
    """The upload's data rows, or a message saying why the whole file was refused."""
    reader = csv.reader(io.StringIO(file_bytes.decode("utf-8-sig", errors="replace")))
    headers = [_header_key(cell) for cell in next(reader, [])]
    if not all(name in headers for name in CSV_HEADERS):
        return [], "The first row must contain the column names badge_number_big and badge_number_little."
    big_column, little_column = (headers.index(name) for name in CSV_HEADERS)
    rows = []
    for line, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) == MAX_UPLOAD_ROWS:
            return [], f"The file has more than {MAX_UPLOAD_ROWS:,} rows. Split it into smaller files."
        rows.append(ImportRow(line, _cell(cells, big_column), _cell(cells, little_column)))
    return rows, ""


def _parse_badge(value):
    return int(value) if value.isdigit() and len(value) <= MAX_BADGE_DIGITS else None


def _row_problem(row, chapter, by_badge, first_line_for_little):
    """Fill in the row's members, or return why the row cannot be saved."""
    found = {}
    for role, value in (("Big", row.big_badge), ("Little", row.little_badge)):
        number = _parse_badge(value)
        if number is None:
            return f"The {role} badge number is missing." if not value else f'"{value}" is not a badge number.'
        members = by_badge.get(number, [])
        if not members:
            return f"No member of {chapter} has badge number {number}."
        if len(members) > 1:
            return f"More than one member of {chapter} has badge number {number}. Fix the roster first."
        found[role] = members[0]
    row.big, row.little = found["Big"], found["Little"]
    if row.big.pk == row.little.pk:
        return "A member cannot be their own Big."
    if not is_initiated(row.little):
        return f"{row.little} is not initiated, so they cannot have a Big yet."
    if not is_initiated(row.big):
        return f"{row.big} is not initiated, so they cannot be a Big."
    first_line = first_line_for_little.setdefault(row.little.pk, row.line)
    if first_line != row.line:
        return f"{row.little} is already listed on line {first_line}."
    return ""


def import_big_little_csv(file_bytes, chapter, actor):
    """Record the pairings in an uploaded CSV of badge numbers (BLWI-7).

    Badge numbers only identify a member within a chapter, so every number is looked up
    in ``chapter``. All rows are checked before any is saved; good rows are then saved
    one at a time, so a row with a problem never blocks the rest of the file.
    """
    rows, error = _read_rows(file_bytes)
    result = ImportResult(rows=rows, error=error)
    if error:
        return result
    numbers = {_parse_badge(value) for row in rows for value in (row.big_badge, row.little_badge)}
    by_badge = {}
    for member in chapter.members.filter(badge_number__in=numbers - {None}):
        by_badge.setdefault(member.badge_number, []).append(member)
    first_line_for_little = {}
    for row in rows:
        row.message = _row_problem(row, chapter, by_badge, first_line_for_little)
        if row.message:
            row.outcome = ERROR
    for row in rows:
        if row.outcome == ERROR:
            continue
        try:
            saved = set_big(row.little, row.big, actor=actor, source=BigLittle.Source.UPLOAD)
        except BigLittleError as problem:
            row.outcome, row.message = ERROR, problem.messages[0]
            continue
        row.outcome = saved.outcome
        row.message = {
            CREATED: "Recorded",
            CHANGED: f"Changed (was {saved.previous_big})",
            UNCHANGED: "No change",
        }[saved.outcome]
    return result
