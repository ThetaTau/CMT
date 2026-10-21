from unittest import mock

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.db import IntegrityError
from django.utils import timezone

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.forms.tests.factories import InitiationFactory
from thetatauCMT.users.models import UserAlter
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

NME = "pledge/new member educator"


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


def _in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


@pytest.fixture
def other_chapter():
    return ChapterFactory(name="beta")


# ---------------------------------------------------------------------------
# Who can be picked (Q9)
# ---------------------------------------------------------------------------
def test_eligible_members_drop_only_the_not_initiated_statuses(chapter, other_chapter):
    kept = {_member(chapter, status).pk for status in ("active", "alumni", "away", "expelled", "deceased")}
    for status in ("pnm", "depledge", "nonmember", "friend"):
        _member(chapter, status)
    _member(other_chapter)

    assert set(services.eligible_members(chapter).values_list("pk", flat=True)) == kept
    assert not services.eligible_members(None).exists()


def test_is_initiated(chapter):
    assert services.is_initiated(_member(chapter, "alumni"))
    assert not services.is_initiated(_member(chapter, "pnm"))


def test_member_label_shows_only_a_real_badge_number(chapter):
    assert services.member_label(_member(chapter, name="Ann Lee", badge_number=1234)) == "Ann Lee (#1234)"
    assert services.member_label(_member(chapter, name="Bo Lee", badge_number=999999999)) == "Bo Lee"


def test_link_chapter_prefers_the_initiation_chapter(chapter, other_chapter):
    member = _member(chapter)
    assert services.link_chapter_for(member) == chapter

    InitiationFactory(user=member, chapter=other_chapter, date=timezone.now().date())
    member.refresh_from_db()
    assert services.link_chapter_for(member) == other_chapter


# ---------------------------------------------------------------------------
# Recording a Big
# ---------------------------------------------------------------------------
def test_set_big_records_who_how_and_where(chapter):
    little, big, officer = _member(chapter), _member(chapter), _member(chapter)

    result = services.set_big(little, big, actor=officer, source=BigLittle.Source.OFFICER)

    assert result.outcome == services.CREATED
    assert result.previous_big is None
    link = result.link
    assert (link.big, link.little, link.chapter) == (big, little, chapter)
    assert (link.source, link.created_by) == (BigLittle.Source.OFFICER, officer)
    assert services.current_big(little) == big


def test_recording_the_same_big_again_changes_nothing(chapter):
    little, big = _member(chapter), _member(chapter)
    first = services.set_big(little, big, source=BigLittle.Source.MEMBER)

    again = services.set_big(little, big, source=BigLittle.Source.MEMBER)

    assert again.outcome == services.UNCHANGED
    assert again.link == first.link
    assert BigLittle.objects.filter(little=little).count() == 1


def test_a_new_big_ends_the_old_pairing(chapter):
    little, old_big, new_big, officer = (_member(chapter) for _ in range(4))
    old = services.set_big(little, old_big, source=BigLittle.Source.MEMBER).link

    result = services.set_big(little, new_big, actor=officer, source=BigLittle.Source.OFFICER)

    assert result.outcome == services.CHANGED
    assert result.previous_big == old_big
    old.refresh_from_db()
    assert old.ended is not None
    assert old.ended_by == officer
    assert list(little.links_as_little.current()) == [result.link]
    assert services.current_big(little) == new_big


def test_a_big_can_take_twins(chapter):
    big = _member(chapter)
    twins = [_member(chapter, badge_number=20), _member(chapter, badge_number=10)]
    for twin in twins:
        services.set_big(twin, big, source=BigLittle.Source.INITIATION)

    assert [link.little for link in services.current_little_links(big)] == [twins[1], twins[0]]


def test_nobody_can_be_their_own_big(chapter):
    member = _member(chapter)
    with pytest.raises(services.BigLittleError, match="cannot be their own Big"):
        services.set_big(member, member, source=BigLittle.Source.MEMBER)


def test_a_three_generation_loop_is_refused(chapter):
    grand, big, little = _member(chapter), _member(chapter), _member(chapter)
    services.set_big(big, grand, source=BigLittle.Source.MEMBER)
    services.set_big(little, big, source=BigLittle.Source.MEMBER)

    with pytest.raises(services.BigLittleError, match="further down"):
        services.set_big(grand, little, source=BigLittle.Source.MEMBER)
    assert not grand.links_as_little.exists()


def test_the_loop_check_finishes_on_bad_data(chapter):
    first, second, newcomer = _member(chapter), _member(chapter), _member(chapter)
    BigLittle.objects.create(big=first, little=second, chapter=chapter)
    BigLittle.objects.create(big=second, little=first, chapter=chapter)

    assert services.would_create_cycle(newcomer, first) is False


def test_a_pairing_is_filed_under_the_initiation_chapter(chapter, other_chapter):
    little, big = _member(chapter), _member(chapter)
    InitiationFactory(user=little, chapter=other_chapter, date=timezone.now().date())
    little.refresh_from_db()

    link = services.set_big(little, big, source=BigLittle.Source.MEMBER).link

    assert link.chapter == other_chapter


