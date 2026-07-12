"""Collect officer contact records for syncable scopes.

Two scopes are supported:

- Region — return the current Regent / Vice Regent / Treasurer / Scribe /
  Corresponding Secretary of every active chapter in the region.
- National — return every current national officer (COUNCIL + NATIONAL_OFFICER
  roles from :mod:`core.models`).

Both funnel through :func:`collect_contacts_for_scope`, which dispatches on a
free-form scope string:

- ``"region:<slug>"``          — a real region (or ``"region:candidate_chapter"``
  for the synthetic candidate-chapter grouping)
- ``"national"``               — the national officers

The dataclass carries everything downstream code — vCard writer, Google People
API, Microsoft Graph — needs to render a contact card, with no ``User`` model
imports at the call sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from core.models import COUNCIL, NATIONAL_OFFICER
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

# Full-role → short abbreviation used in the contact display name (per user spec:
# "X-R Franklin Ventura"). Ordering here is also the priority order used when a
# member holds more than one officer role — regent wins, then vice regent, etc.
OFFICER_POSITION_ABBR: dict[str, str] = {
    "regent": "R",
    "vice regent": "VR",
    "treasurer": "T",
    "scribe": "S",
    "corresponding secretary": "CS",
}

# Frozen list of the officer roles we sync. Do NOT reuse the mutable
# ``CHAPTER_OFFICER`` set from ``core.models`` because we care about the
# regent-first priority order when a member holds multiple roles.
SYNCED_OFFICER_ROLES: tuple[str, ...] = tuple(OFFICER_POSITION_ABBR)

# Every COUNCIL and NATIONAL_OFFICER role is sync-eligible. Sorted for stable
# ordering in the vCard output and to make abbreviation collisions deterministic.
NATIONAL_ROLES: tuple[str, ...] = tuple(sorted(COUNCIL | NATIONAL_OFFICER))

# Human display name for the "chapter" column in national officer contacts.
NATIONAL_CHAPTER_LABEL = "National Office"
NATIONAL_CHAPTER_ABBR = "NAT"
NATIONAL_SCOPE = "national"

_WORD_RE = re.compile(r"[A-Za-z]+")
# Filler words dropped from a role name before we take initials. Keeps
# "Diversity, Equity, and Inclusion Chair" → DEIC rather than DEAIC.
_STOP_WORDS = frozenset({"and", "of", "the", "for", "to", "a", "an", "on"})

# Manual overrides where the auto-generated initials don't match the natoff
# preferred abbreviation. Per the natoff spec, ``grand inner guard`` is "GIG"
# (last letter of "Guard") — the automatic first-letter-of-each-word rule would
# produce "GIG" which collides visually with "GOG" from ``grand outer guard``.
_ROLE_ABBR_OVERRIDES: dict[str, str] = {
    "grand inner guard": "GIG",
    "grand outer guard": "GOG",
}


def national_role_abbr(role: str) -> str:
    """Return the initials of ``role`` for use in the contact display name.

    Rules per the natoff spec:
    - "regional director" → "RD"
    - "national officer"  → "NO"
    - "grand inner guard" → "GIG"   (via :data:`_ROLE_ABBR_OVERRIDES`)

    We take the first letter of every significant word (a-z only, so a hyphen
    doesn't split a single word into two initials; stop words like "and", "of",
    "the" are dropped) and uppercase the result. Specific problem cases are
    hand-overridden via :data:`_ROLE_ABBR_OVERRIDES`.
    """
    key = (role or "").strip().lower()
    if key in _ROLE_ABBR_OVERRIDES:
        return _ROLE_ABBR_OVERRIDES[key]
    words = _WORD_RE.findall(role or "")
    initials = "".join(word[0] for word in words if word.lower() not in _STOP_WORDS).upper()
    return initials or "NAT"


# Precomputed abbreviations for every national role — used by templates + tests.
NATIONAL_ROLE_ABBR: dict[str, str] = {role: national_role_abbr(role) for role in NATIONAL_ROLES}


@dataclass
class OfficerContact:
    """A single officer contact card, provider-agnostic."""

    chapter_abbr: str
    chapter_name: str
    role: str  # full role name, e.g. "regent"
    role_abbr: str  # short abbr, e.g. "R"
    first_name: str
    last_name: str
    preferred_name: str = ""
    middle_name: str = ""
    suffix: str = ""
    email: str = ""
    email_school: str = ""
    phone: str = ""
    user_pk: int | None = None
    extra_roles: list[str] = field(default_factory=list)
    # Generic chapter mailbox(es) tied to this officer's role(s), e.g. the
    # chapter's ``email_regent`` address for the regent. Empty for national
    # officers (they have no chapter-scoped generic mailbox).
    generic_emails: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Return ``"{chapter}-{pos} {First} {Last}"`` per the natoff spec."""
        given = (self.preferred_name or self.first_name).strip()
        family = self.last_name.strip()
        # Strip whitespace from every segment so we never emit "X-R  Frank Doe".
        given_family = " ".join(part for part in (given, family) if part)
        prefix = f"{self.chapter_abbr}-{self.role_abbr}".strip("-") or "TT"
        if not given_family:
            return prefix
        return f"{prefix} {given_family}"

    @property
    def emails(self) -> list[str]:
        """Return primary email + school email + generic role mailbox(es), deduped.

        Preserves the member's personal address and the ``.edu`` on file, then
        appends any chapter generic mailbox(es) associated with the officer's
        role(s) (e.g. the chapter ``email_regent`` for the regent) so the sync
        pushes those extra addresses onto the same contact card.
        """
        seen: set[str] = set()
        out: list[str] = []
        for value in (self.email, self.email_school, *self.generic_emails):
            value = (value or "").strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                out.append(value)
        return out


