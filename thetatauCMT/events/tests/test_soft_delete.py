"""Soft-delete tests for events.

Acceptance criteria covered by name:
    * a GET shows a confirmation page and does NOT delete (confirmation required)
    * a chapter officer of the event's chapter can soft-delete it
    * a regular member cannot soft-delete an event
    * an officer of a different chapter cannot soft-delete the event
    * a National Officer can soft-delete any event
    * a soft-deleted event is hidden from the default and reverse managers
    * a soft-deleted event is removed from scoring
    * a soft-deleted event can be restored
"""

import datetime

import pytest
from django.contrib.auth.models import Group
from django.db.models import Sum

from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.events.models import Event
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

GREEK = list(GREEK_ABR.values())
TODAY = datetime.date.today()


def _evt_type():
    return ScoreType.objects.filter(type="Evt").first()


def _event(chapter, name, date=TODAY, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_type(), date=date, name=name, **kwargs)


def _make_chapter_officer(user, client):
    """Chapter officer (officer group, definitely NOT natoff)."""
    officer, _ = Group.objects.get_or_create(name="officer")
    natoff, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(officer)
    user.groups.remove(natoff)
    natoff.user_set.remove(user)
    user.current_roles = ["scribe"]
    user.save(update_fields=["current_roles"])
    client.force_login(user)


def _make_natoff(user, client):
    natoff, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(natoff)
    client.force_login(user)


# ===========================================================================
# Confirmation + permission (the view)
# ===========================================================================


@pytest.mark.django_db
def test_get_shows_confirmation_and_does_not_delete(auto_login_user, chapter_factory):
    """a GET shows a confirmation page and does NOT delete (confirmation required)"""
    chapter = chapter_factory.create(name=GREEK[0])
    officer = UserFactory.create(chapter=chapter, name="Confirm Officer")
    client, _ = auto_login_user(user=officer)
    _make_chapter_officer(officer, client)
    event = _event(chapter, "Needs Confirm")

    response = client.get(event.get_delete_url())

    assert response.status_code == 200
    assert b"Confirm deletion" in response.content
    event.refresh_from_db()
    assert event.deleted is False


@pytest.mark.django_db
def test_chapter_officer_can_soft_delete_event(auto_login_user, chapter_factory):
    """a chapter officer of the event's chapter can soft-delete it"""
    chapter = chapter_factory.create(name=GREEK[0])
    officer = UserFactory.create(chapter=chapter, name="Del Officer")
    client, _ = auto_login_user(user=officer)
    _make_chapter_officer(officer, client)
    event = _event(chapter, "Officer Deletes")

    response = client.post(event.get_delete_url())

    assert response.status_code == 302
    assert not Event.objects.filter(pk=event.pk).exists()
    stored = Event.all_objects.get(pk=event.pk)
    assert stored.deleted is True
    assert stored.deleted_by_id == officer.pk


@pytest.mark.django_db
def test_regular_member_cannot_soft_delete(auto_login_user, chapter_factory):
    """a regular member cannot soft-delete an event"""
    chapter = chapter_factory.create(name=GREEK[0])
    event = _event(chapter, "Members Cannot Delete")
    client, _ = auto_login_user()  # plain member, no officer group

    response = client.post(event.get_delete_url())

    assert response.status_code == 302
    assert response.url == event.get_absolute_url()
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_officer_of_other_chapter_cannot_delete(auto_login_user, chapter_factory):
    """an officer of a different chapter cannot soft-delete the event"""
    chapter = chapter_factory.create(name=GREEK[0])
    other_chapter = chapter_factory.create(name=GREEK[1])
    event = _event(chapter, "Cross Chapter Guard")
    officer = UserFactory.create(chapter=other_chapter, name="Wrong Chapter Officer")
    client, _ = auto_login_user(user=officer)
    _make_chapter_officer(officer, client)

    response = client.post(event.get_delete_url())

    assert response.status_code == 302
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_national_officer_can_delete_event(auto_login_user, chapter_factory):
    """a National Officer can soft-delete any event"""
    chapter = chapter_factory.create(name=GREEK[0])
    event = _event(chapter, "Natoff Deletes")
    natoff = UserFactory.create(name="Nat Officer")
    client, _ = auto_login_user(user=natoff)
    _make_natoff(natoff, client)

    response = client.post(event.get_delete_url())

    assert response.status_code == 302
    assert not Event.objects.filter(pk=event.pk).exists()


# ===========================================================================
# Model behavior — removed from scoring and everywhere
# ===========================================================================


@pytest.mark.django_db
def test_soft_deleted_event_hidden_from_default_and_reverse_managers(chapter_factory):
    """a soft-deleted event is hidden from the default and reverse managers"""
    chapter = chapter_factory.create(name=GREEK[0])
    score_type = _evt_type()
    event = _event(chapter, "Vanishing Event")
    assert Event.objects.filter(pk=event.pk).exists()

    event.soft_delete(UserFactory.create(name="Deleter"))

    assert not Event.objects.filter(pk=event.pk).exists()
    assert Event.all_objects.filter(pk=event.pk).exists()
    # Reverse relations (chapter.events / type.events) also hide it.
    assert not chapter.events.filter(pk=event.pk).exists()
    assert not score_type.events.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_soft_delete_removes_event_from_scoring(chapter_factory):
    """a soft-deleted event is removed from scoring"""
    chapter = chapter_factory.create(name=GREEK[0])
    score_type = _evt_type()

    def chapter_total():
        return score_type.chapter_events(chapter).aggregate(total=Sum("score"))["total"] or 0

    before = chapter_total()
    keep = _event(chapter, "Keep Score")
    remove = _event(chapter, "Remove Score")
    Event.all_objects.filter(pk=keep.pk).update(score=5)
    Event.all_objects.filter(pk=remove.pk).update(score=7)
    assert chapter_total() == before + 12

    remove.refresh_from_db()
    remove.soft_delete(UserFactory.create(name="Score Deleter"))

    assert chapter_total() == before + 5  # the removed event's 7 points are gone


@pytest.mark.django_db
def test_soft_deleted_event_can_be_restored(chapter_factory):
    """a soft-deleted event can be restored"""
    chapter = chapter_factory.create(name=GREEK[0])
    event = _event(chapter, "Comeback Event")
    actor = UserFactory.create(name="Restorer")
    event.soft_delete(actor)
    assert not Event.objects.filter(pk=event.pk).exists()

    Event.all_objects.get(pk=event.pk).restore(actor)

    assert Event.objects.filter(pk=event.pk).exists()
