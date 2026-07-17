import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.awards.services import revoke_grant
from thetatauCMT.awards.tests._helpers import sign_rmp
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardGrantFactory, AwardTypeFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

_NAMES = list(GREEK_ABR.values())


def _natoff():
    """A logged-in National Officer (natoff group) with a current RMP signature."""
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    sign_rmp(user)
    return user


def _content(response):
    return response.content.decode()


def _award_names(response):
    """Award names actually present in the (filtered) directory rows.

    Asserting against the filtered queryset -- rather than the raw HTML -- avoids
    false matches from award / cycle / chapter names rendered in the filter
    ``<select>`` dropdowns.
    """
    return {grant.award_type.name for grant in response.context["filter"].qs}


# ---------------------------------------------------------------------------
# Acceptance: public access (no login required)
# ---------------------------------------------------------------------------
def test_directory_is_public(client):
    """An anonymous visitor can browse the award-winner directory."""
    response = client.get(reverse("awards:directory"))
    assert response.status_code == 200


def test_directory_lists_active_winners(client):
    member = UserFactory(status="active")
    AwardGrantFactory(award_type=AwardTypeFactory(name="Distinguished Service"), recipient_member=member)
    response = client.get(reverse("awards:directory"))
    assert "Distinguished Service" in _award_names(response)
    assert member.name in _content(response)  # recipient rendered in the table


# ---------------------------------------------------------------------------
# Acceptance: filter by award type
# ---------------------------------------------------------------------------
def test_filter_by_award_type(client):
    award_a = AwardTypeFactory(name="Alpha Prize")
    award_b = AwardTypeFactory(name="Beta Prize")
    AwardGrantFactory(award_type=award_a, recipient_member=UserFactory(status="active"))
    AwardGrantFactory(award_type=award_b, recipient_member=UserFactory(status="active"))
    names = _award_names(client.get(reverse("awards:directory"), {"award_type": award_a.pk}))
    assert "Alpha Prize" in names
    assert "Beta Prize" not in names


# ---------------------------------------------------------------------------
# Acceptance: filter by level
# ---------------------------------------------------------------------------
def test_filter_by_level(client):
    member_award = AwardTypeFactory(name="Member Level Award", level="member")
    chapter_award = AwardTypeFactory(name="Chapter Level Award", level="chapter")
    AwardGrantFactory(award_type=member_award, recipient_member=UserFactory(status="active"))
    AwardGrantFactory(award_type=chapter_award, recipient_member=None, recipient_chapter=ChapterFactory(name=_NAMES[0]))
    names = _award_names(client.get(reverse("awards:directory"), {"level": "chapter"}))
    assert "Chapter Level Award" in names
    assert "Member Level Award" not in names


# ---------------------------------------------------------------------------
# Acceptance: filter by cycle
# ---------------------------------------------------------------------------
def test_filter_by_cycle(client):
    cycle_a = AwardCycleFactory(name="2024")
    cycle_b = AwardCycleFactory(name="2025")
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Cycle A Award"), cycle=cycle_a, recipient_member=UserFactory(status="active")
    )
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Cycle B Award"), cycle=cycle_b, recipient_member=UserFactory(status="active")
    )
    names = _award_names(client.get(reverse("awards:directory"), {"cycle": cycle_a.pk}))
    assert "Cycle A Award" in names
    assert "Cycle B Award" not in names


# ---------------------------------------------------------------------------
# Acceptance: filter by chapter (matches chapter recipients and members of it)
# ---------------------------------------------------------------------------
def test_filter_by_chapter(client):
    chapter_a = ChapterFactory(name=_NAMES[0])
    chapter_b = ChapterFactory(name=_NAMES[1])
    # A member of chapter A.
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Member In A Award"),
        recipient_member=UserFactory(status="active", chapter=chapter_a),
    )
    # Chapter B itself is a recipient.
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Chapter B Award"),
        recipient_member=None,
        recipient_chapter=chapter_b,
    )
    # Filtering by chapter A shows the member-of-A grant, not chapter B's.
    names_a = _award_names(client.get(reverse("awards:directory"), {"chapter": chapter_a.slug}))
    assert "Member In A Award" in names_a
    assert "Chapter B Award" not in names_a
    # Filtering by chapter B shows the chapter-recipient grant.
    names_b = _award_names(client.get(reverse("awards:directory"), {"chapter": chapter_b.slug}))
    assert "Chapter B Award" in names_b
    assert "Member In A Award" not in names_b


