"""Tests for users/filters.py."""

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_user_role_list_filter_filter_region_national():
    """filter_region with 'national' returns unchanged queryset."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    qs = User.objects.all()
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_region(qs, "region", "national")
    assert list(result) == list(qs)


@pytest.mark.django_db
def test_user_role_list_filter_filter_region_candidate_chapter():
    """filter_region with 'candidate_chapter' returns only candidate chapter users."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create(candidate_chapter=True)
    user = UserFactory.create(chapter=chapter)
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_region(qs, "region", "candidate_chapter")
    assert user in result


@pytest.mark.django_db
def test_user_role_list_filter_filter_region_by_slug():
    """filter_region with region slug filters by that region."""
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    chapter = ChapterFactory.create(region=region)
    user = UserFactory.create(chapter=chapter)
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_region(qs, "region", region.slug)
    assert user in result


@pytest.mark.django_db
def test_user_role_list_filter_filter_current_status_active():
    """filter_current_status with 'active' filters active and activeCC users."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    user = UserFactory.create(current_status="active")
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_current_status(qs, "current_status", "active")
    assert user in result


@pytest.mark.django_db
def test_user_role_list_filter_filter_current_status_pnm():
    """filter_current_status with 'pnm' filters prospective members."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    user = UserFactory.create(current_status="pnm")
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_current_status(qs, "current_status", "pnm")
    assert user in result


@pytest.mark.django_db
def test_user_role_list_filter_filter_current_status_no_value():
    """filter_current_status with no value returns unchanged queryset."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    qs = User.objects.all()
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_current_status(qs, "current_status", "")
    assert list(result) == list(qs)


@pytest.mark.django_db
def test_user_role_list_filter_filter_chapter():
    """filter_chapter filters users by chapter slug."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    chapter1 = ChapterFactory.create()
    chapter2 = ChapterFactory.create()
    user1 = UserFactory.create(chapter=chapter1)
    user2 = UserFactory.create(chapter=chapter2)
    qs = User.objects.filter(pk__in=[user1.pk, user2.pk])
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_chapter(qs, "chapter", chapter1.slug)
    assert user1 in result
    assert user2 not in result


@pytest.mark.django_db
def test_user_role_list_filter_filter_current_roles():
    """filter_current_roles filters by overlapping roles."""
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    user = UserFactory.create(current_roles=["regent"])
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(queryset=qs)
    result = f.filter_current_roles(qs, "current_roles", ["regent"])
    assert user in result


@pytest.mark.django_db
def test_advisor_list_filter_filter_region_national():
    """AdvisorListFilter filter_region with 'national' returns unchanged queryset."""
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    qs = User.objects.all()
    f = AdvisorListFilter(queryset=qs)
    result = f.filter_region(qs, "region", "national")
    assert list(result) == list(qs)


@pytest.mark.django_db
def test_advisor_list_filter_filter_region_candidate_chapter():
    """AdvisorListFilter filter_region with 'candidate_chapter' filters correctly."""
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create(candidate_chapter=True)
    user = UserFactory.create(chapter=chapter)
    qs = User.objects.filter(pk=user.pk)
    f = AdvisorListFilter(queryset=qs)
    result = f.filter_region(qs, "region", "candidate_chapter")
    assert user in result


@pytest.mark.django_db
def test_advisor_list_filter_filter_region_by_slug():
    """AdvisorListFilter filter_region with region slug filters correctly."""
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    regions = Region.objects.all()
    if not regions.exists():
        pytest.skip("No regions in DB")
    region = regions.first()
    chapter = ChapterFactory.create(region=region)
    user = UserFactory.create(chapter=chapter)
    qs = User.objects.filter(pk=user.pk)
    f = AdvisorListFilter(queryset=qs)
    result = f.filter_region(qs, "region", region.slug)
    assert user in result


@pytest.mark.django_db
def test_advisor_list_filter_filter_chapter_narrows_by_slug():
    """AdvisorListFilter.filter_chapter narrows to the given chapter slug.

    The declared ``chapter`` ChoiceFilter referenced ``method="filter_chapter"``
    but the method did not exist, so rendering the advisor list raised an
    AssertionError at filter time (issue #827).
    """
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create()
    user = UserFactory.create(chapter=chapter)
    qs = User.objects.all()
    f = AdvisorListFilter(queryset=qs)
    assert user in f.filter_chapter(qs, "chapter", chapter.slug)
    assert user not in f.filter_chapter(qs, "chapter", "a-different-chapter-slug")


