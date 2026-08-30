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
# Employer / Position registries (free-text resolution)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_positions_from_text_splits_cleans_and_reuses():
    from thetatauCMT.users.models import Position, positions_from_text

    existing = Position.objects.create(name="Engineer")
    positions = positions_from_text("  engineer , Project   Manager ,, ")
    assert positions == [existing, Position.objects.get(name="Project Manager")]
    assert Position.objects.filter(name__iexact="engineer").count() == 1


@pytest.mark.django_db
def test_employer_from_text_matches_case_insensitively():
    from thetatauCMT.forms.models import Employer, employer_from_text

    existing = Employer.objects.create(name="Boeing")
    assert employer_from_text("  boeing ") == existing
    assert employer_from_text("") is None
    assert employer_from_text("Lockheed Martin").name == "Lockheed Martin"


@pytest.mark.django_db
def test_position_clean_normalizes_whitespace():
    from thetatauCMT.users.models import Position

    position = Position(name="  Field   Engineer  ")
    position.full_clean()
    assert position.name == "Field Engineer"


# ---------------------------------------------------------------------------
# Final major(s)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_major_final_copies_pledge_major():
    from thetatauCMT.jobs.models import Major
    from thetatauCMT.users.tests.factories import UserFactory as _UserFactory

    existing = Major.objects.create(name="chemical engineering")
    user = _UserFactory.create()
    user.major.major = "Chemical Engineering"
    user.major.save(update_fields=["major"])
    user.seed_major_final()
    assert list(user.major_final.all()) == [existing]
    assert Major.objects.filter(name__iexact="chemical engineering").count() == 1


@pytest.mark.django_db
def test_seed_major_final_leaves_a_curated_list_alone():
    from thetatauCMT.jobs.models import Major
    from thetatauCMT.users.tests.factories import UserFactory as _UserFactory

    user = _UserFactory.create()
    user.major.major = "Chemical Engineering"
    user.major.save(update_fields=["major"])
    physics = Major.objects.create(name="physics")
    user.major_final.add(physics)
    user.seed_major_final()
    assert list(user.major_final.all()) == [physics]


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
    User,
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
def test_contact_visible_to_chapter_officer_always_sees():
    """Officers can always see their own chapter's members, even at 'no_one'."""
    chapter = ChapterFactory(name=_GREEK_NAMES[0])
    owner = UserFactory(chapter=chapter)
    officer = _in_group(UserFactory(chapter=chapter), "officer")
    plain_member = UserFactory(chapter=chapter)
    other_officer = _in_group(UserFactory(chapter=ChapterFactory(name=_GREEK_NAMES[1])), "officer")
    assert owner.contact_visible_to(officer, CONTACT_VISIBILITY_NO_ONE) is True
    assert owner.contact_visible_to(plain_member, CONTACT_VISIBILITY_NO_ONE) is False
    # An officer of a DIFFERENT chapter must not see it.
    assert owner.contact_visible_to(other_officer, CONTACT_VISIBILITY_NO_ONE) is False


@pytest.mark.django_db
def test_contact_visible_to_retired_officers_level_behaves_like_no_one():
    """Rows saved at the retired 'officers' level keep working."""
    chapter = ChapterFactory(name=_GREEK_NAMES[0])
    owner = UserFactory(chapter=chapter)
    officer = _in_group(UserFactory(chapter=chapter), "officer")
    plain_member = UserFactory(chapter=chapter)
    assert owner.contact_visible_to(officer, CONTACT_VISIBILITY_OFFICERS) is True
    assert owner.contact_visible_to(plain_member, CONTACT_VISIBILITY_OFFICERS) is False


def test_contact_visibility_choices_drop_the_officers_level():
    """'officers' is not offered: it now means the same thing as 'no_one'."""
    from thetatauCMT.users.models import CONTACT_VISIBILITY_CHOICES

    values = [value for value, _ in CONTACT_VISIBILITY_CHOICES]
    assert values == [
        CONTACT_VISIBILITY_NO_ONE,
        CONTACT_VISIBILITY_CHAPTER,
        CONTACT_VISIBILITY_MEMBERS,
    ]
    labels = dict(CONTACT_VISIBILITY_CHOICES)
    assert labels[CONTACT_VISIBILITY_NO_ONE] == "Only National Officers, Admins, and my chapter's officers"


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


# ---------------------------------------------------------------------------
# Hide national officer functionality (natoff_hidden / view as member)
# ---------------------------------------------------------------------------
from core.models import user_is_national_officer  # noqa: E402
from thetatauCMT.users.models import UserAlter  # noqa: E402


@pytest.mark.django_db
def test_natoff_hidden_false_for_non_natoff():
    user = UserFactory()
    assert user.in_national_officer_group is False
    assert user.natoff_hidden is False
    assert user.is_national_officer_group is False


