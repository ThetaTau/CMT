"""CSV parsing + idempotent ingestion for legacy / historical award imports (AWI-13).

:func:`ingest_award_csv` is the single entry point used by the admin upload view
and the ``import_awards`` management command. Each row is mapped to an award type
(admin-managed catalog -- must already exist), a cycle (created on demand), and a
backdated ``effective_date``; the recipient is matched via
:mod:`thetatauCMT.awards.import_matching`. Confident matches create the
``import`` grant immediately; everything else is routed to the manual
:class:`~thetatauCMT.awards.models.AwardImportMatchQueueItem` queue.

Idempotency
-----------
* :func:`import_grant` reuses an existing grant for the same
  ``(award_type, cycle, recipient)`` rather than duplicating it, so re-importing
  never double-creates grants.
* Queue rows are de-duplicated by a stable ``fingerprint`` of their raw identity:
  a second import of the same row reuses the pending item (refreshing its
  candidates), and rows whose fingerprint was already resolved are skipped.
"""

import datetime
import hashlib
import re
import uuid
from dataclasses import dataclass, field

from django.utils import timezone
from django.utils.dateparse import parse_date

from thetatauCMT.attendance.upload import COLUMN_ALIASES as _MEMBER_ALIASES
from thetatauCMT.attendance.upload import parse_rows

from .import_matching import match_recipient
from .models import AwardCycle, AwardGrant, AwardImportMatchQueueItem, AwardType
from .services import _recipient_kwargs, grant_award

# Member identity columns are shared with the attendance uploader; award-specific
# columns are layered on top. ("year" stays mapped to graduation_year — use
# "cycle" / "cycle_year" for the award period to avoid ambiguity.)
COLUMN_ALIASES = {
    **_MEMBER_ALIASES,
    "award": {"award", "award_type", "award_name", "awardtype"},
    "cycle": {"cycle", "cycle_name", "award_cycle", "cycle_year"},
    "region": {"region", "region_name", "recipient_region"},
    "recipient": {"recipient", "recipient_name", "winner"},
    "effective_date": {"effective_date", "award_date", "awarded_date", "awarded_on", "date_awarded"},
}

_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y")