@pytest.mark.django_db
def test_advisor_list_filter_chapter_choice_applies_via_qs():
    """Selecting a chapter filters ``.qs`` without raising.

    Exercises the real django-filter method-resolution path that crashed before
    ``filter_chapter`` existed (issue #827).
    """
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create()
    user = UserFactory.create(chapter=chapter)
    f = AdvisorListFilter({"chapter": chapter.slug}, queryset=User.objects.all())
    assert user in list(f.qs)


def _grad_year_users():
    """Create three users in one chapter with distinct graduation years."""
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create()
    early = UserFactory.create(chapter=chapter, graduation_year=2020)
    mid = UserFactory.create(chapter=chapter, graduation_year=2024)
    late = UserFactory.create(chapter=chapter, graduation_year=2028)
    qs = User.objects.filter(pk__in=[early.pk, mid.pk, late.pk])
    return qs, early, mid, late


@pytest.mark.django_db
def test_user_role_list_filter_graduation_year_gte():
    """graduation_year__gte returns members graduating in that year or later."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, early, mid, late = _grad_year_users()
    f = UserRoleListFilter(QueryDict("graduation_year__gte=2024"), queryset=qs)
    result = list(f.qs)
    assert early not in result
    assert mid in result
    assert late in result


@pytest.mark.django_db
def test_user_role_list_filter_graduation_year_lte():
    """graduation_year__lte returns members graduating in that year or earlier."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, early, mid, late = _grad_year_users()
    f = UserRoleListFilter(QueryDict("graduation_year__lte=2024"), queryset=qs)
    result = list(f.qs)
    assert early in result
    assert mid in result
    assert late not in result


@pytest.mark.django_db
def test_user_role_list_filter_graduation_year_range():
    """Combining gte and lte bounds members to a graduation-year window."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, early, mid, late = _grad_year_users()
    f = UserRoleListFilter(
        QueryDict("graduation_year__gte=2022&graduation_year__lte=2026"),
        queryset=qs,
    )
    result = list(f.qs)
    assert early not in result
    assert mid in result
    assert late not in result


@pytest.mark.django_db
def test_user_role_list_filter_graduation_year_icontains_preserved():
    """The original graduation_year__icontains lookup still filters by substring."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, early, mid, late = _grad_year_users()
    f = UserRoleListFilter(QueryDict("graduation_year__icontains=2028"), queryset=qs)
    result = list(f.qs)
    assert early not in result
    assert mid not in result
    assert late in result


def _badge_number_users():
    """Create three users in one chapter with distinct badge numbers."""
    from thetatauCMT.users.models import User

    chapter = ChapterFactory.create()
    low = UserFactory.create(chapter=chapter, badge_number=100)
    mid = UserFactory.create(chapter=chapter, badge_number=500)
    high = UserFactory.create(chapter=chapter, badge_number=900)
    qs = User.objects.filter(pk__in=[low.pk, mid.pk, high.pk])
    return qs, low, mid, high


@pytest.mark.django_db
def test_user_role_list_filter_badge_number_gte():
    """badge_number__gte returns members with that badge number or higher."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, low, mid, high = _badge_number_users()
    f = UserRoleListFilter(QueryDict("badge_number__gte=500"), queryset=qs)
    result = list(f.qs)
    assert low not in result
    assert mid in result
    assert high in result


@pytest.mark.django_db
def test_user_role_list_filter_badge_number_lte():
    """badge_number__lte returns members with that badge number or lower."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, low, mid, high = _badge_number_users()
    f = UserRoleListFilter(QueryDict("badge_number__lte=500"), queryset=qs)
    result = list(f.qs)
    assert low in result
    assert mid in result
    assert high not in result


