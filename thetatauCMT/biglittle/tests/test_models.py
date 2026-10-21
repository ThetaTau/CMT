import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _pairing(big, little, **kwargs):
    return BigLittle.objects.create(big=big, little=little, chapter=little.chapter, **kwargs)


def test_a_little_has_at_most_one_current_big():
    little = UserFactory()
    _pairing(UserFactory(chapter=little.chapter), little)
    with pytest.raises(IntegrityError), transaction.atomic():
        _pairing(UserFactory(chapter=little.chapter), little)


def test_former_bigs_do_not_block_a_current_big():
    little = UserFactory()
    _pairing(UserFactory(chapter=little.chapter), little, ended=timezone.now())
    _pairing(UserFactory(chapter=little.chapter), little, ended=timezone.now())
    current = _pairing(UserFactory(chapter=little.chapter), little)

    assert list(BigLittle.objects.filter(little=little).current()) == [current]
    assert BigLittle.objects.filter(little=little).former().count() == 2


def test_nobody_is_their_own_big():
    member = UserFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        _pairing(member, member)


def test_a_big_can_have_twins():
    big = UserFactory()
    twins = [UserFactory(chapter=big.chapter), UserFactory(chapter=big.chapter)]
    for little in twins:
        _pairing(big, little)

    assert set(big.links_as_big.current().values_list("little", flat=True)) == {twin.pk for twin in twins}


def test_related_managers_split_current_and_former():
    little = UserFactory()
    old_big = UserFactory(chapter=little.chapter)
    new_big = UserFactory(chapter=little.chapter)
    former = _pairing(old_big, little, ended=timezone.now())
    current = _pairing(new_big, little)

    assert list(little.links_as_little.current()) == [current]
    assert list(little.links_as_little.former()) == [former]
    assert not old_big.links_as_big.current().exists()
    assert list(new_big.links_as_big.current()) == [current]


def test_is_current_and_str():
    little = UserFactory(name="Lee Little")
    big = UserFactory(chapter=little.chapter, name="Bo Big")
    pairing = _pairing(big, little)

    assert pairing.is_current
    assert str(pairing) == "Bo Big is the Big of Lee Little"
    pairing.ended = timezone.now()
    assert not pairing.is_current


def test_source_defaults_to_admin():
    little = UserFactory()
    pairing = _pairing(UserFactory(chapter=little.chapter), little)
    assert pairing.source == BigLittle.Source.ADMIN
