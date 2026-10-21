import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


def _profile(client, member):
    return client.get(reverse("users:profile", kwargs={"username": member.username}))


@pytest.fixture
def family(chapter):
    big, member, little = _member(chapter, name="Bo Big"), _member(chapter), _member(chapter, name="Lee Little")
    services.set_big(member, big, source=BigLittle.Source.MEMBER)
    services.set_big(little, member, source=BigLittle.Source.MEMBER)
    return {"big": big, "member": member, "little": little}


def test_the_member_sees_their_big_littles_and_tree_link(auto_login_user, chapter, family):
    member = family["member"]
    client, _ = auto_login_user(user=member)

    response = _profile(client, member)

    card = response.context["big_little"]
    assert (card["big"], card["littles"]) == (family["big"], [family["little"]])
    assert card["edit_url"] == reverse("users:detail") + "#big_little"
    assert card["tree_url"] == reverse("biglittle:tree", kwargs={"slug": chapter.slug}) + f"?member={member.pk}"
    content = response.content.decode()
    assert 'id="big-little-card"' in content
    assert "View in the family tree" in content


def test_a_replaced_big_is_not_shown(auto_login_user, chapter, family):
    member = family["member"]
    services.set_big(member, _member(chapter, name="New Big"), source=BigLittle.Source.MEMBER)
    client, _ = auto_login_user(user=member)

    content = _profile(client, member).content.decode()

    assert "New Big" in content
    assert "Bo Big" not in content


def test_an_initiated_member_without_pairings_is_prompted(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))

    content = _profile(client, member).content.decode()

    assert "You have not recorded your Big yet." in content


def test_a_pnm_gets_no_card(auto_login_user, chapter):
    client, pnm = auto_login_user(user=_member(chapter, "pnm"))

    response = _profile(client, pnm)

    assert not response.context["big_little"]["show"]
    assert 'id="big-little-card"' not in response.content.decode()


def test_chapter_members_see_the_card_without_an_edit_link(auto_login_user, chapter, family):
    client, _ = auto_login_user(user=_member(chapter))

    card = _profile(client, family["member"]).context["big_little"]

    assert card["show"]
    assert card["edit_url"] == ""


def test_an_officer_gets_the_record_page_as_the_edit_link(auto_login_user, chapter, family):
    client, officer = auto_login_user(user=_member(chapter))
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])

    card = _profile(client, family["member"]).context["big_little"]

    assert card["edit_url"] == reverse("biglittle:record") + f"?little={family['member'].pk}"


def test_members_of_other_chapters_do_not_see_the_card(auto_login_user, family):
    client, _ = auto_login_user(user=_member(ChapterFactory(name="beta")))

    response = _profile(client, family["member"])

    assert response.context["big_little"] is None
    assert "Bo Big" not in response.content.decode()