@pytest.mark.django_db
def test_user_role_list_filter_badge_number_range():
    """Combining gte and lte bounds members to a badge-number window."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter

    qs, low, mid, high = _badge_number_users()
    f = UserRoleListFilter(
        QueryDict("badge_number__gte=200&badge_number__lte=700"),
        queryset=qs,
    )
    result = list(f.qs)
    assert low not in result
    assert mid in result
    assert high not in result


# ---------------------------------------------------------------------------
# Name search also matches maiden_name (marriage last name change)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filter_name_or_maiden_name_matches_maiden_name():
    """The shared helper matches maiden_name even when `name` does not contain it."""
    from thetatauCMT.users.filters import filter_name_or_maiden_name
    from thetatauCMT.users.models import User

    user = UserFactory.create(name="Jane Doe", maiden_name="Fitzgerald")
    qs = User.objects.filter(pk=user.pk)
    assert user in filter_name_or_maiden_name(qs, "name", "Fitzgerald")


@pytest.mark.django_db
def test_filter_name_or_maiden_name_still_matches_name():
    """The shared helper still matches the denormalized `name` field."""
    from thetatauCMT.users.filters import filter_name_or_maiden_name
    from thetatauCMT.users.models import User

    user = UserFactory.create(name="Jane Doe", maiden_name="Fitzgerald")
    qs = User.objects.filter(pk=user.pk)
    assert user in filter_name_or_maiden_name(qs, "name", "Jane")


@pytest.mark.django_db
def test_user_role_list_filter_name_icontains_matches_maiden_name():
    """UserRoleListFilter's name search matches a member's maiden name."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User

    user = UserFactory.create(maiden_name="Fitzgerald")
    qs = User.objects.filter(pk=user.pk)
    f = UserRoleListFilter(QueryDict("name__icontains=Fitzgerald"), queryset=qs)
    assert user in list(f.qs)


@pytest.mark.django_db
def test_advisor_list_filter_name_icontains_matches_maiden_name():
    """AdvisorListFilter's name search matches a member's maiden name."""
    from django.http import QueryDict

    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User

    user = UserFactory.create(maiden_name="Fitzgerald")
    qs = User.objects.filter(pk=user.pk)
    f = AdvisorListFilter(QueryDict("name__icontains=Fitzgerald"), queryset=qs)
    assert user in list(f.qs)


# ---------------------------------------------------------------------------
# Member search boxes (chapter roster + Search all Members)
# ---------------------------------------------------------------------------


def _search(params, queryset):
    from django.http import QueryDict

    from thetatauCMT.users.filters import UserSearchFilter

    query = QueryDict(mutable=True)
    for key, value in params.items():
        query.setlist(key, value if isinstance(value, list) else [value])
    return UserSearchFilter(query, queryset=queryset)


@pytest.mark.django_db
def test_name_box_needs_every_word_in_one_of_the_members_names():
    """A member who goes by his middle name is found by first + last name, and by maiden name."""
    from thetatauCMT.users.models import User

    names = dict(middle_name="Quill", suffix="", nickname="Skip", maiden_name="")
    henry = UserFactory.create(
        first_name="Kevin", preferred_name="Henry", last_name="Smithers", **{**names, "maiden_name": "Oldcastle"}
    )
    other = UserFactory.create(first_name="Kevin", preferred_name=None, last_name="Brown", name="Kevin Brown", **names)
    qs = User.objects.filter(pk__in=[henry.pk, other.pk])

    assert henry.name == "Henry Smithers"
    assert list(_search({"name": "kevin smithers"}, qs).qs) == [henry]
    assert list(_search({"name": "oldcastle"}, qs).qs) == [henry]
    assert set(_search({"name": "kev"}, qs).qs) == {henry, other}
    assert list(_search({"name": "kevin jones"}, qs).qs) == []


@pytest.mark.django_db
def test_initiation_boxes_follow_the_semester_boundaries():
    """Spring runs January to June and Fall July to December; only semesters with initiations are offered."""
    import datetime

    from thetatauCMT.forms.tests.factories import InitiationFactory
    from thetatauCMT.users.models import User

    fall, spring, never = UserFactory.create_batch(3)
    InitiationFactory.create(user=fall, date=datetime.date(2023, 12, 31))
    InitiationFactory.create(user=spring, date=datetime.date(2024, 1, 1))
    qs = User.objects.filter(pk__in=[fall.pk, spring.pk, never.pk])

    semesters = _search({}, qs).form.fields["initiation_semester"].choices
    assert list(semesters) == [("", "Any semester"), ("sp-2024", "Spring 2024"), ("fa-2023", "Fall 2023")]
    assert list(_search({"initiation_semester": "fa-2023"}, qs).qs) == [fall]
    assert list(_search({"initiation_semester": "sp-2024"}, qs).qs) == [spring]
    on_new_years_eve = {"initiation_date__gte": "2023-12-31", "initiation_date__lte": "2023-12-31"}
    assert list(_search(on_new_years_eve, qs).qs) == [fall]


