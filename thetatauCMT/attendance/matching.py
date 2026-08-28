"""Member-matching pipeline for national-event attendance uploads (WI-7).

A national event spans chapters, so uploaded rows often carry only an email or a
name — no member id. :func:`match_row` takes one normalised upload row and finds
the best-matching :class:`~thetatauCMT.users.models.User` together with a
confidence score in ``[0, 1]``.

Match priority
--------------
1. **id**          exact lookup by member id (pk) or badge number  -> score 1.00
2. **exact email** case-insensitive match on ``email`` /
                   ``email_school``                                -> score 0.95
3. **name**        fuzzy full-name similarity, *raised* by
                   graduation-year, chapter and email agreement    -> score 0..1

Name-tier scoring
-----------------
``confidence = name_similarity * NAME_WEIGHT
             + (GRAD_YEAR_WEIGHT  if graduation year agrees)
             + (CHAPTER_WEIGHT    if home chapter agrees)
             + (EMAIL_WEIGHT      if the row's email is corroborated by watson)``

The weights sum to ``1.0`` (``0.65 + 0.10 + 0.10 + 0.15``) so a *perfect* name
match that also agrees on graduation year and chapter scores ``0.85``, and a
name match corroborated on every filled-in field scores ``1.0``. Because
``NAME_WEIGHT`` alone (``0.65``) is > the ``0.60`` auto-accept threshold, an
exact and unambiguous full-name match still auto-accepts on its own, while a
merely *good* name match (e.g. similarity ``0.80`` → ``0.52``) stays below
threshold unless other filled-in fields raise it.

``name_similarity`` is the :func:`difflib.SequenceMatcher` ratio over the
normalised (lower-cased, punctuation-stripped, whitespace-collapsed) names,
taking the best of the stored full name vs. ``"first last"`` and of the direct
vs. token-sorted comparison (so ``"Doe, Jane"`` still matches ``"Jane Doe"``).

Watson-backed corroboration
----------------------------
A row rarely fills in every field, and the previous implementation only ever
raised a name match using ``graduation_year``/``chapter`` — an uploaded email
or a nickname/maiden-name variant that didn't exactly match tier 2 was simply
discarded, so confidence collapsed to a near-pure first/last name comparison.
The name-tier candidate pool is now built with :mod:`watson`'s full-text index
(:func:`_name_candidate_pool`), which covers every identity field registered
on ``User`` — ``name``, ``first_name``, ``last_name``, ``nickname``,
``preferred_name``, ``maiden_name``, ``username``, ``email``, ``email_school``
and ``chapter__name`` — so a row matches on *whichever* of those fields it
happens to supply, not just the literal name columns. Separately, whatever
email/chapter text the row supplies is checked with watson against the pool
(:func:`_watson_hits`) and, when corroborated, raises the score via
``EMAIL_WEIGHT``/``CHAPTER_WEIGHT`` even if the email didn't exactly match
anyone at tier 2 or the chapter text doesn't resolve to a real ``Chapter``.

Auto-accept
-----------
A row auto-accepts only when the top candidate's score is **strictly greater
than** ``settings.ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD`` (default ``0.60``)
**and** the match is unambiguous — i.e. no runner-up candidate sits within
``AMBIGUITY_MARGIN`` of the top score. Everything else is routed to the manual
match queue (:class:`~thetatauCMT.attendance.models.MatchQueueItem`).
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

from django.conf import settings
from django.db.models import Q
from watson import search as watson

# --- Tunable scoring constants -------------------------------------------------
NAME_WEIGHT = 0.65
GRAD_YEAR_WEIGHT = 0.10
CHAPTER_WEIGHT = 0.10
EMAIL_WEIGHT = 0.15
ID_MATCH_SCORE = 1.0
EMAIL_MATCH_SCORE = 0.95
AMBIGUITY_MARGIN = 0.05
DEFAULT_THRESHOLD = 0.60
# Cap the candidate pool / stored candidate list so a broad name never scans the
# entire ~30k-member table or bloats the queue item.
CANDIDATE_POOL_LIMIT = 200
MAX_STORED_CANDIDATES = 5


def get_threshold():
    """Auto-accept threshold (configurable, defaults to 0.60)."""
    return getattr(settings, "ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD", DEFAULT_THRESHOLD)


@dataclass
class MatchResult:
    """Outcome of matching a single upload row."""

    user: Optional[object] = None
    score: float = 0.0
    tier: str = "none"  # "id" | "email" | "name" | "none"
    auto_accept: bool = False
    candidates: List[dict] = field(default_factory=list)


def normalize(value):
    """Lower-case, strip punctuation, and collapse whitespace."""
    if not value:
        return ""
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ratio(a, b):
    """Best of direct vs. token-sorted SequenceMatcher ratio."""
    if not a or not b:
        return 0.0
    direct = SequenceMatcher(None, a, b).ratio()
    a_sorted = " ".join(sorted(a.split()))
    b_sorted = " ".join(sorted(b.split()))
    sorted_ratio = SequenceMatcher(None, a_sorted, b_sorted).ratio()
    return max(direct, sorted_ratio)


def _row_name(row):
    name = (row.get("name") or "").strip()
    if name:
        return name
    return f"{row.get('first_name', '') or ''} {row.get('last_name', '') or ''}".strip()


def name_similarity(row_name, user):
    """Best normalised similarity of ``row_name`` against a user's names.

    Checks nickname/preferred_name/maiden_name too, so an uploaded row that
    was found via one of those alternate fields (see :func:`_name_candidate_pool`)
    scores on the field that actually matched, not just the formal legal name.
    """
    a = normalize(row_name)
    if not a:
        return 0.0
    candidates = [
        user.name,
        f"{user.first_name or ''} {user.last_name or ''}",
        user.nickname,
        user.preferred_name,
        user.maiden_name,
    ]
    return max((_ratio(a, normalize(c)) for c in candidates if c), default=0.0)


def _resolve_grad_year(raw):
    if raw in (None, ""):
        return None
    match = re.search(r"\d{4}", str(raw))
    return int(match.group()) if match else None


def _resolve_chapter(raw):
    """Best-effort chapter lookup by name or slug (returns a Chapter or None)."""
    if not raw:
        return None
    from thetatauCMT.chapters.models import Chapter

    raw = str(raw).strip()
    return (
        Chapter.objects.filter(Q(name__iexact=raw) | Q(slug__iexact=raw)).first()
        or Chapter.objects.filter(Q(name__icontains=raw) | Q(slug__icontains=raw)).first()
    )


def score_name_candidate(row, user, chapter=None, email_hits=None, chapter_hits=None):
    """Confidence (0..1) and human-readable reasons for a name-tier candidate.

    ``email_hits``/``chapter_hits`` are optional sets of candidate pks (from
    :func:`_watson_hits`) confirming that the row's email/chapter text is
    corroborated *somewhere* in that candidate's watson-indexed fields, even
    when it isn't an exact tier-2 email match or a resolvable ``Chapter``.
    """
    sim = name_similarity(_row_name(row), user)
    score = sim * NAME_WEIGHT
    reasons = [f"name similarity {sim:.0%}"]
    grad = _resolve_grad_year(row.get("graduation_year"))
    if grad and user.graduation_year and grad == user.graduation_year:
        score += GRAD_YEAR_WEIGHT
        reasons.append(f"graduation year {grad} matches")
    chapter_agrees = chapter is not None and user.chapter_id == chapter.pk
    if not chapter_agrees and chapter_hits and user.pk in chapter_hits:
        chapter_agrees = True
    if chapter_agrees:
        score += CHAPTER_WEIGHT
        reasons.append(f"chapter {chapter.name if chapter is not None else row.get('chapter')} matches")
    if email_hits and user.pk in email_hits:
        score += EMAIL_WEIGHT
        reasons.append("email matches")
    return round(min(score, 1.0), 4), reasons


def _candidate_dict(user, score, reasons):
    return {
        "user_id": user.pk,
        "name": user.name,
        "badge_number": user.badge_number,
        "chapter": user.chapter.name if user.chapter_id else "",
        "graduation_year": user.graduation_year,
        "score": round(score, 4),
        "reasons": reasons,
    }


def _name_candidate_pool(row, chapter):
    """A bounded queryset of plausible name-match candidates.

    Discovery goes through watson's full-text index first, so a row's name
    matches against every identity field registered on ``User`` (name,
    first/last name, nickname, preferred_name, maiden_name, username) instead
    of only ``name``/``first_name``/``last_name``. Falls back to a plain
    icontains scan of those same fields if watson turns up nothing (e.g. no
    index entries yet).
    """
    from thetatauCMT.users.models import User

    qs = User.objects.select_related("chapter")
    if chapter is not None:
        qs = qs.filter(chapter=chapter)
    tokens = [t for t in normalize(_row_name(row)).split() if len(t) >= 2]
    if not tokens:
        return User.objects.none()
    search_text = " ".join(tokens)
    try:
        pool = watson.filter(qs, search_text)[:CANDIDATE_POOL_LIMIT]
        if pool:
            return pool
    except Exception:
        pass
    query = Q()
    for token in tokens:
        query |= (
            Q(name__icontains=token)
            | Q(first_name__icontains=token)
            | Q(last_name__icontains=token)
            | Q(nickname__icontains=token)
            | Q(preferred_name__icontains=token)
            | Q(maiden_name__icontains=token)
        )
    return qs.filter(query)[:CANDIDATE_POOL_LIMIT]


def _watson_hits(pool_qs, term):
    """Pks within ``pool_qs`` that watson's index confirms for ``term``.

    Lets a row's email or chapter text corroborate a name match via *any*
    watson-registered field (e.g. ``email_school``, ``username``,
    ``chapter__name``) instead of requiring an exact tier-2 email match or a
    resolvable ``Chapter``.
    """
    term = (term or "").strip()
    if not term:
        return set()
    try:
        return set(watson.filter(pool_qs, term).values_list("pk", flat=True))
    except Exception:
        return set()


def _lookup_by_id(row):
    """Tier 1 — exact member id (pk) or badge number lookup."""
    from thetatauCMT.users.models import User

    raw_id = (row.get("member_id") or "").strip()
    if raw_id.isdigit():
        user = User.objects.filter(pk=int(raw_id)).first()
        if user:
            return user, "member id"
    raw_badge = (row.get("badge_number") or "").strip()
    if raw_badge.isdigit():
        user = User.objects.filter(badge_number=int(raw_badge)).first()
        if user:
            return user, "badge number"
    return None, ""


def _lookup_by_email(row):
    """Tier 2 — exact (case-insensitive) email match."""
    from thetatauCMT.users.models import User

    email = (row.get("email") or "").strip()
    if not email:
        return []
    return list(User.objects.filter(Q(email__iexact=email) | Q(email_school__iexact=email)).select_related("chapter"))


def match_row(row, threshold=None):
    """Match a single normalised upload ``row`` to a member.

    ``row`` keys (all optional): ``member_id``, ``badge_number``, ``email``,
    ``name``, ``first_name``, ``last_name``, ``chapter``, ``graduation_year``.
    """
    threshold = get_threshold() if threshold is None else threshold

    # Tier 1: exact id / badge -> unambiguous, always auto-accept.
    user, id_reason = _lookup_by_id(row)
    if user is not None:
        return MatchResult(
            user=user,
            score=ID_MATCH_SCORE,
            tier="id",
            auto_accept=True,
            candidates=[_candidate_dict(user, ID_MATCH_SCORE, [f"exact {id_reason} match"])],
        )

    # Tier 2: exact email.
    email_matches = _lookup_by_email(row)
    if email_matches:
        candidates = [_candidate_dict(u, EMAIL_MATCH_SCORE, ["exact email match"]) for u in email_matches]
        # A single email owner auto-accepts; multiple owners are ambiguous.
        auto = len(email_matches) == 1 and EMAIL_MATCH_SCORE > threshold
        return MatchResult(
            user=email_matches[0] if auto else None,
            score=EMAIL_MATCH_SCORE,
            tier="email",
            auto_accept=auto,
            candidates=candidates[:MAX_STORED_CANDIDATES],
        )

    # Tier 3: fuzzy name, raised by graduation year, chapter and email agreement.
    from thetatauCMT.users.models import User

    chapter = _resolve_chapter(row.get("chapter"))
    pool = list(_name_candidate_pool(row, chapter))
    if not pool:
        return MatchResult(tier="none")
    pool_qs = User.objects.filter(pk__in=[candidate.pk for candidate in pool])
    email_hits = _watson_hits(pool_qs, row.get("email"))
    chapter_hits = _watson_hits(pool_qs, row.get("chapter"))
    scored = []
    for candidate in pool:
        score, reasons = score_name_candidate(row, candidate, chapter, email_hits, chapter_hits)
        scored.append((score, candidate, reasons))
    scored.sort(key=lambda t: (t[0], t[1].pk), reverse=True)
    candidates = [_candidate_dict(u, s, r) for s, u, r in scored[:MAX_STORED_CANDIDATES]]
    top_score, top_user, _ = scored[0]
    ambiguous = len(scored) > 1 and (scored[0][0] - scored[1][0]) < AMBIGUITY_MARGIN
    auto = top_score > threshold and not ambiguous
    return MatchResult(
        user=top_user if auto else None,
        score=top_score,
        tier="name",
        auto_accept=auto,
        candidates=candidates,
    )
