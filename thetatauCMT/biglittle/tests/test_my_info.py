import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.forms import NOT_INITIATED_MESSAGE
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/users/myinfo/"


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


def _last_message(response):
    return [str(message) for message in get_messages(response.wsgi_request)][-1]


def test_the_url_is_edit_my_info():
    assert reverse("users:detail") == URL


def test_a_pnm_is_told_to_wait_for_initiation(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter, "pnm"))

    content = client.get(URL).content.decode()

    assert 'id="big_little"' in content
    assert "You can record your Big after you are initiated." in content
    assert 'value="big"' not in content


def test_a_pnm_cannot_post_a_big(auto_login_user, chapter):
    client, pnm = auto_login_user(user=_member(chapter, "pnm"))
    big = _member(chapter)

    response = client.post(URL, {"action": "big", "big": big.pk})

    assert response.status_code == 200
    assert NOT_INITIATED_MESSAGE in response.context["forms"]["big"].non_field_errors()
    assert services.current_big(pnm) is None


def test_a_member_records_then_changes_their_big(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    first, second = _member(chapter, name="Ann First"), _member(chapter, name="Ben Second")

    response = client.post(URL, {"action": "big", "big": first.pk})
    assert response.url == URL + "#big_little"
    assert _last_message(response) == "Recorded Ann First as your Big."
    link = BigLittle.objects.current().get(little=member)
    assert (link.big, link.source, link.created_by) == (first, BigLittle.Source.MEMBER, member)

    response = client.post(URL, {"action": "big", "big": second.pk})
    assert _last_message(response) == "Changed your Big from Ann First to Ben Second."
    assert services.current_big(member) == second

    response = client.post(URL, {"action": "big", "big": second.pk})
    assert _last_message(response) == "No changes were made."


def test_the_current_big_is_shown_and_preselected(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    big = _member(chapter, name="Bo Big")
    services.set_big(member, big, source=BigLittle.Source.MEMBER)

    response = client.get(URL)

    assert response.context["forms"]["big"].initial == {"big": big.pk}
    assert response.context["big_little"]["big_link"].big == big
    assert "Remove Bo Big as your Big?" in response.content.decode()


@pytest.mark.parametrize("pick", ["self", "other chapter", "pnm"])
def test_a_member_cannot_pick_an_ineligible_big(auto_login_user, chapter, pick):
    client, member = auto_login_user(user=_member(chapter))
    choice = {
        "self": member,
        "other chapter": _member(ChapterFactory(name="beta")),
        "pnm": _member(chapter, "pnm"),
    }[pick]

    response = client.post(URL, {"action": "big", "big": choice.pk})

    assert response.status_code == 200
    assert "big" in response.context["forms"]["big"].errors
    assert 'class="accordion-collapse collapse show" aria-labelledby="heading-big-little"' in (
        response.content.decode()
    )


def test_a_member_adds_a_little_who_has_no_big(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    little = _member(chapter, name="Lee Little")

    response = client.post(URL, {"action": "little", "little": little.pk})

    assert _last_message(response) == "Recorded Lee Little as your Little."
    link = BigLittle.objects.current().get(little=little)
    assert (link.big, link.created_by) == (member, member)


def test_a_member_cannot_take_over_someone_elses_little(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    little, big = _member(chapter, name="Lee Little"), _member(chapter, name="Bo Big")
    services.set_big(little, big, source=BigLittle.Source.OFFICER)

    response = client.post(URL, {"action": "little", "little": little.pk})

    assert response.context["forms"]["little"].errors["little"] == [
        "Lee Little already has a Big recorded (Bo Big). Ask a chapter officer to change it."
    ]
    assert services.current_big(little) == big


def test_a_member_cannot_add_their_own_big_as_a_little(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    big = _member(chapter)
    services.set_big(member, big, source=BigLittle.Source.MEMBER)

    response = client.post(URL, {"action": "little", "little": big.pk})

    assert "further down" in str(response.context["forms"]["little"].errors["little"])


def test_only_littles_the_member_recorded_can_be_removed_there(auto_login_user, chapter):
    client, member = auto_login_user(user=_member(chapter))
    own = _member(chapter, name="Own Little")
    officer_recorded = _member(chapter, name="Officer Little")
    services.set_big(own, member, actor=member, source=BigLittle.Source.MEMBER)
    services.set_big(officer_recorded, member, actor=_member(chapter), source=BigLittle.Source.OFFICER)

    rows = {row["link"].little.name: row["can_remove"] for row in client.get(URL).context["big_little"]["little_links"]}

    assert rows == {"Own Little": True, "Officer Little": False}
