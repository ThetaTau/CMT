"""vCard 3.0 renderer for contact-sync exports (RFC 2426 / RFC 6350).

Hand-rolled instead of pulling in ``vobject`` because we emit only the small
subset of properties Google Contacts / Outlook / Apple Contacts need:
``FN``, ``N``, ``EMAIL``, ``TEL``, ``ORG``, ``TITLE``, ``NOTE``, ``CATEGORIES``.

The output uses CRLF line endings (RFC 6350 §3.3) and quotes special characters
per §3.4.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from .officers import OfficerContact

# Any of these characters requires escaping in vCard TEXT values.
_ESCAPE_RE = re.compile(r"([\\,;])")
CRLF = "\r\n"
LINE_MAX = 75  # RFC 6350 §3.2 folding limit
VCARD_MIME_TYPE = "text/vcard; charset=utf-8"


def _escape(value: str) -> str:
    if not value:
        return ""
    value = _ESCAPE_RE.sub(r"\\\1", value)
    return value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _fold(line: str) -> str:
    """Fold a single vCard line at 75 octets per RFC 6350 §3.2."""
    if len(line.encode("utf-8")) <= LINE_MAX:
        return line
    out: list[str] = []
    remaining = line
    first = True
    while remaining:
        # Slice by characters, then trim so the byte count stays <=75.
        take = LINE_MAX if first else LINE_MAX - 1
        chunk = remaining[:take]
        while len(chunk.encode("utf-8")) > take and chunk:
            chunk = chunk[:-1]
        if not chunk:
            # Guard against pathological single-char > 75 bytes (shouldn't happen).
            chunk = remaining[0]
        out.append(chunk if first else " " + chunk)
        remaining = remaining[len(chunk) :]
        first = False
    return CRLF.join(out)


def _line(name: str, value: str, *, params: dict[str, str] | None = None) -> str:
    parts = [name]
    if params:
        for key, val in params.items():
            parts.append(f"{key}={val}")
    header = ";".join(parts)
    return _fold(f"{header}:{value}")


def _n_value(contact: OfficerContact) -> str:
    # N is "Family;Given;Additional;Prefix;Suffix" per RFC 6350 §6.2.2.
    given = contact.preferred_name or contact.first_name
    additional = contact.middle_name if not contact.preferred_name else contact.first_name
    return ";".join(_escape(v) for v in (contact.last_name, given, additional, "", contact.suffix))


def build_vcard(contact: OfficerContact, *, source_label: str = "Theta Tau CMT") -> str:
    """Render a single :class:`OfficerContact` as a vCard 3.0 string."""
    lines: list[str] = ["BEGIN:VCARD", "VERSION:3.0"]
    lines.append(_line("FN", _escape(contact.display_name)))
    lines.append(_line("N", _n_value(contact)))
    org_value = ";".join(_escape(v) for v in ("Theta Tau", f"{contact.chapter_name} Chapter"))
    lines.append(_line("ORG", org_value))
    title = contact.role.title()
    if contact.extra_roles:
        title = title + " / " + " / ".join(r.title() for r in contact.extra_roles)
    lines.append(_line("TITLE", _escape(title)))
    for idx, email in enumerate(contact.emails):
        params = {"TYPE": "INTERNET,PREF" if idx == 0 else "INTERNET"}
        lines.append(_line("EMAIL", _escape(email), params=params))
    if contact.phone:
        lines.append(_line("TEL", _escape(contact.phone), params={"TYPE": "CELL,VOICE"}))
    categories = ",".join(_escape(v) for v in ("Theta Tau", f"{contact.chapter_name} Chapter", contact.role.title()))
    lines.append(_line("CATEGORIES", categories))
    note = f"Synced from {source_label} on {date.today().isoformat()}"
    lines.append(_line("NOTE", _escape(note)))
    lines.append("END:VCARD")
    return CRLF.join(lines) + CRLF


def build_vcard_collection(
    contacts: Iterable[OfficerContact],
    *,
    source_label: str = "Theta Tau CMT",
) -> str:
    """Render an iterable of contacts as a concatenated vCard 3.0 document."""
    return "".join(build_vcard(c, source_label=source_label) for c in contacts)
