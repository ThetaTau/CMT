"""Load historical Executive Council terms of office from a CSV export.

    docker exec thetataucmt_local_django python manage.py runscript load_ec_terms \
        --script-args secrets/ECTerms_3Aug2026.csv

Dry run by default; add ``commit`` to the script args to actually write the rows.

Expected columns: ``Name``, ``ID`` (the CMT user pk), ``Term of Office``, ``Role``.
"""

import csv
import datetime
import re
from collections import defaultdict

from django.db import transaction

from thetatauCMT.users.models import User, UserRoleChange

DEFAULT_PATH = "secrets/ECTerms_3Aug2026.csv"

# CSV role label -> UserRoleChange.role value (see core.models NAT_OFFICERS).
# The four delegate variants all collapse onto the single "council delegate" choice.
ROLE_MAP = {
    "grand regent": "grand regent",
    "vice grand regent": "grand vice regent",
    "grand scribe": "grand scribe",
    "grand treasurer": "grand treasurer",
    "grand marshal": "grand marshal",
    "grand inner guard": "grand inner guard",
    "grand outer guard": "grand outer guard",
    "delegate-at-large": "council delegate",
    "student member - executive council": "council delegate",
    "executive council delegate a": "council delegate",
    "executive council delegate b": "council delegate",
}

# Terms run convention to convention; the biennium boundary used elsewhere in
# the codebase (core.models.BIENNIUM_START_DATE) is July 1.
TERM_START_MONTH_DAY = (7, 1)
TERM_END_MONTH_DAY = (6, 30)

# "1911-13", "1954-56*", "1972-74†", "1998-00", "1904 (Pre-Convention)"
TERM_RE = re.compile(r"^(\d{4})(?:\s*-\s*(\d{2,4}))?")


def parse_term(text):
    """Return (start_date, end_date) for a "Term of Office" cell, or None."""
    match = TERM_RE.match((text or "").strip())
    if not match:
        return None
    start_year = int(match.group(1))
    end_raw = match.group(2)
    if end_raw is None:
        # A single pre-Convention year, e.g. "1904 (Pre-Convention)".
        end_year = start_year + 1
    else:
        end_year = int(end_raw)
        if len(end_raw) == 2:
            end_year += start_year - start_year % 100
            if end_year < start_year:
                # Century rollover, e.g. "1998-00" is 1998 to 2000.
                end_year += 100
    return (
        datetime.date(start_year, *TERM_START_MONTH_DAY),
        datetime.date(end_year, *TERM_END_MONTH_DAY),
    )


def _read_rows(path):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=encoding, newline="") as csv_file:
                return list(csv.DictReader(csv_file))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path} as utf-8 or cp1252")


def _build_name_index():
    index = defaultdict(list)
    for user in User.objects.all().only("id", "name"):
        index[(user.name or "").strip().lower()].append(user)
    return index


def _resolve_user(row, name_index):
    """Match a CSV row to a User by pk, falling back to an unambiguous name."""
    raw_id = (row.get("ID") or "").strip()
    if raw_id.isdigit():
        user = User.objects.filter(pk=int(raw_id)).first()
        if user is not None:
            return user, None
    name = (row.get("Name") or "").strip()
    matches = name_index.get(name.lower(), [])
    if len(matches) == 1:
        return matches[0], f"id {raw_id or 'blank'} not found, matched on name"
    if len(matches) > 1:
        return None, f"name matches {len(matches)} members"
    return None, "no member found"


def run(*args):
    path = DEFAULT_PATH
    commit = False
    for arg in args:
        if arg.lower() == "commit":
            commit = True
        else:
            path = arg

    rows = _read_rows(path)
    name_index = _build_name_index()
    existing = set(
        UserRoleChange.objects.filter(role__in=set(ROLE_MAP.values())).values_list("user_id", "role", "start", "end")
    )

    today = datetime.date.today()
    to_create = []
    seen = set()
    problems = []
    counts = defaultdict(int)

    for line, row in enumerate(rows, start=2):
        label = f"line {line}: {row.get('Name', '')} / {row.get('Term of Office', '')} / {row.get('Role', '')}"
        role = ROLE_MAP.get((row.get("Role") or "").strip().lower())
        if role is None:
            problems.append(f"{label} -- unknown role")
            counts["unknown role"] += 1
            continue
        term = parse_term(row.get("Term of Office"))
        if term is None:
            problems.append(f"{label} -- unparsable term")
            counts["unparsable term"] += 1
            continue
        start, end = term
        if end >= today:
            # bulk_create skips UserRoleChange.save(), so current_roles and the
            # officer/natoff groups would not be synced. Add those in the UI.
            problems.append(f"{label} -- term is not over, add it through the site instead")
            counts["current term"] += 1
            continue
        user, note = _resolve_user(row, name_index)
        if user is None:
            problems.append(f"{label} -- {note}")
            counts["no member"] += 1
            continue
        if note:
            problems.append(f"{label} -- {note}")
        key = (user.pk, role, start, end)
        if key in existing:
            counts["already loaded"] += 1
            continue
        if key in seen:
            counts["duplicate row"] += 1
            continue
        seen.add(key)
        to_create.append(UserRoleChange(user=user, role=role, start=start, end=end))

    print(f"Read {len(rows)} rows from {path}")
    for reason, count in sorted(counts.items()):
        print(f"  skipped, {reason}: {count}")
    if problems:
        print("Rows needing attention:")
        for problem in problems:
            print(f"  {problem}")
    print(f"  to create: {len(to_create)}")

    if not commit:
        print('Dry run, nothing written. Re-run with "commit" in --script-args to save.')
        return

    # bulk_create bypasses UserRoleChange.save() and post_save signals, so no
    # new officer notification or email signal fires for these historical terms.
    with transaction.atomic():
        UserRoleChange.objects.bulk_create(to_create, batch_size=500)
    print(f"Created {len(to_create)} historical role records.")
