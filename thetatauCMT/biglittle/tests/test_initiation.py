from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.urls import reverse

from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.models import Initiation
from thetatauCMT.forms.tests.factories import BadgeFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


def _member(chapter, status="active", **kwargs):
    return UserFactory(chapter=chapter, current_status=status, **kwargs)


@pytest.fixture
def officer_client(auto_login_user, chapter):
    client, officer = auto_login_user(user=_member(chapter, badge_number=100))
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])
    return client, officer


def _select_for_initiation(client, pnms):
    session = client.session
    session["init-selection"] = {"Initiate": [pnm.pk for pnm in pnms], "Depledge": [], "Defer": [], "Roll": []}
    session.save()


def _payload(chapter, pnms, bigs):
    badge = BadgeFactory()
    next_badge = chapter.next_badge_number()
    data = {
        "chapter": chapter.name,
        "initiates-TOTAL_FORMS": str(len(pnms)),
        "initiates-INITIAL_FORMS": str(len(pnms)),
        "initiates-MIN_NUM_FORMS": "0",
        "initiates-MAX_NUM_FORMS": "1000",
        "depledges-TOTAL_FORMS": "0",
        "depledges-INITIAL_FORMS": "0",
        "depledges-MIN_NUM_FORMS": "0",
        "depledges-MAX_NUM_FORMS": "1000",
    }
    for index, big in enumerate(bigs):
        prefix = f"initiates-{index}-"
        data.update(
            {
                f"{prefix}date": "2020-02-01",
                f"{prefix}date_graduation": "2024-05-01",
                f"{prefix}roll": str(next_badge + index),
                f"{prefix}gpa": "3.5",
                f"{prefix}test_a": "90",
                f"{prefix}test_b": "90",
                f"{prefix}badge": str(badge.pk),
                f"{prefix}big": str(big.pk) if big else "",
            }
        )
    return data


def _pnms(chapter, count):
    pnms = [UserFactory(chapter=chapter, badge_number=2_000_001 + index) for index in range(count)]
    for pnm in pnms:
        # Chapter.pledges() reads status history, not just current_status.
        pnm.set_current_status(status="pnm")
    return pnms


def test_the_report_shows_a_big_picker(officer_client, chapter):
    client, _ = officer_client
    _select_for_initiation(client, _pnms(chapter, 1))

    response = client.get(reverse("forms:initiation"))

    content = response.content.decode()
    assert '<th style="width: 20%">Big</th>' in content
    assert reverse("biglittle:member-autocomplete") in content
    assert 'aria-label="Big"' in content


def test_initiating_with_a_big_records_the_pairing(officer_client, chapter):
    client, officer = officer_client
    pnm = _pnms(chapter, 1)[0]
    big = _member(chapter, badge_number=101)
    _select_for_initiation(client, [pnm])

    response = client.post(reverse("forms:initiation"), _payload(chapter, [pnm], [big]))

    assert response.status_code == 302
    link = BigLittle.objects.current().get(little=pnm)
    assert (link.big, link.chapter, link.source, link.created_by) == (
        big,
        chapter,
        BigLittle.Source.INITIATION,
        officer,
    )


def test_twins_can_share_a_big(officer_client, chapter):
    client, _ = officer_client
    twins = _pnms(chapter, 2)
    big = _member(chapter, badge_number=101)
    _select_for_initiation(client, twins)

    client.post(reverse("forms:initiation"), _payload(chapter, twins, [big, big]))

    assert set(big.links_as_big.current().values_list("little", flat=True)) == {twin.pk for twin in twins}


@pytest.mark.parametrize("big_kind", ["other chapter", "pnm"])
def test_a_big_who_cannot_be_picked_stops_the_report(officer_client, chapter, big_kind):
    client, _ = officer_client
    pnms = _pnms(chapter, 2)
    big = _member(ChapterFactory(name="beta")) if big_kind == "other chapter" else pnms[1]
    _select_for_initiation(client, pnms[:1])

    response = client.post(reverse("forms:initiation"), _payload(chapter, pnms[:1], [big]))

    assert response.status_code == 200
    assert not Initiation.objects.exists()
    assert not BigLittle.objects.exists()


def test_leaving_the_big_blank_initiates_as_before(officer_client, chapter):
    client, _ = officer_client
    pnm = _pnms(chapter, 1)[0]
    _select_for_initiation(client, [pnm])

    response = client.post(reverse("forms:initiation"), _payload(chapter, [pnm], [None]))

    assert response.status_code == 302
    assert Initiation.objects.filter(user=pnm).exists()
    assert not BigLittle.objects.exists()


def test_a_skipped_duplicate_initiation_records_no_big(officer_client, chapter):
    client, _ = officer_client
    pnm = _pnms(chapter, 1)[0]
    big = _member(chapter, badge_number=101)
    _select_for_initiation(client, [pnm])

    with mock.patch(
        "thetatauCMT.forms.models.Initiation.save",
        side_effect=IntegrityError("duplicate key value violates unique constraint"),
    ):
        response = client.post(reverse("forms:initiation"), _payload(chapter, [pnm], [big]))

    assert response.status_code == 302
    assert not BigLittle.objects.exists()
