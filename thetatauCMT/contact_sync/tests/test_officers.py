"""Tests for the officer collection helper."""

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.contact_sync.officers import (
    OFFICER_POSITION_ABBR,
    SYNCED_OFFICER_ROLES,
    collect_region_officer_contacts,
)
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _assign_role(user, role: str) -> None:
    """Attach a current UserRoleChange row for ``user`` and mirror it onto ``current_roles``.

    Uses ``current=True`` (post-generation hook on UserRoleChangeFactory) so the
    generated start/end straddle today. The model's ``save()`` pre-save logic
    then appends the role to ``user.current_roles`` for us.
    """
    UserRoleChangeFactory.create(user=user, role=role, current=True)
    user.refresh_from_db()
    current = set(user.current_roles or [])
    current.add(role)
    user.current_roles = list(current)
    user.save(update_fields=["current_roles"])


@pytest.mark.django_db
def test_collect_returns_officers_with_expected_display_name():
    chapter = ChapterFactory.create(greek="X")
    user = UserFactory.create(
        chapter=chapter,
        first_name="Franklin",
        last_name="Ventura",
        preferred_name="",
        email="frank@example.com",
        phone_number="+15551234567",
    )
    _assign_role(user, "regent")
    contacts, region_name = collect_region_officer_contacts(chapter.region.slug)
    display_names = [c.display_name for c in contacts]
    # candidate_chapter tests may have seeded a synthetic region with a different
    # display name; assert loosely against the real region's name.
    assert region_name == chapter.region.name
    assert "X-R Franklin Ventura" in display_names
    my = next(c for c in contacts if c.user_pk == user.pk)
    assert my.role == "regent"
    assert my.role_abbr == "R"
    assert my.chapter_abbr == "X"
    assert my.email == "frank@example.com"


@pytest.mark.django_db
def test_collect_role_filter_narrows_to_treasurer():
    chapter = ChapterFactory.create(greek="Y")
    for role in ("regent", "treasurer", "scribe"):
        user = UserFactory.create(chapter=chapter, first_name="A", last_name=role.title(), email=f"{role}@ex.com")
        _assign_role(user, role)
    contacts, _ = collect_region_officer_contacts(chapter.region.slug, roles=["treasurer"])
    roles = {c.role for c in contacts if c.chapter_abbr == "Y"}
    assert roles == {"treasurer"}


@pytest.mark.django_db
def test_collect_role_filter_empty_falls_back_to_all_synced_roles():
    chapter = ChapterFactory.create(greek="Z")
    user = UserFactory.create(chapter=chapter, first_name="A", last_name="Test", email="a@example.com")
    _assign_role(user, "regent")
    contacts, _ = collect_region_officer_contacts(chapter.region.slug, roles=["bogus-role"])
    assert any(c.user_pk == user.pk for c in contacts)


@pytest.mark.django_db
def test_collect_picks_highest_priority_role_when_user_holds_multiple():
    chapter = ChapterFactory.create(greek="W")
    user = UserFactory.create(chapter=chapter, first_name="Multi", last_name="Role", email="m@example.com")
    _assign_role(user, "treasurer")
    _assign_role(user, "regent")  # regent should win over treasurer
    contacts, _ = collect_region_officer_contacts(chapter.region.slug)
    ours = [c for c in contacts if c.user_pk == user.pk]
    assert len(ours) == 1
    assert ours[0].role == "regent"
    assert "treasurer" in ours[0].extra_roles


@pytest.mark.django_db
def test_collect_returns_empty_for_unknown_region_slug():
    contacts, name = collect_region_officer_contacts("does-not-exist")
    assert contacts == []
    assert name == "does-not-exist"


@pytest.mark.django_db
def test_collect_candidate_chapter_scope():
    chapter = ChapterFactory.create(greek="C", candidate_chapter=True)
    user = UserFactory.create(chapter=chapter, first_name="Cand", last_name="Idate", email="c@example.com")
    _assign_role(user, "regent")
    contacts, name = collect_region_officer_contacts("candidate_chapter")
    assert name == "Candidate Chapters"
    assert any(c.user_pk == user.pk for c in contacts)


def test_officer_position_abbr_matches_spec():
    assert OFFICER_POSITION_ABBR == {
        "regent": "R",
        "vice regent": "VR",
        "treasurer": "T",
        "scribe": "S",
        "corresponding secretary": "CS",
    }
    # Order matters: regent must appear first (priority when picking primary role).
    assert SYNCED_OFFICER_ROLES[0] == "regent"
