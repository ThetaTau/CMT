"""Tests for chapters/management/commands/chapter_founding_day_email.py."""

import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from thetatauCMT.chapters.management.commands.chapter_founding_day_email import (
    CATEGORY_SLUG,
    CONFIG_KEY,
    _founding_day_chapters,
    _member_queryset,
)
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.users.tests.factories import UserFactory

TODAY = datetime.date.today()
# A leap year so `date(LEAP_YEAR, TODAY.month, TODAY.day)` never raises on Feb 29.
LEAP_YEAR = 2000


def _email_body(email):
    parts = [email.body]
    parts.extend(content for content, _ in getattr(email, "alternatives", []))
    return "\n".join(parts)


# ─── _founding_day_chapters ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_founding_day_chapters_matches_founding_month_and_day_any_year():
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    other = ChapterFactory.create(
        name="beta",
        active=True,
        candidate_chapter=False,
        founding_date=TODAY - datetime.timedelta(days=40),
    )
    slugs = set(_founding_day_chapters(TODAY).values_list("slug", flat=True))
    assert chapter.slug in slugs
    assert other.slug not in slugs


@pytest.mark.django_db
def test_founding_day_chapters_excludes_inactive_chapter():
    chapter = ChapterFactory.create(
        name="alpha",
        active=False,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    slugs = set(_founding_day_chapters(TODAY).values_list("slug", flat=True))
    assert chapter.slug not in slugs


@pytest.mark.django_db
def test_founding_day_chapters_excludes_colony():
    """Colonies (``candidate_chapter=True``) have not been chartered yet."""
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=True,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    slugs = set(_founding_day_chapters(TODAY).values_list("slug", flat=True))
    assert chapter.slug not in slugs


@pytest.mark.django_db
def test_founding_day_chapters_override_ignores_date_gate():
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=TODAY - datetime.timedelta(days=40),
    )
    slugs = set(_founding_day_chapters(TODAY, override=True).values_list("slug", flat=True))
    assert chapter.slug in slugs


# ─── _member_queryset ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_member_queryset_includes_actives_and_alumni_only():
    chapter = ChapterFactory.create(name="alpha")
    active_user = UserFactory.create(chapter=chapter, status="active")
    alumni_user = UserFactory.create(chapter=chapter, status="alumni")
    pledge_user = UserFactory.create(chapter=chapter, status="pnm")
    advisor_user = UserFactory.create(chapter=chapter, status="advisor")

    recipients = set(_member_queryset(chapter).values_list("pk", flat=True))

    assert active_user.pk in recipients
    assert alumni_user.pk in recipients
    assert pledge_user.pk not in recipients
    assert advisor_user.pk not in recipients


@pytest.mark.django_db
def test_member_queryset_excludes_opted_out_and_no_contact():
    chapter = ChapterFactory.create(name="alpha")
    subscribed = UserFactory.create(chapter=chapter, status="active")
    opted_out = UserFactory.create(chapter=chapter, status="active", unsubscribe_categories=[CATEGORY_SLUG])
    globally_off = UserFactory.create(chapter=chapter, status="active", unsubscribe_email=True)
    no_contact = UserFactory.create(chapter=chapter, status="active", no_contact=True)

    recipients = set(_member_queryset(chapter).values_list("pk", flat=True))

    assert subscribed.pk in recipients
    assert opted_out.pk not in recipients
    assert globally_off.pk not in recipients
    assert no_contact.pk not in recipients


# ─── command integration ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_command_sends_config_email_to_founding_day_chapter(mailoutbox):
    Config.objects.create(
        key=CONFIG_KEY,
        value="Happy Chapter Founding Day, {{ chapter.name }}! It has been {{ years }} years.",
        description="test",
    )
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    member = UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", stdout=StringIO())

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert member.email in email.to
    assert "Happy Chapter Founding Day" in _email_body(email)
    assert str(TODAY.year - LEAP_YEAR) in _email_body(email)


@pytest.mark.django_db
def test_command_skips_chapter_not_founding_today(mailoutbox):
    Config.objects.create(key=CONFIG_KEY, value="Happy Chapter Founding Day!", description="test")
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=TODAY - datetime.timedelta(days=40),
    )
    UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_command_skips_colony_even_if_date_matches(mailoutbox):
    Config.objects.create(key=CONFIG_KEY, value="Happy Chapter Founding Day!", description="test")
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=True,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_command_dry_run_does_not_send(mailoutbox):
    Config.objects.create(key=CONFIG_KEY, value="Happy Chapter Founding Day!", description="test")
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", "--dry-run", stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_command_respects_category_opt_out(mailoutbox):
    Config.objects.create(key=CONFIG_KEY, value="Happy Chapter Founding Day!", description="test")
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    UserFactory.create(chapter=chapter, status="active", unsubscribe_categories=[CATEGORY_SLUG])

    call_command("chapter_founding_day_email", stdout=StringIO())

    assert mailoutbox == []


@pytest.mark.django_db
def test_command_override_sends_regardless_of_date(mailoutbox):
    Config.objects.create(key=CONFIG_KEY, value="Happy Chapter Founding Day!", description="test")
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=TODAY - datetime.timedelta(days=40),
    )
    member = UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", "--override", stdout=StringIO())

    assert len(mailoutbox) == 1
    assert member.email in mailoutbox[0].to


@pytest.mark.django_db
def test_command_missing_config_aborts_without_error(mailoutbox):
    """No 'ChapterFoundingDay' Config row -> nothing sent, no traceback."""
    chapter = ChapterFactory.create(
        name="alpha",
        active=True,
        candidate_chapter=False,
        founding_date=datetime.date(LEAP_YEAR, TODAY.month, TODAY.day),
    )
    UserFactory.create(chapter=chapter, status="active")

    call_command("chapter_founding_day_email", stdout=StringIO(), stderr=StringIO())

    assert mailoutbox == []


def test_list_vars_prints_template_variables():
    out = StringIO()
    call_command("chapter_founding_day_email", "--list-vars", stdout=out)
    output = out.getvalue()
    assert "founding_date" in output
    assert "years" in output


@pytest.mark.django_db
def test_chapter_founding_day_category_is_registered():
    from thetatauCMT.users.unsubscribe import CATEGORY_SLUGS

    assert CATEGORY_SLUG in CATEGORY_SLUGS
