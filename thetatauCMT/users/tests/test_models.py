import pytest


@pytest.mark.django_db
def test_get_absolute_url(tp):
    user = tp.make_user()
    assert user.get_absolute_url() == "/users/myinfo/"


@pytest.mark.django_db
def test__str__(tp):
    user = tp.make_user()
    user.name = "Test User"
    user.save(update_fields=["name"])
    assert str(user) == "Test User"


# ---------------------------------------------------------------------------
# Contact-field visibility (contact_visible_to)
# ---------------------------------------------------------------------------
from django.contrib.auth.models import AnonymousUser, Group  # noqa: E402

from thetatauCMT.chapters.models import GREEK_ABR  # noqa: E402
from thetatauCMT.chapters.tests.factories import ChapterFactory  # noqa: E402
from thetatauCMT.regions.tests.factories import RegionFactory  # noqa: E402
from thetatauCMT.users.models import (  # noqa: E402
    CONTACT_VISIBILITY_CHAPTER,
    CONTACT_VISIBILITY_MEMBERS,
    CONTACT_VISIBILITY_NO_ONE,
    CONTACT_VISIBILITY_OFFICERS,
)
from thetatauCMT.users.tests.factories import UserFactory  # noqa: E402

_GREEK_NAMES = list(GREEK_ABR.values())


def _in_group(user, name):
    group, _ = Group.objects.get_or_create(name=name)
    user.groups.add(group)
    return user


@pytest.mark.django_db
def test_contact_visible_to_owner_always_sees_own():
    owner = UserFactory()
    assert owner.contact_visible_to(owner, CONTACT_VISIBILITY_NO_ONE) is True


@pytest.mark.django_db
def test_contact_visible_to_no_one_hides_from_other_member():
    chapter = ChapterFactory(name=_GREEK_NAMES[0])
    owner = UserFactory(chapter=chapter)
    viewer = UserFactory(chapter=chapter)
    assert owner.contact_visible_to(viewer, CONTACT_VISIBILITY_NO_ONE) is False


@pytest.mark.django_db
def test_contact_visible_to_national_officer_always_sees():
    owner = UserFactory()
    natoff = _in_group(UserFactory(), "natoff")
    assert owner.contact_visible_to(natoff, CONTACT_VISIBILITY_NO_ONE) is True


@pytest.mark.django_db
def test_contact_visible_to_superuser_always_sees():
    owner = UserFactory()
    admin = UserFactory(is_superuser=True)
    assert owner.contact_visible_to(admin, CONTACT_VISIBILITY_NO_ONE) is True


@pytest.mark.django_db
def test_contact_visible_to_members_any_authenticated_member():
    owner = UserFactory(chapter=ChapterFactory(name=_GREEK_NAMES[0]))
    viewer = UserFactory(chapter=ChapterFactory(name=_GREEK_NAMES[1]))
    assert owner.contact_visible_to(viewer, CONTACT_VISIBILITY_MEMBERS) is True


@pytest.mark.django_db
def test_contact_visible_to_chapter_only_same_chapter():
    chapter = ChapterFactory(name=_GREEK_NAMES[0])
    other = ChapterFactory(name=_GREEK_NAMES[1])
    owner = UserFactory(chapter=chapter)
    same = UserFactory(chapter=chapter)
    diff = UserFactory(chapter=other)
    assert owner.contact_visible_to(same, CONTACT_VISIBILITY_CHAPTER) is True
    assert owner.contact_visible_to(diff, CONTACT_VISIBILITY_CHAPTER) is False


@pytest.mark.django_db
def test_contact_visible_to_officers_only_same_chapter_officer():
    chapter = ChapterFactory(name=_GREEK_NAMES[0])
    owner = UserFactory(chapter=chapter)
    officer = _in_group(UserFactory(chapter=chapter), "officer")
    plain_member = UserFactory(chapter=chapter)
    other_officer = _in_group(UserFactory(chapter=ChapterFactory(name=_GREEK_NAMES[1])), "officer")
    assert owner.contact_visible_to(officer, CONTACT_VISIBILITY_OFFICERS) is True
    assert owner.contact_visible_to(plain_member, CONTACT_VISIBILITY_OFFICERS) is False
    # An officer of a DIFFERENT chapter must not see it.
    assert owner.contact_visible_to(other_officer, CONTACT_VISIBILITY_OFFICERS) is False


@pytest.mark.django_db
def test_contact_visible_to_unauthenticated_is_false():
    owner = UserFactory()
    assert owner.contact_visible_to(AnonymousUser(), CONTACT_VISIBILITY_MEMBERS) is False
    assert owner.contact_visible_to(None, CONTACT_VISIBILITY_MEMBERS) is False


@pytest.mark.django_db
def test_default_contact_visibility_is_no_one():
    owner = UserFactory()
    assert owner.email_visibility == CONTACT_VISIBILITY_NO_ONE
    assert owner.phone_visibility == CONTACT_VISIBILITY_NO_ONE
    assert owner.address_visibility == CONTACT_VISIBILITY_NO_ONE


@pytest.mark.django_db
def test_director_regions_lists_directed_regions():
    region = RegionFactory(name="Test Region A")
    director = UserFactory()
    region.directors.add(director)
    assert list(director.director_regions) == [region]
    assert list(UserFactory().director_regions) == []
