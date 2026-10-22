import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.biglittle.views import FamilyTreeView
from thetatauCMT.chapters.tests.factories import ChapterFactory
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


def _pair(big, little):
    services.set_big(little, big, source=BigLittle.Source.OFFICER)


def _url(chapter, **params):
    url = reverse("biglittle:tree", kwargs={"slug": chapter.slug})
    return url + ("?" + "&".join(f"{key}={value}" for key, value in params.items()) if params else "")


def _drawn(response):
    """Member pks drawn as markers, from every person trace in the figure."""
    return {
        int(url.rstrip("/").rsplit("/", 1)[1])
        for trace in response.context["figure"]["data"]
        if trace.get("customdata")
        for url in trace["customdata"]
    }


@pytest.fixture
def two_families(chapter):
    founder, middle, youngest = _member(chapter), _member(chapter), _member(chapter)
    _pair(founder, middle)
    _pair(middle, youngest)
    other_big, other_little = _member(chapter), _member(chapter)
    _pair(other_big, other_little)
    return {"big": [founder, middle, youngest], "small": [other_big, other_little]}


def test_signed_out_visitors_are_sent_to_sign_in(client, chapter):
    response = client.get(_url(chapter))
    assert "login" in response.url


def test_unknown_chapters_are_not_found(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    assert client.get(reverse("biglittle:tree", kwargs={"slug": "no-such-chapter"})).status_code == 404


def test_a_chapter_member_sees_the_tree_and_its_text_version(auto_login_user, chapter, two_families):
    client, _ = auto_login_user(user=_member(chapter))

    response = client.get(_url(chapter))

    assert response.status_code == 200
    everyone = {member.pk for family in two_families.values() for member in family}
    assert _drawn(response) == everyone
    assert response.context["selected_family"] == "all"
    assert [node["person"].pk for node in response.context["outline"]] == [
        two_families["big"][0].pk,
        two_families["small"][0].pk,
    ]
    content = response.content.decode()
    assert 'id="family-tree-figure"' in content
    assert response.context["plotlyjs_url"] in content
    assert "Text version of the tree" in content


def test_members_of_other_chapters_are_sent_to_their_own_tree(auto_login_user, chapter, other_chapter):
    client, _ = auto_login_user(user=_member(other_chapter))

    response = client.get(_url(chapter))

    assert response.url == _url(other_chapter)
    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "Only members of alpha, its Regional Directors, National Officers and Admins can view its family tree."
    ]


def test_regional_directors_and_national_officers_can_view(auto_login_user, chapter, other_chapter):
    director = _member(other_chapter)
    chapter.region.directors.add(director)
    client, _ = auto_login_user(user=director)
    assert client.get(_url(chapter)).status_code == 200

    natoff = _member(other_chapter)
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    client, _ = auto_login_user(user=natoff)
    assert client.get(_url(chapter)).status_code == 200


@override_settings(DEBUG=True)  # lets the superuser past the 2FA setup middleware
def test_admins_can_view(auto_login_user, chapter, other_chapter):
    client, _ = auto_login_user(user=_member(other_chapter, is_superuser=True))
    assert client.get(_url(chapter)).status_code == 200


def test_member_focuses_and_highlights_their_family(auto_login_user, chapter, two_families):
    client, _ = auto_login_user(user=_member(chapter))
    youngest = two_families["big"][2]

    response = client.get(_url(chapter, member=youngest.pk))

    assert _drawn(response) == {member.pk for member in two_families["big"]}
    assert response.context["selected_family"] == str(two_families["big"][0].pk)
    assert response.context["figure"]["data"][-1]["name"] == "Selected member"


def test_a_member_without_pairings_gets_a_notice(auto_login_user, chapter, two_families):
    client, viewer = auto_login_user(user=_member(chapter))

    response = client.get(_url(chapter, member=viewer.pk))

    assert response.context["notice"] == "That member has no Big or Little recorded in this chapter's family tree."
    assert response.context["selected_family"] == "all"


def test_a_family_can_be_picked(auto_login_user, chapter, two_families):
    client, _ = auto_login_user(user=_member(chapter))

    response = client.get(_url(chapter, family=two_families["small"][0].pk))

    assert _drawn(response) == {member.pk for member in two_families["small"]}


