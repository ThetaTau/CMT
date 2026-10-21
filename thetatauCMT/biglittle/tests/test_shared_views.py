import json

import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import UserAlter
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


@pytest.fixture
def other_chapter():
    return ChapterFactory(name="beta")


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _search(client, **params):
    if "forward" in params:
        params["forward"] = json.dumps(params["forward"])
    response = client.get(reverse("biglittle:member-autocomplete"), params)
    assert response.status_code == 200
    return {int(row["id"]): row["text"] for row in response.json()["results"]}


# ---------------------------------------------------------------------------
# Member picker
# ---------------------------------------------------------------------------
def test_picker_requires_sign_in(client):
    response = client.get(reverse("biglittle:member-autocomplete"))
    assert response.status_code == 302
    assert "login" in response.url


def test_picker_lists_initiated_members_of_the_current_chapter(auto_login_user, chapter, other_chapter):
    client, viewer = auto_login_user(user=_member(chapter))
    alumnus = _member(chapter, "alumni", name="Al Umnus", badge_number=42)
    _member(chapter, "pnm")
    _member(other_chapter)

    results = _search(client)

    assert set(results) == {viewer.pk, alumnus.pk}
    assert results[alumnus.pk] == "Al Umnus (#42)"


def test_picker_searches_names_and_badge_numbers(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter, name="Viewer Person", badge_number=1))
    ann = _member(chapter, name="Ann Rivera", badge_number=314)
    _member(chapter, name="Bob Stone", badge_number=27)

    assert set(_search(client, q="rivera")) == {ann.pk}
    assert set(_search(client, q="314")) == {ann.pk}
    assert set(_search(client, q="99999999999")) == set()


def test_picker_can_leave_out_the_viewer(auto_login_user, chapter):
    client, viewer = auto_login_user(user=_member(chapter))
    other = _member(chapter)

    assert set(_search(client, forward={"exclude_self": "true"})) == {other.pk}


def test_picker_follows_the_chapter_switcher_unless_asked_for_the_own_chapter(auto_login_user, chapter, other_chapter):
    client, natoff = auto_login_user(user=_member(chapter))
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    UserAlter.objects.create(user=natoff, chapter=other_chapter)
    elsewhere = _member(other_chapter)

    assert set(_search(client)) == {elsewhere.pk}
    assert set(_search(client, forward={"scope": "own"})) == {natoff.pk}


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------
def _pairing(chapter, **kwargs):
    little, big = _member(chapter), _member(chapter)
    return services.set_big(little, big, source=BigLittle.Source.MEMBER, **kwargs).link


def test_remove_only_accepts_post(auto_login_user, chapter):
    link = _pairing(chapter)
    client, _ = auto_login_user(user=link.little)

    response = client.get(reverse("biglittle:remove", args=[link.pk]))

    assert response.status_code == 405


def test_the_little_can_remove_their_big(auto_login_user, chapter):
    link = _pairing(chapter)
    client, _ = auto_login_user(user=link.little)

    response = client.post(reverse("biglittle:remove", args=[link.pk]), {"return_to": "myinfo"})

    assert response.url == reverse("users:detail") + "#big_little"
    assert not BigLittle.objects.filter(pk=link.pk).exists()
    assert _messages(response) == [f"Removed {link.big} as {link.little}'s Big."]


def test_a_bystander_cannot_remove_a_pairing(auto_login_user, chapter):
    link = _pairing(chapter)
    client, _ = auto_login_user(user=_member(chapter))

    response = client.post(reverse("biglittle:remove", args=[link.pk]))

    assert BigLittle.objects.filter(pk=link.pk).exists()
    assert _messages(response) == [f"You cannot remove {link.big} as {link.little}'s Big."]


def test_an_officer_removes_and_returns_to_the_list(auto_login_user, chapter):
    link = _pairing(chapter)
    client, officer = auto_login_user(user=_member(chapter))
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])

    response = client.post(reverse("biglittle:remove", args=[link.pk]))

    assert response.url == reverse("biglittle:list")
    assert not BigLittle.objects.filter(pk=link.pk).exists()


def test_an_ended_pairing_cannot_be_removed_here(auto_login_user, chapter):
    link = _pairing(chapter)
    services.set_big(link.little, _member(chapter), source=BigLittle.Source.MEMBER)
    client, _ = auto_login_user(user=link.little)

    response = client.post(reverse("biglittle:remove", args=[link.pk]))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Profile redirect
# ---------------------------------------------------------------------------
def test_profile_redirect_requires_sign_in(client, chapter):
    member = _member(chapter)
    response = client.get(reverse("biglittle:member", args=[member.pk]))
    assert "login" in response.url


def test_profile_redirect_goes_to_the_profile(auto_login_user, chapter):
    member = _member(chapter)
    client, _ = auto_login_user(user=_member(chapter))

    response = client.get(reverse("biglittle:member", args=[member.pk]))

    assert response.status_code == 302
    assert response.url == reverse("users:profile", kwargs={"username": member.username})
