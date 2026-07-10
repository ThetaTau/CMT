"""CSV parsing and idempotent ingestion for national-event attendance uploads (WI-7).

:func:`ingest_attendance_csv` is the single entry point used by the upload view.
It parses the file, runs each row through :func:`attendance.matching.match_row`,
auto-records confident matches, and routes everything else to the manual
:class:`~thetatauCMT.attendance.models.MatchQueueItem` queue.

Idempotency
-----------
* Auto-matched rows call :func:`attendance.services.record_attendance`, which
  upserts on the unique ``(event, user)`` constraint — re-uploading never
  double-creates attendance.
* Unresolved rows are de-duplicated by a stable ``fingerprint`` of their raw
  identity fields: a second upload of the same row reuses the existing pending
  queue item (refreshing its candidates) instead of adding a duplicate, and rows
  whose fingerprint was already resolved are skipped entirely.
"""

import csv
import hashlib
import io
import re
import uuid
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from .matching import match_row
from .models import AttendanceRecord, MatchQueueItem
from .services import record_attendance

# Canonical row key -> set of accepted header spellings (compared after the
# header itself is lower-cased and non-alphanumerics collapsed to "_").
COLUMN_ALIASES = {
    "member_id": {"member_id", "memberid", "id", "user_id", "userid", "pk", "cmt_id"},
    "badge_number": {"badge", "badge_number", "badgenumber", "roll", "roll_number", "badge_no"},
    "email": {"email", "e_mail", "email_address", "emailaddress", "mail", "personal_email"},
    "name": {"name", "full_name", "fullname", "member_name", "membername"},
    "first_name": {"first_name", "firstname", "first", "given_name", "givenname"},
    "last_name": {"last_name", "lastname", "last", "surname", "family_name", "familyname"},
    "chapter": {"chapter", "chapter_name", "chaptername", "chapter_designation"},
    "graduation_year": {
        "graduation_year",
        "grad_year",
        "gradyear",
        "graduation",
        "class_year",
        "classyear",
        "year",
    },
}


@dataclass
class UploadResult:
    """Summary of an :func:`ingest_attendance_csv` run."""

    upload_id: str = ""
    total: int = 0
    auto_matched: int = 0
    updated: int = 0
    queued: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    @property
    def resolved(self):
        return self.auto_matched + self.updated

    def as_dict(self):
        return {
            "upload_id": self.upload_id,
            "total": self.total,
            "auto_matched": self.auto_matched,
            "updated": self.updated,
            "queued": self.queued,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _canonical_header(raw_header):
    key = re.sub(r"[^a-z0-9]+", "_", (raw_header or "").strip().lower()).strip("_")
    for canonical, aliases in COLUMN_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    return None


def parse_rows(file_bytes):
    """Parse CSV ``bytes`` into ``(row, original)`` pairs.

    ``row`` maps canonical keys to trimmed values; ``original`` preserves the raw
    header/value pairs for audit. Blank lines are ignored.
    """
    if isinstance(file_bytes, str):
        text = file_bytes
    else:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    all_rows = [r for r in reader]
    if not all_rows:
        return []
    header = all_rows[0]
    mapping = {i: _canonical_header(h) for i, h in enumerate(header)}
    parsed = []
    for raw in all_rows[1:]:
        if not any((cell or "").strip() for cell in raw):
            continue
        row = {}
        original = {}
        for i, value in enumerate(raw):
            header_name = header[i] if i < len(header) else f"col{i}"
            original[header_name] = value
            canonical = mapping.get(i)
            if canonical:
                row[canonical] = (value or "").strip()
        parsed.append((row, original))
    return parsed


def row_fingerprint(row):
    """Stable hash of a row's raw identity fields (drives idempotent re-uploads)."""
    basis = "|".join(
        (row.get(key) or "").strip().lower()
        for key in (
            "member_id",
            "badge_number",
            "email",
            "name",
            "first_name",
            "last_name",
            "chapter",
            "graduation_year",
        )
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:64]


def _has_identity(row):
    """True if the row carries anything we can match on."""
    if any((row.get(k) or "").strip() for k in ("member_id", "badge_number", "email", "name")):
        return True
    return bool((row.get("first_name") or "").strip() and (row.get("last_name") or "").strip())


def _queue_defaults(row, original, match, upload_id, uploaded_by, default_status):
    return {
        "upload_id": upload_id,
        "raw_member_id": (row.get("member_id") or "")[:100],
        "raw_badge_number": (row.get("badge_number") or "")[:100],
        "raw_email": (row.get("email") or "")[:255],
        "raw_name": (row.get("name") or "")[:255],
        "raw_first_name": (row.get("first_name") or "")[:255],
        "raw_last_name": (row.get("last_name") or "")[:255],
        "raw_chapter": (row.get("chapter") or "")[:255],
        "raw_graduation_year": (row.get("graduation_year") or "")[:16],
        "raw_row": original,
        "candidates": match.candidates,
        "best_score": match.score,
        "target_status": default_status,
        "uploaded_by": uploaded_by,
    }


def ingest_attendance_csv(event, file_bytes, uploaded_by, default_status=None, threshold=None):
    """Parse and ingest an attendance CSV for ``event``. Returns an :class:`UploadResult`."""
    default_status = default_status or AttendanceRecord.STATUS.ATTENDED
    upload_id = uuid.uuid4()
    result = UploadResult(upload_id=str(upload_id))
    parsed = parse_rows(file_bytes)
    result.total = len(parsed)

    for row, original in parsed:
        if not _has_identity(row):
            result.skipped += 1
            result.errors.append("Row skipped: no member id, email, or name.")
            continue

        fingerprint = row_fingerprint(row)
        match = match_row(row, threshold=threshold)

        if match.auto_accept and match.user is not None:
            already = AttendanceRecord.objects.filter(event=event, user=match.user).exists()
            with transaction.atomic():
                record_attendance(event, match.user, default_status, uploaded_by)
                # If this identity was previously queued, it is now resolved.
                MatchQueueItem.objects.filter(
                    event=event,
                    fingerprint=fingerprint,
                    status=MatchQueueItem.Status.PENDING,
                ).update(
                    status=MatchQueueItem.Status.RESOLVED,
                    resolved_user=match.user,
                    resolved_by=uploaded_by,
                    resolved_at=timezone.now(),
                )
            if already:
                result.updated += 1
            else:
                result.auto_matched += 1
            continue

        # Needs manual review — route to the queue, idempotently.
        if MatchQueueItem.objects.filter(
            event=event,
            fingerprint=fingerprint,
            status=MatchQueueItem.Status.RESOLVED,
        ).exists():
            result.skipped += 1
            continue

        item, created = MatchQueueItem.objects.get_or_create(
            event=event,
            fingerprint=fingerprint,
            status=MatchQueueItem.Status.PENDING,
            defaults=_queue_defaults(row, original, match, upload_id, uploaded_by, default_status),
        )
        if created:
            result.queued += 1
        else:
            # Refresh candidates for an existing pending row (no duplicate).
            item.candidates = match.candidates
            item.best_score = match.score
            item.save(update_fields=["candidates", "best_score", "modified"])
            result.skipped += 1

    return result