@pytest.mark.django_db
def test_natoff_group_acts_as_national_officer_by_default():
    user = _in_group(UserFactory(), "natoff")
    assert user.in_national_officer_group is True
    assert user.natoff_hidden is False
    assert user.is_national_officer_group is True
    assert user_is_national_officer(user) is True


@pytest.mark.django_db
def test_hide_natoff_makes_user_act_as_member():
    user = _in_group(UserFactory(), "natoff")
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    # Still a raw member of the group (so the switch-back UI stays available)...
    assert user.in_national_officer_group is True
    assert user.natoff_hidden is True
    # ...but not currently *acting* as a National Officer.
    assert user.is_national_officer_group is False
    assert user_is_national_officer(user) is False


@pytest.mark.django_db
def test_hide_natoff_still_hides_for_superuser_natoff():
    user = _in_group(UserFactory(is_superuser=True), "natoff")
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    # Even a superuser previewing as a member is not treated as a National Officer.
    assert user_is_national_officer(user) is False


@pytest.mark.django_db
def test_hide_natoff_with_role_still_acts_as_chapter_officer():
    other = ChapterFactory(name=_GREEK_NAMES[3])
    user = _in_group(UserFactory(), "natoff")
    UserAlter.objects.create(user=user, chapter=other, role="scribe", hide_natoff=True)
    # Altered chapter + role still apply while natoff functionality is hidden.
    assert user.current_chapter == other
    assert "scribe" in user.chapter_officer()
    assert user.is_national_officer_group is False


@pytest.mark.django_db
def test_hide_natoff_without_role_is_plain_member():
    other = ChapterFactory(name=_GREEK_NAMES[4])
    user = _in_group(UserFactory(), "natoff")
    UserAlter.objects.create(user=user, chapter=other, role=None, hide_natoff=True)
    assert user.current_chapter == other
    assert user.chapter_officer() == set()
    assert user.is_national_officer_group is False


# ---------------------------------------------------------------------------
# Hide admin functionality (admin_hidden / is_admin)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_hidden_false_for_non_superuser():
    user = UserFactory()
    assert user.admin_hidden is False
    assert user.is_admin is False


@pytest.mark.django_db
def test_superuser_acts_as_admin_by_default():
    user = UserFactory(is_superuser=True)
    assert user.admin_hidden is False
    assert user.is_admin is True
    assert user_is_national_officer(user) is True


@pytest.mark.django_db
def test_hide_admin_makes_user_act_as_member():
    user = UserFactory(is_superuser=True)
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_admin=True)
    # Still a raw superuser (so the switch-back control stays available)...
    assert user.is_superuser is True
    assert user.admin_hidden is True
    # ...but not currently *acting* as an Admin.
    assert user.is_admin is False
    assert user_is_national_officer(user) is False


@pytest.mark.django_db
def test_hide_admin_alone_leaves_natoff_functionality():
    user = _in_group(UserFactory(is_superuser=True), "natoff")
    UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_admin=True)
    assert user.is_admin is False
    assert user.is_national_officer_group is True
    assert user_is_national_officer(user) is True


@pytest.mark.django_db
def test_hiding_both_toggles_without_role_is_a_plain_member():
    user = _in_group(UserFactory(is_superuser=True), "natoff")
    UserAlter.objects.create(
        user=user,
        chapter=user.chapter,
        role=None,
        hide_natoff=True,
        hide_admin=True,
    )
    assert user.is_admin is False
    assert user.is_national_officer_group is False
    assert user.is_officer_group is False
    assert user.chapter_officer() == set()
    assert user_is_national_officer(user) is False


@pytest.mark.django_db
def test_changing_email_syncs_username():
    UserFactory(email="old@example.edu")
    user = User.objects.get(username="old@example.edu")
    user.email = "new@example.edu"
    user.save()
    assert user.username == "new@example.edu"
    assert User.objects.get(pk=user.pk).username == "new@example.edu"


@pytest.mark.django_db
def test_changing_email_leaves_a_customised_username_alone():
    UserFactory(email="member@example.edu", username="legacy-handle")
    user = User.objects.get(username="legacy-handle")
    user.email = "member2@example.edu"
    user.save()
    assert user.username == "legacy-handle"


@pytest.mark.django_db
def test_email_change_colliding_with_another_username_is_skipped():
    UserFactory(email="taken@example.edu")
    UserFactory(email="mine@example.edu")
    user = User.objects.get(username="mine@example.edu")
    user.email = "taken@example.edu"
    user.save()  # must not raise IntegrityError
    assert user.username == "mine@example.edu"


@pytest.mark.django_db
def test_email_change_via_update_fields_persists_username():
    UserFactory(email="a@example.edu")
    user = User.objects.get(username="a@example.edu")
    user.email = "b@example.edu"
    user.save(update_fields=["email"])
    assert User.objects.get(pk=user.pk).username == "b@example.edu"


@pytest.mark.django_db
def test_new_user_still_takes_username_from_email():
    user = UserFactory(username="", email="fresh@example.edu")
    assert user.username == "fresh@example.edu"
