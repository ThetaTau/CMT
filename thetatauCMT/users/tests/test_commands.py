"""
Tests for the officer-update reminder commands.

Covers the split between the per-chapter daily reminder
(``officer_update_reminder_email``) and the weekly Regional Director roll-up
(``region_officer_reminder_digest``):

* the daily reminder no longer emails an unresponsive chapter's Regional
  Director every day (no recipients -> no send, and the region is not cc'd), and
* Regional Directors instead receive one weekly summary per region.
"""

import datetime
import uuid
from io import StringIO

import pytest
from django.core.management import call_command

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _region(**kwargs):
    """A region with a unique name so a reused test DB can't leak chapters into it."""
    kwargs.setdefault("name", f"RDReg {uuid.uuid4().hex[:8]}")
    return RegionFactory.create(**kwargs)


def _chapter_in_region(region, **kwargs):
    """Create a chapter attached to ``region`` with a clean officer slate.

    ``ChapterFactory`` uses ``django_get_or_create=("name",)`` and may drop a
    ``region=`` kwarg, so the region is assigned after creation (the documented
    ChapterFactory-collision workaround). Any pre-existing officer roles from a
    reused test DB are cleared so ``get_about_expired_coucil`` is deterministic.
    """
    chapter = ChapterFactory.create(**kwargs)
    chapter.region = region
    chapter.save(update_fields=["region"])
    UserRoleChange.objects.filter(user__chapter=chapter).delete()
    return chapter


def _email_body(email):
    parts = [email.body]
    parts.extend(content for content, _ in getattr(email, "alternatives", []))
    return "\n".join(parts)


# ─── officer_update_reminder_email (daily) ────────────────────────────────────


@pytest.mark.django_db
def test_daily_reminder_skips_chapter_with_no_recipients(mailoutbox):
    """A chapter with no current/past officers no longer emails only the RD daily."""
    region = _region(email="region-only@example.com")
    chapter = _chapter_in_region(region)

    call_command("officer_update_reminder_email", chapter=[chapter.slug], stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_daily_reminder_sends_to_officers_without_region_cc(mailoutbox):
    """When there are chapter recipients the reminder sends, but never cc's the RD."""
    region = _region(email="region-cc@example.com")
    chapter = _chapter_in_region(region)
    officer = UserFactory.create(chapter=chapter, email="pastregent@example.com")
    # current not passed -> role ended in the past 8 months => a "past officer"
    UserRoleChangeFactory.create(user=officer, role="regent")

    call_command("officer_update_reminder_email", chapter=[chapter.slug], stdout=StringIO())

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "pastregent@example.com" in email.to
    assert "region-cc@example.com" not in (email.cc or [])
    assert "region-cc@example.com" not in email.to


# ─── region_officer_reminder_digest (weekly) ──────────────────────────────────


@pytest.mark.django_db
def test_digest_sends_one_summary_to_region_directors(mailoutbox):
    region = _region(email="rd-mailbox@example.com")
    director = UserFactory.create(email="director@example.com")
    region.directors.add(director)
    chapter = _chapter_in_region(region)

    call_command("region_officer_reminder_digest", "--region", region.slug, "--override", stdout=StringIO())

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "rd-mailbox@example.com" in email.to
    assert "director@example.com" in email.to
    assert region.name in email.subject
    assert chapter.name in _email_body(email)


@pytest.mark.django_db
def test_digest_lists_all_chapters_needing_updates(mailoutbox):
    region = _region(email="rd-multi@example.com")
    chapter_a = _chapter_in_region(region, name="alpha")
    chapter_b = _chapter_in_region(region, name="beta")

    call_command("region_officer_reminder_digest", "--region", region.slug, "--override", stdout=StringIO())

    assert len(mailoutbox) == 1
    body = _email_body(mailoutbox[0])
    assert chapter_a.name in body
    assert chapter_b.name in body


@pytest.mark.django_db
def test_digest_skips_region_with_no_updates(mailoutbox):
    region = _region(email="rd-empty@example.com")

    call_command("region_officer_reminder_digest", "--region", region.slug, "--override", stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_digest_dry_run_sends_nothing(mailoutbox):
    region = _region(email="rd-dry@example.com")
    _chapter_in_region(region)
    out = StringIO()

    call_command("region_officer_reminder_digest", "--region", region.slug, "--dry-run", stdout=out)

    assert mailoutbox == []
    assert "dry-run" in out.getvalue()


@pytest.mark.django_db
def test_digest_skips_when_not_scheduled_weekday(mailoutbox):
    """Run daily but only send on the target weekday (PythonAnywhere has no weekly task)."""
    region = _region(email="rd-gated@example.com")
    _chapter_in_region(region)  # a chapter that WOULD be reported if not gated
    not_today = (datetime.date.today().weekday() + 1) % 7
    out = StringIO()

    call_command(
        "region_officer_reminder_digest",
        "--region",
        region.slug,
        "--weekday",
        str(not_today),
        stdout=out,
    )

    assert mailoutbox == []
    assert "Not the scheduled day" in out.getvalue()
