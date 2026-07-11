"""Tests for the national-officer sync scope + auto-sync toggle + weekly cmd."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.contact_sync.officers import (
    NATIONAL_ROLE_ABBR,
    NATIONAL_ROLES,
    collect_national_officer_contacts,
    national_role_abbr,
    normalize_scope,
    scope_display_name,
)
from thetatauCMT.contact_sync.providers.base import SyncResult
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _seed_national_role(user, role: str) -> None:
    UserRoleChangeFactory.create(user=user, role=role, current=True)
    user.refresh_from_db()
    current = set(user.current_roles or [])
    current.add(role)
    user.current_roles = list(current)
    user.save(update_fields=["current_roles"])


# --------------------------------------------------------------------- abbreviations
def test_national_role_abbr_matches_spec_examples():
    """User-spec examples: regional director → RD, national officer → NO, grand inner guard → GIG.

    ``grand inner guard`` is honoured via the explicit override table in
    ``_ROLE_ABBR_OVERRIDES``; the other two follow the default first-letter rule.
    """
    assert national_role_abbr("regional director") == "RD"
    assert national_role_abbr("national officer") == "NO"
    assert national_role_abbr("grand inner guard") == "GIG"


def test_national_role_abbr_skips_filler_words():
    """Common English filler words don't contribute to the abbreviation."""
    assert national_role_abbr("Diversity, Equity, and Inclusion Chair") == "DEIC"
    assert national_role_abbr("Educational Foundation Board of Director") == "EFBD"


def test_national_role_abbr_handles_hyphens():
    """Non-letter separators must NOT split a single word into two initials."""
    assert national_role_abbr("in-house counsel") == "IHC"


def test_national_role_abbr_fallback_for_blank():
    assert national_role_abbr("") == "NAT"
    assert national_role_abbr("   ") == "NAT"


def test_every_national_role_has_a_nonempty_abbr():
    for role in NATIONAL_ROLES:
        abbr = NATIONAL_ROLE_ABBR[role]
        assert abbr, f"{role!r} has empty abbr"
        assert abbr == abbr.upper()


# --------------------------------------------------------------------- collect
@pytest.mark.django_db
def test_collect_national_officer_contacts_uses_NAT_prefix_and_role_initials():
    user = UserFactory.create(
        first_name="Franklin",
        last_name="Ventura",
        email="fv@example.com",
        email_school="fv@theta.edu",
        phone_number="+15551234567",
    )
    _seed_national_role(user, "regional director")
    contacts, display = collect_national_officer_contacts()
    display_names = [c.display_name for c in contacts]
    assert "NAT-RD Franklin Ventura" in display_names
    assert display == "National Officers"
    match = next(c for c in contacts if c.user_pk == user.pk)
    # Both emails must be present so the QA'ing officer sees both push targets.
    assert set(match.emails) == {"fv@example.com", "fv@theta.edu"}


@pytest.mark.django_db
def test_collect_national_officer_contacts_skips_chapter_officers():
    """Someone with only a chapter role (e.g. regent) must not appear in the national list."""
    user = UserFactory.create(first_name="A", last_name="B", email="ab@example.com")
    _seed_national_role(user, "regent")  # chapter role, not a national one
    contacts, _ = collect_national_officer_contacts()
    assert all(c.user_pk != user.pk for c in contacts)


# --------------------------------------------------------------------- scope helpers
def test_normalize_scope_variants():
    assert normalize_scope("national") == "national"
    assert normalize_scope("region:east") == "region:east"
    assert normalize_scope("east") == "region:east"
    assert normalize_scope("") == ""
    assert normalize_scope("  east  ") == "region:east"


def test_scope_display_name_for_national_does_not_hit_db():
    assert scope_display_name("national") == "National Officers"


# --------------------------------------------------------------------- upper case
def test_chapter_abbr_is_uppercased():
    from types import SimpleNamespace

    from thetatauCMT.contact_sync.officers import _chapter_abbr

    # ``_chapter_abbr`` only reads ``.greek`` / ``.name`` / ``.slug`` — no DB
    # touch — so a simple stand-in exercises the code path without spinning up
    # a full ChapterFactory (which auto-generates curricula and would try to
    # save the model).
    lower = SimpleNamespace(greek="x", name="chi", slug="chi")
    assert _chapter_abbr(lower) == "X"
    # Fallback path: no greek, chapter name should be uppercased too.
    empty_greek = SimpleNamespace(greek="", name="alpha kappa", slug="alpha-kappa")
    assert _chapter_abbr(empty_greek) == "ALPHA"