# ---------------------------------------------------------------------------
# Acceptance: filter by region (member / chapter / region recipients)
# ---------------------------------------------------------------------------
def test_filter_by_region(client):
    region_a = RegionFactory(name="Region Alpha")
    region_b = RegionFactory(name="Region Beta")
    chapter_a = ChapterFactory(name=_NAMES[0], region=region_a)
    chapter_b = ChapterFactory(name=_NAMES[1], region=region_b)
    # Member whose chapter is in region A.
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Region A Member Award"),
        recipient_member=UserFactory(status="active", chapter=chapter_a),
    )
    # Chapter in region B is a recipient.
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Region B Chapter Award"),
        recipient_member=None,
        recipient_chapter=chapter_b,
    )
    # Region A itself is a recipient.
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Region A Direct Award"),
        recipient_member=None,
        recipient_region=region_a,
    )
    names_a = _award_names(client.get(reverse("awards:directory"), {"region": region_a.slug}))
    assert "Region A Member Award" in names_a
    assert "Region A Direct Award" in names_a
    assert "Region B Chapter Award" not in names_a

    names_b = _award_names(client.get(reverse("awards:directory"), {"region": region_b.slug}))
    assert "Region B Chapter Award" in names_b
    assert "Region A Member Award" not in names_b


# ---------------------------------------------------------------------------
# Acceptance: "all winners of X" view
# ---------------------------------------------------------------------------
def test_type_winners_view(client):
    award = AwardTypeFactory(name="Golden Gear")
    other = AwardTypeFactory(name="Silver Gear")
    winner = UserFactory(status="active")
    AwardGrantFactory(award_type=award, recipient_member=winner)
    AwardGrantFactory(award_type=other, recipient_member=UserFactory(status="active"))
    response = client.get(reverse("awards:type_winners", args=[award.pk]))
    assert response.status_code == 200
    assert "Winners of Golden Gear" in _content(response)  # heading
    names = _award_names(response)
    assert "Golden Gear" in names
    assert "Silver Gear" not in names


def test_type_winners_view_unknown_pk_404(client):
    assert client.get(reverse("awards:type_winners", args=[999999])).status_code == 404


# ---------------------------------------------------------------------------
# Acceptance: "winners in cycle Y" view
# ---------------------------------------------------------------------------
def test_cycle_winners_view(client):
    cycle = AwardCycleFactory(name="Convention 2025")
    other_cycle = AwardCycleFactory(name="Convention 2023")
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="In Cycle Award"), cycle=cycle, recipient_member=UserFactory(status="active")
    )
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Other Cycle Award"),
        cycle=other_cycle,
        recipient_member=UserFactory(status="active"),
    )
    response = client.get(reverse("awards:cycle_winners", args=[cycle.pk]))
    assert response.status_code == 200
    assert "Winners in Convention 2025" in _content(response)  # heading
    names = _award_names(response)
    assert "In Cycle Award" in names
    assert "Other Cycle Award" not in names


# ---------------------------------------------------------------------------
# Acceptance: revoked excluded by default, labeled when requested
# ---------------------------------------------------------------------------
def test_revoked_excluded_by_default(client):
    grant = AwardGrantFactory(award_type=AwardTypeFactory(name="Revoked Away Award"))
    revoke_grant(grant, revoked_by=UserFactory(), reason="mistake")
    response = client.get(reverse("awards:directory"))
    assert "Revoked Away Award" not in _award_names(response)


def test_revoked_shown_to_national_officer_when_requested(client):
    grant = AwardGrantFactory(award_type=AwardTypeFactory(name="Revoked Shown Award"))
    revoke_grant(grant, revoked_by=UserFactory(), reason="mistake")
    client.force_login(_natoff())
    response = client.get(reverse("awards:directory"), {"show_revoked": "1"})
    assert "Revoked Shown Award" in _award_names(response)
    # The status column is rendered with a revoked badge when revoked grants show.
    assert "bg-danger" in _content(response)


def test_revoked_hidden_from_non_national_officer(client):
    grant = AwardGrantFactory(award_type=AwardTypeFactory(name="Hidden Revoked Award"))
    revoke_grant(grant, revoked_by=UserFactory(), reason="mistake")
    # Even with ?show_revoked=1, a non-National-Officer never sees revoked grants.
    response = client.get(reverse("awards:directory"), {"show_revoked": "1"})
    assert "Hidden Revoked Award" not in _award_names(response)
    assert response.context["can_view_revoked"] is False


def test_active_grants_still_shown_with_show_revoked(client):
    AwardGrantFactory(award_type=AwardTypeFactory(name="Active Alongside Award"))
    response = client.get(reverse("awards:directory"), {"show_revoked": "1"})
    assert "Active Alongside Award" in _award_names(response)


# ---------------------------------------------------------------------------
# Acceptance: recipient search
# ---------------------------------------------------------------------------
def test_recipient_search(client):
    member = UserFactory(status="active")
    AwardGrantFactory(award_type=AwardTypeFactory(name="Searchable Member Award"), recipient_member=member)
    AwardGrantFactory(
        award_type=AwardTypeFactory(name="Unsearched Chapter Award"),
        recipient_member=None,
        recipient_chapter=ChapterFactory(name=_NAMES[0]),
    )
    names = _award_names(client.get(reverse("awards:directory"), {"recipient": member.name}))
    assert "Searchable Member Award" in names
    assert "Unsearched Chapter Award" not in names
