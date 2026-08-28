"""Add `User.major_final` and seed it from the pledge-form major.

`major` is a per-chapter `ChapterCurricula` row; `major_final` points at the
shared `jobs.Major` vocabulary. The backfill maps each curriculum's text through
the same curated alias list `populate_job_majors` uses so a member whose pledge
major was "Aeronautical & Astronautical Engineering" lands on the canonical
"aerospace engineering" row rather than adding a near-duplicate.

The backfill is set-based on purpose: a fixed number of queries plus batched
inserts, no per-member or per-name query. Production has hundreds of thousands
of members, so keep it that way.
"""

import json
from pathlib import Path

from django.db import migrations, models

# Rows per bulk_create round trip.
BATCH = 1000

FIXTURE = Path(__file__).resolve().parents[2] / "jobs" / "fixtures" / "job_majors.json"

# Curriculum placeholders that should not become a major of their own.
_SKIP_NAMES = {"other", "others", "unknown", "undecided", "undeclared", "none", "n/a", "na"}


def _normalize(name):
    """Match `populate_job_majors.normalize`: collapse whitespace, lowercase."""
    return " ".join((name or "").split()).lower()


def _alias_map():
    """Spelling -> canonical major name, from the curated job board fixture.

    A missing or unreadable fixture is not fatal: names then fall back to their
    normalized selves, which `populate_job_majors` can still merge later.
    """
    try:
        entries = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    aliases = {}
    for entry in entries:
        canonical = _normalize(entry.get("name"))
        if not canonical:
            continue
        aliases[canonical] = canonical
        for spelling in entry.get("aliases", []):
            spelling = _normalize(spelling)
            if spelling:
                aliases.setdefault(spelling, canonical)
    return aliases


def populate_major_final(apps, schema_editor):
    ChapterCurricula = apps.get_model("chapters", "ChapterCurricula")
    Major = apps.get_model("jobs", "Major")
    User = apps.get_model("users", "User")
    through = User._meta.get_field("major_final").remote_field.through

    # order_by() clears User.Meta.ordering so the streaming pass below does not
    # sort the whole member table.
    with_major = User.objects.exclude(major__isnull=True).order_by()
    if not with_major.exists():
        return

    aliases = _alias_map()
    # One query for the whole (small) curriculum table; resolving a name is then
    # a dict hit instead of a query per member.
    canonical_by_curricula = {}
    for curricula_id, text in ChapterCurricula.objects.values_list("id", "major"):
        name = _normalize(text)
        if not name or name in _SKIP_NAMES:
            continue
        canonical_by_curricula[curricula_id] = aliases.get(name, name)[:1000]
    if not canonical_by_curricula:
        return

    existing = {_normalize(name): pk for pk, name in Major.objects.values_list("id", "name")}
    missing = {name for name in canonical_by_curricula.values() if name not in existing}
    if missing:
        Major.objects.bulk_create(
            [Major(name=name) for name in sorted(missing)],
            batch_size=BATCH,
            ignore_conflicts=True,
        )
        existing = {_normalize(name): pk for pk, name in Major.objects.values_list("id", "name")}

    major_id_by_curricula = {
        curricula_id: existing[name] for curricula_id, name in canonical_by_curricula.items() if name in existing
    }
    if not major_id_by_curricula:
        return

    links = []
    for user_id, curricula_id in with_major.values_list("id", "major_id").iterator(chunk_size=2000):
        major_id = major_id_by_curricula.get(curricula_id)
        if major_id is None:
            continue
        links.append(through(user_id=user_id, major_id=major_id))
        if len(links) >= BATCH:
            through.objects.bulk_create(links, batch_size=BATCH, ignore_conflicts=True)
            links = []
    if links:
        through.objects.bulk_create(links, batch_size=BATCH, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("chapters", "0001_initial"),
        ("jobs", "0001_initial"),
        ("users", "0044_employer_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="major_final",
            field=models.ManyToManyField(
                blank=True,
                related_name="members",
                to="jobs.major",
                verbose_name="Final Major(s)",
            ),
        ),
        migrations.RunPython(populate_major_final, reverse_code=migrations.RunPython.noop),
    ]