# --------------------------------------------------------------------- helpers
def _pick_primary_role(
    current_roles: Iterable[str] | None,
    priority_list: Iterable[str],
) -> tuple[str | None, list[str]]:
    """Return the highest-priority officer role and any other synced roles held."""
    if not current_roles:
        return None, []
    priority = tuple(priority_list)
    priority_set = set(priority)
    role_set = {r for r in current_roles if r in priority_set}
    if not role_set:
        return None, []
    for candidate in priority:
        if candidate in role_set:
            others = [r for r in priority if r in role_set and r != candidate]
            return candidate, others
    return None, []


def _chapter_abbr(chapter: Chapter) -> str:
    """Return the short display prefix for a chapter (Greek letter, else slug).

    Always returns an upper-case value so contact names render as ``X-R …``
    even when ``chapter.greek`` was persisted lower-case.
    """
    abbr = (chapter.greek or "").strip()
    if abbr:
        return abbr.upper()
    # Fall back to first letters of the chapter name so at least SOMETHING renders.
    name = (chapter.name or "").strip() or (chapter.slug or "").strip()
    fallback = name.split(" ")[0][:6] if name else "TT"
    return fallback.upper()


def _officers_for_chapter(chapter: Chapter) -> list[OfficerContact]:
    officers = chapter.get_current_officers().filter(
        current_roles__overlap=list(SYNCED_OFFICER_ROLES),
    )
    contacts: list[OfficerContact] = []
    chapter_abbr = _chapter_abbr(chapter)
    for user in officers.distinct():
        primary, extras = _pick_primary_role(user.current_roles, SYNCED_OFFICER_ROLES)
        if not primary:
            continue
        # Collect the chapter's generic mailbox(es) for every synced role this
        # officer holds (primary + extras) so the sync ties them to this card.
        generic_emails: list[str] = []
        for role in (primary, *extras):
            generic = chapter.generic_email_for_role(role)
            if generic and generic not in generic_emails:
                generic_emails.append(generic)
        contacts.append(
            OfficerContact(
                chapter_abbr=chapter_abbr,
                chapter_name=chapter.name,
                role=primary,
                role_abbr=OFFICER_POSITION_ABBR[primary],
                first_name=(user.first_name or "").strip(),
                last_name=(user.last_name or "").strip(),
                preferred_name=(user.preferred_name or "").strip(),
                middle_name=(user.middle_name or "").strip(),
                suffix=(user.suffix or "").strip(),
                email=(user.email or "").strip(),
                email_school=(user.email_school or "").strip(),
                phone=(user.phone_number or "").strip(),
                user_pk=user.pk,
                extra_roles=extras,
                generic_emails=generic_emails,
            )
        )
    return contacts


def _resolve_region_scope(region_slug: str) -> tuple[list[Chapter], str]:
    """Return ``(chapters, display_name)`` for a region slug.

    ``candidate_chapter`` is a synthetic scope Region uses to represent the
    non-region grouping of candidate chapters — handle it explicitly.
    """
    active = Chapter.objects.exclude(active=False)
    if region_slug == "candidate_chapter":
        return list(active.filter(candidate_chapter=True)), "Candidate Chapters"
    region = Region.objects.filter(slug=region_slug).first()
    if region is None:
        return [], region_slug
    return list(active.filter(region=region)), region.name