def test_a_concurrent_insert_becomes_a_friendly_error(chapter):
    little, big = _member(chapter), _member(chapter)
    with mock.patch.object(BigLittle.objects, "create", side_effect=IntegrityError("duplicate")):
        with pytest.raises(services.BigLittleError, match="Someone else just recorded"):
            services.set_big(little, big, source=BigLittle.Source.MEMBER)


def test_remove_link_deletes_the_pairing(chapter):
    little = _member(chapter)
    link = services.set_big(little, _member(chapter), source=BigLittle.Source.MEMBER).link

    services.remove_link(link)

    assert not BigLittle.objects.filter(pk=link.pk).exists()
    assert services.current_big(little) is None


# ---------------------------------------------------------------------------
# Managers (Q4)
# ---------------------------------------------------------------------------
def test_manager_roles_default_to_the_new_member_educator():
    assert services.get_manager_roles() == {NME}
    assert services.manager_roles_label() == "the New Member Educator"


def test_manager_roles_come_from_config_and_ignore_unknown_roles():
    Config.objects.create(key=services.MANAGER_ROLES_CONFIG_KEY, value="<p>Scribe, not a role</p>")
    assert services.get_manager_roles() == {"scribe"}

    Config.objects.create(key=services.MANAGER_ROLES_CONFIG_KEY, value="nonsense")
    assert services.get_manager_roles() == {NME}


def test_officers_and_the_new_member_educator_manage_their_own_chapter(chapter, other_chapter):
    officer = _in_group(_member(chapter), "officer")
    educator = _member(chapter, current_roles=[NME])

    for user in (officer, educator):
        assert services.can_manage(user, chapter)
        assert not services.can_manage(user, other_chapter)
    assert not services.can_manage(_member(chapter), chapter)
    assert not services.can_manage(AnonymousUser(), chapter)
    assert not services.can_manage(officer, None)


def test_a_config_override_replaces_the_new_member_educator(chapter):
    Config.objects.create(key=services.MANAGER_ROLES_CONFIG_KEY, value="scribe")

    assert services.can_manage(_member(chapter, current_roles=["scribe"]), chapter)
    assert not services.can_manage(_member(chapter, current_roles=[NME]), chapter)


def test_national_officers_manage_the_chapter_they_switched_to(chapter, other_chapter):
    natoff = _in_group(_member(chapter), "natoff")
    UserAlter.objects.create(user=natoff, chapter=other_chapter)

    assert services.can_manage(natoff, other_chapter)
    assert not services.can_manage(natoff, chapter)


def test_viewing_as_a_member_needs_a_real_or_impersonated_chapter_role(chapter):
    natoff = _in_group(_member(chapter), "natoff")
    alter = UserAlter.objects.create(user=natoff, chapter=chapter, hide_natoff=True)
    assert not services.can_manage(natoff, chapter)

    alter.role = "regent"
    alter.save()
    assert services.can_manage(natoff, chapter)


def test_admins_manage_unless_admin_is_hidden(chapter):
    admin = _member(chapter, is_superuser=True)
    assert services.can_manage(admin, chapter)

    UserAlter.objects.create(user=admin, chapter=chapter, hide_admin=True)
    assert not services.can_manage(admin, chapter)


# ---------------------------------------------------------------------------
# Removing (Q3)
# ---------------------------------------------------------------------------
def test_who_can_remove_a_pairing(chapter):
    big, little, bystander = _member(chapter), _member(chapter), _member(chapter)
    officer = _in_group(_member(chapter), "officer")
    by_officer = services.set_big(little, big, actor=officer, source=BigLittle.Source.OFFICER).link

    assert services.can_remove(little, by_officer)
    assert services.can_remove(officer, by_officer)
    assert not services.can_remove(big, by_officer)
    assert not services.can_remove(bystander, by_officer)
    assert not services.can_remove(AnonymousUser(), by_officer)

    services.remove_link(by_officer)
    by_big = services.set_big(little, big, actor=big, source=BigLittle.Source.MEMBER).link
    assert services.can_remove(big, by_big)


# ---------------------------------------------------------------------------
# Who sees a chapter's tree (Q2)
# ---------------------------------------------------------------------------
def test_tree_is_for_the_chapter_rds_national_officers_and_admins(chapter, other_chapter):
    assert services.can_view_tree(_member(chapter), chapter)
    assert not services.can_view_tree(_member(other_chapter), chapter)
    assert not services.can_view_tree(AnonymousUser(), chapter)
    assert services.can_view_tree(_in_group(_member(other_chapter), "natoff"), chapter)
    assert services.can_view_tree(_member(other_chapter, is_superuser=True), chapter)

    director = _member(other_chapter)
    chapter.region.directors.add(director)
    assert services.can_view_tree(director, chapter)


def test_viewing_as_a_member_limits_a_national_officer_to_their_chapter(chapter, other_chapter):
    natoff = _in_group(_member(other_chapter), "natoff")
    chapter.region.directors.add(natoff)
    UserAlter.objects.create(user=natoff, chapter=other_chapter, hide_natoff=True)

    assert not services.can_view_tree(natoff, chapter)
    assert services.can_view_tree(natoff, other_chapter)
