"""CSV injection (a.k.a. formula injection) hardening for data exports.

Spreadsheet applications (Excel, Google Sheets, LibreOffice) treat a cell that
begins with ``= + - @`` or a tab/carriage-return as a **formula**. If exported
user-supplied text starts with one of those characters, opening the file can
execute the "formula" (data exfiltration, command execution via DDE, etc.).

:func:`escape_csv_value` prefixes such cells with a single quote so the content
is always treated as text. Genuine numeric values (including negative numbers
like ``-5`` or ``+3.14``) are left untouched so financial exports stay usable.
"""

import re

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_NUMERIC_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")


def escape_csv_value(value):
    """Neutralize a single cell that could be interpreted as a formula."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return text
    if text[0] in _FORMULA_PREFIXES and not _NUMERIC_RE.match(text):
        return "'" + text
    return text


def escape_csv_row(row):
    """Return ``row`` (an iterable of cells) with every cell escaped."""
    return [escape_csv_value(cell) for cell in row]