def collect_region_officer_contacts(
    region_slug: str,
    roles: Iterable[str] | None = None,
) -> tuple[list[OfficerContact], str]:
    """Return officer contacts for a region (plus a display name for the region).

    ``roles`` optionally narrows the set of officer roles included; defaults to
    all five in :data:`SYNCED_OFFICER_ROLES`.
    """
    if roles is None:
        role_filter = set(SYNCED_OFFICER_ROLES)
    else:
        role_filter = {r for r in roles if r in OFFICER_POSITION_ABBR}
        if not role_filter:
            role_filter = set(SYNCED_OFFICER_ROLES)
    chapters, region_name = _resolve_region_scope(region_slug)
    out: list[OfficerContact] = []
    for chapter in chapters:
        for contact in _officers_for_chapter(chapter):
            if contact.role in role_filter:
                out.append(contact)
    # Sort by chapter abbr, then role priority (regent first), then name.
    role_priority = {r: i for i, r in enumerate(SYNCED_OFFICER_ROLES)}
    out.sort(key=lambda c: (c.chapter_abbr.lower(), role_priority.get(c.role, 99), c.last_name.lower()))
    return out, region_name


# --------------------------------------------------------------------- national
def collect_national_officer_contacts(
    roles: Iterable[str] | None = None,
) -> tuple[list[OfficerContact], str]:
    """Return national-officer contacts (COUNCIL + NATIONAL_OFFICER).

    All contacts share ``chapter_abbr="NAT"`` and ``chapter_name="National
    Office"``. Role abbreviation is the initials of the role name (see
    :func:`national_role_abbr`).
    """
    # Imported inside the function so the module load order doesn't trip when
    # unit-testing helper logic without the User app fully wired.
    from thetatauCMT.users.models import User

    if roles is None:
        role_filter = set(NATIONAL_ROLES)
    else:
        role_filter = {r for r in roles if r in NATIONAL_ROLE_ABBR}
        if not role_filter:
            role_filter = set(NATIONAL_ROLES)
    officers = (
        User.objects.filter(current_roles__overlap=list(role_filter)).distinct().order_by("last_name", "first_name")
    )
    out: list[OfficerContact] = []
    for user in officers:
        primary, extras = _pick_primary_role(user.current_roles, NATIONAL_ROLES)
        if not primary or primary not in role_filter:
            continue
        out.append(
            OfficerContact(
                chapter_abbr=NATIONAL_CHAPTER_ABBR,
                chapter_name=NATIONAL_CHAPTER_LABEL,
                role=primary,
                role_abbr=NATIONAL_ROLE_ABBR[primary],
                first_name=(user.first_name or "").strip(),
                last_name=(user.last_name or "").strip(),
                preferred_name=(user.preferred_name or "").strip(),
                middle_name=(user.middle_name or "").strip(),
                suffix=(user.suffix or "").strip(),
                email=(user.email or "").strip(),
                email_school=(user.email_school or "").strip(),
                phone=(user.phone_number or "").strip(),
                user_pk=user.pk,
                extra_roles=extras,
            )
        )
    # Sort by role priority (per NATIONAL_ROLES ordering), then last name.
    role_priority = {r: i for i, r in enumerate(NATIONAL_ROLES)}
    out.sort(key=lambda c: (role_priority.get(c.role, 99), c.last_name.lower()))
    return out, "National Officers"


# --------------------------------------------------------------------- dispatch
def collect_contacts_for_scope(
    scope: str,
    roles: Iterable[str] | None = None,
) -> tuple[list[OfficerContact], str]:
    """Return contacts for a scope string used by URL / POST endpoints.

    Recognised values:

    - ``"national"`` → :func:`collect_national_officer_contacts`
    - ``"region:<slug>"`` → :func:`collect_region_officer_contacts`

    A bare region slug (backwards-compatibility with earlier URLs that only
    supported region sync) is also accepted.
    """
    if scope == NATIONAL_SCOPE:
        return collect_national_officer_contacts(roles=roles)
    if scope.startswith("region:"):
        return collect_region_officer_contacts(scope.split(":", 1)[1], roles=roles)
    # Legacy path — treat any other value as a region slug.
    return collect_region_officer_contacts(scope, roles=roles)


def scope_display_name(scope: str) -> str:
    """Human-friendly label for a scope, without hitting the DB when possible."""
    if scope == NATIONAL_SCOPE:
        return "National Officers"
    slug = scope.split(":", 1)[1] if scope.startswith("region:") else scope
    if slug == "candidate_chapter":
        return "Candidate Chapters"
    region = Region.objects.filter(slug=slug).first()
    return region.name if region else slug


def normalize_scope(raw: str) -> str:
    """Return a canonical scope string from a raw URL/POST value.

    Accepts either the fully-qualified ``"region:<slug>"`` / ``"national"``
    form or a bare region slug (legacy). Empty input returns the legacy form.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw == NATIONAL_SCOPE or raw.startswith("region:"):
        return raw
    return f"region:{raw}"
