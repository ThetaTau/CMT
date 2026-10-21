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

NME = "pledge/new member educator"


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


@pytest.fixture
def other_chapter():
    return ChapterFactory(name="beta")


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


def _officer(chapter):
    officer = _member(chapter)
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])
    return officer


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _rows(response):
    return [row.record for row in response.context["table"].rows]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def test_a_member_reads_the_list_without_edit_buttons(auto_login_user, chapter, other_chapter):
    client, viewer = auto_login_user(user=_member(chapter))
    little, big = _member(chapter), _member(chapter, name="Bo Big")
    services.set_big(little, big, source=BigLittle.Source.MEMBER)
    _member(chapter, "pnm")
    _member(other_chapter)

    response = client.get(reverse("biglittle:list"))

    assert response.status_code == 200
    rows = {record.pk: record for record in _rows(response)}
    assert set(rows) == {viewer.pk, little.pk, big.pk}
    assert rows[little.pk].big_name == "Bo Big"
    assert rows[big.pk].little_count == 1
    assert "actions" not in [column.name for column in response.context["table"].columns]
    assert not response.context["can_manage"]


@pytest.mark.parametrize("make_manager", [_officer, lambda chapter: _member(chapter, current_roles=[NME])])
def test_officers_and_the_new_member_educator_get_the_edit_buttons(auto_login_user, chapter, make_manager):
    client, _ = auto_login_user(user=make_manager(chapter))

    response = client.get(reverse("biglittle:list"))

    assert response.context["can_manage"]
    assert "actions" in [column.name for column in response.context["table"].columns]
    assert reverse("biglittle:record") in response.content.decode()


def test_the_list_filters_by_big_and_status(auto_login_user, chapter):
    client, viewer = auto_login_user(user=_member(chapter))
    little, big = _member(chapter), _member(chapter, "alumni")
    services.set_big(little, big, source=BigLittle.Source.MEMBER)

    assert {r.pk for r in _rows(client.get(reverse("biglittle:list"), {"big": "yes"}))} == {little.pk}
    assert {r.pk for r in _rows(client.get(reverse("biglittle:list"), {"big": "no"}))} == {viewer.pk, big.pk}
    assert {r.pk for r in _rows(client.get(reverse("biglittle:list"), {"status": "alumni"}))} == {big.pk}


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------
def test_a_plain_member_cannot_open_or_post_the_record_page(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter))
    little, big = _member(chapter), _member(chapter)
    url = reverse("biglittle:record")

    response = client.get(url)
    assert response.url == reverse("biglittle:list")
    assert _messages(response) == [
        "Only chapter officers and the New Member Educator can record Bigs and Littles for the whole chapter."
    ]

    client.post(url, {"little": little.pk, "big": big.pk})
    assert not BigLittle.objects.exists()


def test_recording_reports_created_changed_and_unchanged(auto_login_user, chapter):
    client, officer = auto_login_user(user=_officer(chapter))
    little = _member(chapter, name="Lee Little")
    first, second = _member(chapter, name="Ann First"), _member(chapter, name="Ben Second")
    url = reverse("biglittle:record")

    response = client.post(url, {"little": little.pk, "big": first.pk})
    assert response.url == reverse("biglittle:list")
    assert _messages(response) == ["Recorded Ann First as Lee Little's Big."]
    link = BigLittle.objects.current().get(little=little)
    assert (link.source, link.created_by) == (BigLittle.Source.OFFICER, officer)

    response = client.post(url, {"little": little.pk, "big": second.pk})
    # Messages pile up because the redirects are not followed, so check the newest.
    assert _messages(response)[-1] == "Changed Lee Little's Big from Ann First to Ben Second."

    response = client.post(url, {"little": little.pk, "big": second.pk})
    assert _messages(response)[-1] == "No change: Ben Second was already Lee Little's Big."


def test_the_record_page_prefills_the_little_and_their_big(auto_login_user, chapter):
    client, _ = auto_login_user(user=_officer(chapter))
    little, big = _member(chapter), _member(chapter)
    services.set_big(little, big, source=BigLittle.Source.MEMBER)

    response = client.get(reverse("biglittle:record"), {"little": little.pk})

    assert response.context["form"].initial == {"little": little.pk, "big": big.pk}


def test_the_record_page_refuses_a_loop_and_other_chapters(auto_login_user, chapter, other_chapter):
    client, _ = auto_login_user(user=_officer(chapter))
    big, little = _member(chapter), _member(chapter)
    services.set_big(little, big, source=BigLittle.Source.MEMBER)

    response = client.post(reverse("biglittle:record"), {"little": big.pk, "big": little.pk})
    assert response.status_code == 200
    assert "further down" in str(response.context["form"].errors["big"])

    response = client.post(reverse("biglittle:record"), {"little": little.pk, "big": _member(other_chapter).pk})
    assert "big" in response.context["form"].errors
    assert services.current_big(little) == big


def test_a_national_officer_records_for_the_chapter_they_switched_to(auto_login_user, chapter, other_chapter):
    client, natoff = auto_login_user(user=_member(chapter))
    natoff.groups.add(Group.objects.get_or_create(name="natoff")[0])
    UserAlter.objects.create(user=natoff, chapter=other_chapter)
    little, big = _member(other_chapter), _member(other_chapter)

    client.post(reverse("biglittle:record"), {"little": little.pk, "big": big.pk})

    assert services.current_big(little) == big
