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
    from thetatauCMT.users.filters import UserRoleListFilter
    from thetatauCMT.users.models import User
    from thetatauCMT.regions.models import Region

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
    from thetatauCMT.users.filters import AdvisorListFilter
    from thetatauCMT.users.models import User
    from thetatauCMT.regions.models import Region

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