@pytest.mark.django_db
def test_status_box_widens_each_status_to_its_group():
    """Alumni also covers deceased and candidate chapter alumni, as on the roster."""
    from thetatauCMT.users.models import User

    alumni = [UserFactory.create(current_status=status) for status in ("alumni", "alumniCC", "deceased")]
    active = UserFactory.create(current_status="active")
    qs = User.objects.filter(pk__in=[member.pk for member in [*alumni, active]])

    assert set(_search({"current_status": "alumni"}, qs).qs) == set(alumni)


@pytest.mark.django_db
def test_zip_code_box_uses_the_distance_box():
    """Zip code finds members with an address within the distance (miles) of it."""
    from address.models import Address, Country, Locality, State

    from thetatauCMT.users.models import User

    country, _ = Country.objects.get_or_create(name="Testland", code="TL")
    state = State.objects.create(name="Test State", code="TS", country=country)
    town = Locality.objects.create(name="Testville", postal_code="00042", state=state)
    uptown = Locality.objects.create(name="Uptown", postal_code="00043", state=state)
    home = Address.objects.create(raw="1 Main St", locality=town, latitude=40.0, longitude=-100.0)
    # About 14 miles north of the 00042 zip code.
    nearby = Address.objects.create(raw="2 Main St", locality=uptown, latitude=40.2, longitude=-100.0)
    local = UserFactory.create(address=home)
    commuter = UserFactory.create(address=nearby)
    qs = User.objects.filter(pk__in=[local.pk, commuter.pk])

    assert list(_search({"zip": "00042", "dist": "5"}, qs).qs) == [local]
    assert set(_search({"zip": "00042", "dist": "30"}, qs).qs) == {local, commuter}


@pytest.mark.django_db
def test_phone_box_compares_digits_only():
    """Typed and stored numbers are compared without their spaces, dashes, dots and brackets."""
    from thetatauCMT.users.models import User

    mobile = UserFactory.create(phone_number="+15124721904")
    legacy = UserFactory.create(phone_number="512.555.0100")
    qs = User.objects.filter(pk__in=[mobile.pk, legacy.pk])

    assert list(_search({"phone": "(512) 472-1904"}, qs).qs) == [mobile]
    assert list(_search({"phone": "555 0100"}, qs).qs) == [legacy]
    assert set(_search({"phone": "512"}, qs).qs) == {mobile, legacy}
    assert list(_search({"phone": "ext"}, qs).qs) == []


@pytest.mark.django_db
def test_address_box_needs_every_word_somewhere_in_the_address():
    """Words can come from the street, city, state name or code, or zip code, or a typed-in address."""
    from address.models import Address, Country, Locality, State

    from thetatauCMT.users.models import User

    country, _ = Country.objects.get_or_create(name="Testland", code="TL")
    state = State.objects.create(name="Lone Star Test", code="TXT", country=country)
    town = Locality.objects.create(name="Austintown", postal_code="78701", state=state)
    parsed = Address.objects.create(raw="221 Baker Street", street_number="221", route="Baker Street", locality=town)
    texan = UserFactory.create(address=parsed)
    typed = UserFactory.create(address=Address.objects.create(raw="17 Main St\nDenverville, CO 80202"))
    qs = User.objects.filter(pk__in=[texan.pk, typed.pk])

    assert list(_search({"address": "baker austintown"}, qs).qs) == [texan]
    assert list(_search({"address": "txt 78701"}, qs).qs) == [texan]
    assert list(_search({"address": "main denverville"}, qs).qs) == [typed]
    assert list(_search({"address": "baker denverville"}, qs).qs) == []


@pytest.mark.django_db
def test_current_roles_box_matches_any_role_picked():
    """Picking several roles finds members holding any one of them."""
    from thetatauCMT.users.models import User

    regent = UserFactory.create(current_roles=["regent"])
    treasurer = UserFactory.create(current_roles=["scribe", "treasurer"])
    director = UserFactory.create(current_roles=["regional director"])
    member = UserFactory.create(current_roles=[])
    qs = User.objects.filter(pk__in=[regent.pk, treasurer.pk, director.pk, member.pk])

    assert set(_search({"current_roles": ["regent", "treasurer"]}, qs).qs) == {regent, treasurer}
    assert list(_search({"current_roles": ["regional director"]}, qs).qs) == [director]
