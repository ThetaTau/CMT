"""Recipient matching for legacy award imports (AWI-13).

Members reuse the attendance national-upload matcher (exact id / email, then
fuzzy name raised by chapter + graduation-year agreement). Chapters and regions
are matched by name or slug / code: an exact match auto-accepts; anything else
is routed to the manual queue with ranked candidates.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

from django.db.models import Q

from thetatauCMT.attendance.matching import match_row, normalize

CANDIDATE_LIMIT = 10


@dataclass
class RecipientMatch:
    """Outcome of matching one import row to a recipient."""

    recipient: Optional[object] = None
    kind: str = "none"
    score: float = 0.0
    auto_accept: bool = False
    candidates: List[dict] = field(default_factory=list)


def _member_candidate(candidate):
    """Normalise an attendance candidate dict to the uniform import shape."""
    return {
        "id": candidate.get("user_id"),
        "name": candidate.get("name", ""),
        "kind": "member",
        "score": candidate.get("score", 0.0),
        "reasons": candidate.get("reasons", []),
        "chapter": candidate.get("chapter", ""),
        "badge_number": candidate.get("badge_number"),
    }


def match_member(row, threshold=None):
    result = match_row(row, threshold=threshold)
    return RecipientMatch(
        recipient=result.user,
        kind="member",
        score=result.score,
        auto_accept=result.auto_accept and result.user is not None,
        candidates=[_member_candidate(c) for c in result.candidates],
    )


def _entity_candidate(obj, kind, score, reasons):
    return {"id": obj.pk, "name": str(obj), "kind": kind, "score": round(score, 4), "reasons": reasons}


def _match_named_entity(raw, kind, model):
    raw = (raw or "").strip()
    if not raw:
        return RecipientMatch(kind=kind)
    exact = model.objects.filter(Q(name__iexact=raw) | Q(slug__iexact=raw)).first()
    if exact is not None:
        return RecipientMatch(
            recipient=exact,
            kind=kind,
            score=1.0,
            auto_accept=True,
            candidates=[_entity_candidate(exact, kind, 1.0, ["exact name / code match"])],
        )
    pool = list(model.objects.filter(Q(name__icontains=raw) | Q(slug__icontains=raw))[:CANDIDATE_LIMIT])
    norm = normalize(raw)
    scored = sorted(
        ((SequenceMatcher(None, norm, normalize(obj.name)).ratio(), obj) for obj in pool),
        key=lambda pair: (pair[0], pair[1].pk),
        reverse=True,
    )
    candidates = [_entity_candidate(obj, kind, score, [f"name similarity {score:.0%}"]) for score, obj in scored]
    return RecipientMatch(
        recipient=None,
        kind=kind,
        score=scored[0][0] if scored else 0.0,
        auto_accept=False,
        candidates=candidates,
    )


def match_chapter(raw):
    from thetatauCMT.chapters.models import Chapter

    return _match_named_entity(raw, "chapter", Chapter)


def match_region(raw):
    from thetatauCMT.regions.models import Region

    return _match_named_entity(raw, "region", Region)


def match_recipient(kind, row):
    """Dispatch to the member / chapter / region matcher for ``kind``."""
    if kind == "member":
        return match_member(row)
    if kind == "chapter":
        return match_chapter(row.get("chapter") or row.get("recipient"))
    if kind == "region":
        return match_region(row.get("region") or row.get("recipient"))
    return RecipientMatch(kind=kind)