@dataclass
class ImportResult:
    """Summary of an :func:`ingest_award_csv` run."""

    upload_id: str = ""
    total: int = 0
    imported: int = 0
    duplicates: int = 0
    queued: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    def as_dict(self):
        return {
            "upload_id": self.upload_id,
            "total": self.total,
            "imported": self.imported,
            "duplicates": self.duplicates,
            "queued": self.queued,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# --- Resolution helpers -------------------------------------------------------
def match_award_type(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    return AwardType.objects.filter(name__iexact=raw).first() or AwardType.objects.filter(name__icontains=raw).first()


def resolve_or_create_cycle(raw):
    """Map a raw cycle label to an existing cycle, or create it (AWI-13 allows
    creating missing cycles). A 4-digit value becomes a full calendar-year cycle."""
    raw = (raw or "").strip()
    if not raw:
        return None
    existing = AwardCycle.objects.filter(name__iexact=raw).first()
    if existing is not None:
        return existing
    if re.fullmatch(r"\d{4}", raw):
        year = int(raw)
        return AwardCycle.objects.create(
            name=raw,
            period_type=AwardCycle.PeriodType.YEAR,
            start_date=datetime.date(year, 1, 1),
            end_date=datetime.date(year, 12, 31),
        )
    return AwardCycle.objects.create(name=raw, period_type=AwardCycle.PeriodType.YEAR)


def parse_effective_date(raw, cycle=None):
    """Parse a backdated effective date; fall back to the cycle's end / start."""
    raw = (raw or "").strip()
    if raw:
        parsed = parse_date(raw)
        if parsed:
            return parsed
        for fmt in _DATE_FORMATS:
            try:
                return datetime.datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    if cycle is not None:
        return cycle.end_date or cycle.start_date
    return None


def import_grant(award_type, cycle, recipient, imported_by, *, effective_date=None, reason=""):
    """Create (or reuse) the backdated ``import`` grant for a recipient.

    Idempotent: returns any existing grant for the same award / cycle / recipient
    instead of creating a duplicate. Historical imports intentionally bypass the
    live eligibility / winner-limit checks. Returns ``(grant, created)``.
    """
    kwargs = _recipient_kwargs(recipient)
    existing = AwardGrant.objects.filter(award_type=award_type, cycle=cycle, **kwargs).first()
    if existing is not None:
        return existing, False
    grant = grant_award(
        award_type,
        cycle,
        recipient,
        imported_by,
        effective_date=effective_date,
        reason=reason,
        source=AwardGrant.Source.IMPORT,
    )
    return grant, True


# --- Parsing (CSV parsing is reused from the attendance uploader) --------------
def _recipient_identity(kind, row):
    if kind == "member":
        keys = ("member_id", "badge_number", "email", "name", "first_name", "last_name", "chapter", "graduation_year")
        return "|".join((row.get(key) or "").strip().lower() for key in keys)
    if kind == "chapter":
        return ((row.get("chapter") or row.get("recipient")) or "").strip().lower()
    if kind == "region":
        return ((row.get("region") or row.get("recipient")) or "").strip().lower()
    return ""


def award_row_fingerprint(award, kind, cycle, row):
    basis = "|".join([str(award.pk), kind, str(cycle.pk), _recipient_identity(kind, row)])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:64]


def _raw_recipient_label(kind, row):
    if kind == "member":
        return (
            row.get("name")
            or f"{row.get('first_name', '') or ''} {row.get('last_name', '') or ''}".strip()
            or row.get("email")
            or row.get("member_id")
            or row.get("badge_number")
            or ""
        )
    if kind == "chapter":
        return row.get("chapter") or row.get("recipient") or ""
    if kind == "region":
        return row.get("region") or row.get("recipient") or ""
    return ""


def _resolve_pending(fingerprint, recipient, grant, imported_by):
    """Mark any pending queue rows for this identity resolved (a later, better
    import auto-accepted what an earlier one had queued)."""
    Status = AwardImportMatchQueueItem.Status
    for item in AwardImportMatchQueueItem.objects.filter(fingerprint=fingerprint, status=Status.PENDING):
        item._set_resolved_recipient(recipient)
        item.resolved_grant = grant
        item.resolved_by = imported_by
        item.resolved_at = timezone.now()
        item.status = Status.RESOLVED
        item.save()


def ingest_award_csv(file_bytes, imported_by, *, threshold=None):
    """Parse and ingest a legacy-award CSV. Returns an :class:`ImportResult`."""
    Status = AwardImportMatchQueueItem.Status
    upload_id = uuid.uuid4()
    result = ImportResult(upload_id=str(upload_id))
    parsed = parse_rows(file_bytes, COLUMN_ALIASES)
    result.total = len(parsed)

    for row, original in parsed:
        raw_award = row.get("award")
        if not raw_award:
            result.skipped += 1
            result.errors.append("Row skipped: no award column.")
            continue
        award = match_award_type(raw_award)
        if award is None:
            result.skipped += 1
            result.errors.append(f"Award type not found: '{raw_award}'.")
            continue
        cycle = resolve_or_create_cycle(row.get("cycle"))
        if cycle is None:
            result.skipped += 1
            result.errors.append(f"No cycle given for award '{raw_award}'.")
            continue

        kind = award.recipient_kind
        effective_date = parse_effective_date(row.get("effective_date"), cycle)
        fingerprint = award_row_fingerprint(award, kind, cycle, row)

        # Already resolved on a prior import -> skip entirely (idempotent).
        if AwardImportMatchQueueItem.objects.filter(fingerprint=fingerprint, status=Status.RESOLVED).exists():
            result.skipped += 1
            continue

        match = match_recipient(kind, row)
        if match.auto_accept and match.recipient is not None:
            grant, created = import_grant(award, cycle, match.recipient, imported_by, effective_date=effective_date)
            _resolve_pending(fingerprint, match.recipient, grant, imported_by)
            if created:
                result.imported += 1
            else:
                result.duplicates += 1
            continue

        # Low confidence -> manual match queue, idempotently.
        item, created = AwardImportMatchQueueItem.objects.get_or_create(
            fingerprint=fingerprint,
            status=Status.PENDING,
            defaults=dict(
                upload_id=upload_id,
                recipient_kind=kind,
                raw_row=original,
                raw_award=raw_award[:255],
                raw_recipient=_raw_recipient_label(kind, row)[:255],
                raw_cycle=(row.get("cycle") or "")[:255],
                raw_effective_date=(row.get("effective_date") or "")[:32],
                award_type=award,
                cycle=cycle,
                effective_date=effective_date,
                candidate_matches=match.candidates,
                best_score=match.score,
                uploaded_by=imported_by,
            ),
        )
        if created:
            result.queued += 1
        else:
            item.candidate_matches = match.candidates
            item.best_score = match.score
            item.save(update_fields=["candidate_matches", "best_score", "modified"])
            result.skipped += 1

    return result
