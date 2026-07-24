"""CSV / Excel exporters for award grants (AWI-12).

A single row builder (:func:`grant_row`) feeds both the CSV and the XLSX writers
so the two formats always share identical columns. Both return a downloadable
``HttpResponse`` with a timestamped filename.
"""

import csv
import datetime

from django.http import HttpResponse

from core.csv_utils import escape_csv_row

from .tables import _context_chapter, _context_region

EXPORT_HEADERS = [
    "Award",
    "Level",
    "Category",
    "Recipient",
    "Recipient Kind",
    "Chapter",
    "Region",
    "Cycle",
    "Effective Date",
    "Status",
    "Source",
    "Granted By",
    "Granted At",
    "Reason",
    "Revoked At",
    "Revoke Reason",
]

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _iso(value):
    return value.isoformat() if value is not None else ""


def grant_row(grant):
    """A flat list of display values for one grant, matching ``EXPORT_HEADERS``."""
    chapter = _context_chapter(grant)
    region = _context_region(grant)
    return [
        grant.award_type.name,
        grant.award_type.get_level_display(),
        grant.award_type.category,
        grant.recipient_display,
        (grant.recipient_kind or "").title(),
        str(chapter) if chapter is not None else "",
        str(region) if region is not None else "",
        grant.cycle.name,
        _iso(grant.effective_date),
        grant.get_status_display(),
        grant.get_source_display(),
        str(grant.granted_by) if grant.granted_by_id else "",
        _iso(grant.granted_at),
        grant.reason,
        _iso(grant.revoked_at),
        grant.revoke_reason,
    ]


def _timestamped(stem, ext):
    return f"{stem}_{datetime.datetime.now():%Y%m%d_%H%M%S}.{ext}"


def grants_csv_response(queryset, filename_stem="awards_export"):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{_timestamped(filename_stem, "csv")}"'
    writer = csv.writer(response)
    writer.writerow(EXPORT_HEADERS)
    for grant in queryset:
        writer.writerow(escape_csv_row(grant_row(grant)))
    return response


def grants_xlsx_response(queryset, filename_stem="awards_export"):
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Awards"
    worksheet.append(EXPORT_HEADERS)
    for grant in queryset:
        worksheet.append(grant_row(grant))
    response = HttpResponse(content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{_timestamped(filename_stem, "xlsx")}"'
    workbook.save(response)
    return response


def grants_export_response(queryset, *, fmt="csv", filename_stem="awards_export"):
    """Return a CSV (default) or XLSX (``fmt="xlsx"``) download for ``queryset``."""
    if fmt == "xlsx":
        return grants_xlsx_response(queryset, filename_stem)
    return grants_csv_response(queryset, filename_stem)