def test_a_big_tree_opens_on_its_largest_family(auto_login_user, chapter, two_families, monkeypatch):
    monkeypatch.setattr(FamilyTreeView, "max_people", 3)
    client, _ = auto_login_user(user=_member(chapter))

    response = client.get(_url(chapter))
    assert _drawn(response) == {member.pk for member in two_families["big"]}
    assert response.context["notice"].startswith("This tree has 5 people in 2 families")

    response = client.get(_url(chapter, family="all"))
    assert len(_drawn(response)) == 5


def test_the_empty_state_and_the_missing_big_count(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    _member(chapter)

    response = client.get(_url(chapter))

    assert response.context["figure"] is None
    content = response.content.decode()
    assert "No Bigs have been recorded for alpha yet." in content
    assert "2 initiated members of alpha" in content
    assert "family_tree.js" not in content


def test_names_are_escaped_in_the_text_version(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    _pair(_member(chapter), _member(chapter, name="<b>Bold</b>"))

    content = client.get(_url(chapter)).content.decode()

    assert "<b>Bold</b>" not in content.split('id="family-tree-figure"')[1]
    assert "&lt;b&gt;Bold&lt;/b&gt;" in content


def test_queries_do_not_grow_with_the_tree(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    big = _member(chapter)
    _pair(big, _member(chapter))
    client.get(_url(chapter))
    with CaptureQueriesContext(connection) as small:
        client.get(_url(chapter))
    for _ in range(6):
        _pair(big, _member(chapter))
    with CaptureQueriesContext(connection) as large:
        client.get(_url(chapter))

    assert len(large) == len(small)


def test_the_chapter_page_links_the_tree_only_for_viewers_who_can_open_it(auto_login_user, chapter, other_chapter):
    button = f'<a href="{_url(chapter)}" class="btn btn-outline-primary btn-sm">'
    page = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    client, _ = auto_login_user(user=_member(chapter))
    assert button in client.get(page).content.decode()

    client, _ = auto_login_user(user=_member(other_chapter))
    assert button not in client.get(page).content.decode()


# ---------------------------------------------------------------------------
# Finding a member, and the zoom buttons
# ---------------------------------------------------------------------------
def _search_url(chapter):
    return reverse("biglittle:tree-members", kwargs={"slug": chapter.slug})


def _search(client, chapter, **params):
    response = client.get(_search_url(chapter), params)
    assert response.status_code == 200
    return {int(row["id"]): row["text"] for row in response.json()["results"]}


def test_the_search_offers_only_people_in_this_chapters_tree(auto_login_user, chapter, other_chapter, two_families):
    client, _ = auto_login_user(user=_member(chapter))
    _member(chapter)
    _pair(_member(other_chapter), _member(other_chapter))

    assert set(_search(client, chapter)) == {member.pk for family in two_families.values() for member in family}


def test_the_search_matches_names_and_badge_numbers(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    big = _member(chapter, name="Ann Rivera", badge_number=314)
    little = _member(chapter, name="Bo Stone", badge_number=27)
    _pair(big, little)

    assert _search(client, chapter, q="rivera") == {big.pk: "Ann Rivera (#314)"}
    assert set(_search(client, chapter, q="27")) == {little.pk}


def test_the_search_follows_who_may_view_the_tree(client, auto_login_user, chapter, other_chapter, two_families):
    assert "login" in client.get(_search_url(chapter)).url

    outsider, _ = auto_login_user(user=_member(other_chapter))
    assert _search(outsider, chapter) == {}
    assert outsider.get(reverse("biglittle:tree-members", kwargs={"slug": "no-such-chapter"})).json()["results"] == []

    director = _member(other_chapter)
    chapter.region.directors.add(director)
    director_client, _ = auto_login_user(user=director)
    assert len(_search(director_client, chapter)) == 5


def test_the_page_has_the_search_and_keeps_the_found_member_selected(auto_login_user, chapter, two_families):
    client, _ = auto_login_user(user=_member(chapter))
    youngest = two_families["big"][2]

    response = client.get(_url(chapter, member=youngest.pk))

    content = response.content.decode()
    assert 'id="member-search"' in content
    assert f'data-autocomplete-light-url="{_search_url(chapter)}"' in content
    assert f'<option value="{youngest.pk}" selected>' in content
    assert response.context["figure"]["layout"]["meta"]["focusX"] is not None
    for action in ("zoom-in", "zoom-out", "fit", "download"):
        assert f'data-tree-action="{action}"' in content