# --------------------------------------------------------------------- national vCard
@pytest.mark.django_db
def test_national_vcard_endpoint_returns_vcf(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    _seed_national_role(user, "regional director")
    response = client.get(reverse("contact_sync:national_vcard"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/vcard")
    body = response.content.decode("utf-8")
    assert "BEGIN:VCARD" in body
    assert "NAT-RD" in body
    assert response["X-CMT-Scope"] == "national"


@pytest.mark.django_db
def test_national_vcard_endpoint_forbidden_for_non_natoff(auto_login_user):
    client, user = auto_login_user()
    response = client.get(reverse("contact_sync:national_vcard"))
    assert response.status_code == 302  # redirect via _forbid


# --------------------------------------------------------------------- sync accepts scope=national
@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s")
def test_provider_sync_accepts_scope_national(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    _seed_national_role(user, "regional director")
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.expires_at = timezone.now() + timedelta(hours=1)
    token.save()
    with mock.patch(
        "thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts",
        return_value=SyncResult(created=1, updated=0, failed=0, total=1),
    ) as push:
        response = client.post(reverse("contact_sync:google_sync"), {"scope": "national"})
    assert response.status_code == 200
    push.assert_called_once()
    contacts_arg = push.call_args[0][1]
    assert all(c.chapter_abbr == "NAT" for c in contacts_arg)


# --------------------------------------------------------------------- auto-sync toggle
@pytest.mark.django_db
def test_auto_sync_toggle_adds_and_removes_scope(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    # Turn ON.
    response = client.post(
        reverse("contact_sync:google_auto_sync"),
        {"scope": "national", "enabled": "1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert "national" in data["auto_sync_scopes"]
    token.refresh_from_db()
    assert "national" in token.auto_sync_scopes
    # Turn OFF.
    response = client.post(
        reverse("contact_sync:google_auto_sync"),
        {"scope": "national", "enabled": "0"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    token.refresh_from_db()
    assert "national" not in (token.auto_sync_scopes or [])


@pytest.mark.django_db
def test_auto_sync_requires_connected_token(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    response = client.post(
        reverse("contact_sync:google_auto_sync"),
        {"scope": "national", "enabled": "1"},
    )
    assert response.status_code == 400
    assert response.json().get("connected") is False


@pytest.mark.django_db
def test_auto_sync_forbidden_for_non_natoff(auto_login_user):
    client, user = auto_login_user()
    response = client.post(
        reverse("contact_sync:google_auto_sync"),
        {"scope": "national", "enabled": "1"},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------- weekly management command
@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s")
def test_weekly_contact_sync_pushes_enrolled_scopes():
    user = UserFactory.create()
    _seed_national_role(user, "regional director")
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.expires_at = timezone.now() + timedelta(hours=1)
    token.auto_sync_scopes = ["national"]
    token.save()
    with mock.patch(
        "thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts",
        return_value=SyncResult(created=1, updated=0, failed=0, total=1),
    ) as push:
        out = StringIO()
        call_command("weekly_contact_sync", stdout=out)
    push.assert_called_once()
    token.refresh_from_db()
    assert token.last_sync_count == 1
    assert token.last_synced_at is not None


@pytest.mark.django_db
def test_weekly_contact_sync_skips_tokens_with_no_auto_sync_scopes():
    user = UserFactory.create()
    UserContactSyncToken.objects.create(user=user, provider="google", auto_sync_scopes=[])
    with mock.patch("thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts") as push:
        call_command("weekly_contact_sync", stdout=StringIO())
    push.assert_not_called()


@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s")
def test_weekly_contact_sync_dry_run_does_not_push():
    user = UserFactory.create()
    _seed_national_role(user, "regional director")
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.expires_at = timezone.now() + timedelta(hours=1)
    token.auto_sync_scopes = ["national"]
    token.save()
    with mock.patch("thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts") as push:
        call_command("weekly_contact_sync", "--dry-run", stdout=StringIO())
    push.assert_not_called()


# --------------------------------------------------------------------- seed cmd
@pytest.mark.django_db
def test_seed_contact_sync_examples_is_idempotent():
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    ChapterFactory.create()  # ensure at least one active chapter
    call_command(
        "seed_contact_sync_examples",
        "--chapters",
        "1",
        "--skip-national",
        stdout=StringIO(),
    )
    from thetatauCMT.users.models import User

    seed_qs = User.objects.filter(email__endswith="@contact-sync-seed.thetatau.local")
    first_count = seed_qs.count()
    assert first_count >= 5  # 5 chapter officer roles for the first chapter
    # Re-run — must not create duplicates.
    call_command(
        "seed_contact_sync_examples",
        "--chapters",
        "1",
        "--skip-national",
        stdout=StringIO(),
    )
    assert seed_qs.count() == first_count
    # Every seed user must have BOTH email + email_school populated.
    for u in seed_qs:
        assert u.email
        assert u.email_school
        assert "seed-university.edu" in u.email_school


@pytest.mark.django_db
def test_seed_contact_sync_examples_national_scope_creates_all_roles():
    # National officer seeding needs at least one active chapter to fall back
    # onto for the ``chapter`` FK on User.
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    ChapterFactory.create()
    call_command(
        "seed_contact_sync_examples",
        "--skip-chapters",
        stdout=StringIO(),
    )
    contacts, _ = collect_national_officer_contacts()
    # Every registered national role should have at least one seeded officer.
    seeded_roles = {c.role for c in contacts}
    for role in NATIONAL_ROLES:
        assert role in seeded_roles, f"national role {role!r} not seeded"


# --------------------------------------------------------------------- natoff form page
@pytest.mark.django_db
def test_national_officer_form_page_includes_sync_button(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.get(reverse("forms:natoff"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Sync National Officers to Contacts" in body
    assert 'id="contactSyncModal"' in body
    assert reverse("contact_sync:national_vcard") in body
