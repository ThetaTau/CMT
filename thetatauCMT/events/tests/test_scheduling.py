"""Tests for the future-event scheduling fields on the event form.

Covers the create/update form gaining a start time + time zone, a rich-text
description, an external info link, and dropping the requirement to fill in the
outcome counts (members / PNMs / alumni / guests / funds raised) that are not
knowable until after the event happens.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.choices import US_UK_TIME_ZONES
from thetatauCMT.events.forms import EventForm
from thetatauCMT.events.models import Event
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType

from .test_views import _evt_score_type, _make_chapter_officer


def _future_date(days=30):
    return datetime.date.today() + datetime.timedelta(days=days)


def _create_post_data(score_type, **overrides):
    data = {
        "name": "Fall Kickoff",
        "date": _future_date().isoformat(),
        "type": score_type.pk,
        "description": "<p>Meet at the <strong>union</strong>.</p>",
        "duration": 2,
        "miles": 0,
        # picture formset management form (default modelformset prefix "form")
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return data


# ===========================================================================
# Model helpers
# ===========================================================================


@pytest.mark.django_db
def test_start_datetime_uses_the_events_own_time_zone(event_factory):
    event = event_factory.create(
        date=datetime.date(2026, 9, 15),
        start_time=datetime.time(18, 30),
        time_zone="America/New_York",
    )
    assert event.start_datetime == datetime.datetime(2026, 9, 15, 18, 30, tzinfo=ZoneInfo("America/New_York"))
    assert event.end_datetime == event.start_datetime + datetime.timedelta(hours=event.duration)


@pytest.mark.django_db
def test_start_datetime_is_none_for_an_all_day_event(event_factory):
    event = event_factory.create(date=datetime.date(2026, 9, 15), start_time=None)
    assert event.start_datetime is None
    assert event.end_datetime is None


@pytest.mark.django_db
def test_blank_time_zone_falls_back_to_the_site_zone(event_factory, settings):
    event = event_factory.create(time_zone="")
    assert event.effective_time_zone == ZoneInfo(settings.TIME_ZONE)


@pytest.mark.django_db
def test_unknown_time_zone_is_rejected():
    event = Event(name="Bad Zone", date=_future_date(), time_zone="Not/AZone")
    with pytest.raises(ValidationError) as excinfo:
        event.clean()
    assert "time_zone" in excinfo.value.message_dict


def test_is_future_only_for_dates_after_today():
    assert Event(date=_future_date()).is_future is True
    assert Event(date=datetime.date.today()).is_future is False
    assert Event(date=_future_date(-1)).is_future is False


# ===========================================================================
# Form behaviour
# ===========================================================================


@pytest.mark.django_db
def test_form_defaults_the_time_zone_to_the_site_zone(settings):
    form = EventForm()
    assert form.initial["time_zone"] == settings.TIME_ZONE


@pytest.mark.django_db
def test_time_zone_is_a_plain_select_of_us_and_uk_zones():
    form = EventForm()
    field = form.fields["time_zone"]
    assert isinstance(field.widget, forms.Select)
    assert not isinstance(field.widget, forms.SelectMultiple)
    values = [value for value, _label in field.choices]
    assert values[0] == ""  # site default
    assert "America/New_York" in values
    assert "Europe/London" in values
    # Nothing outside the US / UK, and short enough for a plain dropdown.
    assert "Asia/Tokyo" not in values
    assert len(values) == len(US_UK_TIME_ZONES) + 1


@pytest.mark.django_db
def test_outcome_fields_are_optional_and_tagged():
    form = EventForm()
    for name in EventForm.OUTCOME_FIELDS:
        assert form.fields[name].required is False
        assert form.fields[name].widget.attrs["data-event-outcome"] == "1"


@pytest.mark.django_db
def test_form_accepts_a_twelve_hour_start_time():
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    form = EventForm(
        data={
            "name": "Evening Social",
            "date": _future_date().isoformat(),
            "start_time": "6:30 PM",
            "time_zone": "America/Chicago",
            "type": score_type.pk,
            "description": "Social",
            "duration": 2,
            "miles": 0,
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["start_time"] == datetime.time(18, 30)
    assert form.cleaned_data["time_zone"] == "America/Chicago"


@pytest.mark.django_db
def test_form_rejects_an_unknown_time_zone():
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    form = EventForm(
        data={
            "name": "Bad Zone",
            "date": _future_date().isoformat(),
            "time_zone": "Middle/Earth",
            "type": score_type.pk,
            "description": "Social",
            "duration": 1,
            "miles": 0,
        }
    )
    assert form.is_valid() is False
    assert "time_zone" in form.errors


# ===========================================================================
# Create view
# ===========================================================================


@pytest.mark.django_db
def test_create_future_event_without_outcome_counts(auto_login_user):
    """A future event needs no members / PNMs / alumni / guests / raised."""
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    response = client.post(
        reverse("events:add"),
        _create_post_data(
            score_type,
            start_time="7:00 PM",
            time_zone="America/New_York",
            external_link="https://example.com/rsvp",
        ),
    )
    assert response.status_code == 302
    event = Event.objects.get(name="Fall Kickoff")
    assert event.start_time == datetime.time(19, 0)
    assert event.time_zone == "America/New_York"
    assert event.external_link == "https://example.com/rsvp"
    assert event.description == "<p>Meet at the <strong>union</strong>.</p>"
    assert (event.members, event.pledges, event.alumni, event.guests) == (0, 0, 0, 0)
    assert event.raised == 0


@pytest.mark.django_db
def test_create_event_defaults_to_all_day_without_a_start_time(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    response = client.post(reverse("events:add"), _create_post_data(score_type))
    assert response.status_code == 302
    event = Event.objects.get(name="Fall Kickoff")
    assert event.start_time is None
    assert event.start_datetime is None


# ===========================================================================
# Update view + detail rendering
# ===========================================================================


@pytest.mark.django_db
def test_update_view_saves_time_and_link(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").exclude(slug="article").first()
    if score_type is None:
        pytest.skip("No non-article Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type, date=_future_date())
    response = client.post(
        event.get_update_url(),
        {
            "name": event.name,
            "date": event.date.isoformat(),
            "start_time": "9:15 AM",
            "time_zone": "America/Los_Angeles",
            "type": score_type.pk,
            "description": "<p>Details</p>",
            "external_link": "https://example.com/info",
            "duration": event.duration,
            "miles": event.miles,
        },
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.start_time == datetime.time(9, 15)
    assert event.time_zone == "America/Los_Angeles"
    assert event.external_link == "https://example.com/info"


@pytest.mark.django_db
def test_detail_page_shows_time_and_link(auto_login_user):
    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(
        chapter=user.chapter,
        type=score_type,
        date=_future_date(),
        start_time=datetime.time(19, 0),
        time_zone="America/New_York",
        external_link="https://example.com/rsvp",
        description="<p>Bring a <em>friend</em>.</p>",
    )
    response = client.get(event.get_absolute_url())
    content = response.content.decode()
    assert "7:00 PM" in content
    assert "America/New_York" in content
    assert "https://example.com/rsvp" in content
    # Rich text renders as markup, not escaped source.
    assert "Bring a <em>friend</em>." in content


@pytest.mark.django_db
def test_detail_page_strips_script_from_the_description(auto_login_user):
    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(
        chapter=user.chapter,
        type=score_type,
        description="<p>ok</p><script>alert(1)</script>",
    )
    content = client.get(event.get_absolute_url()).content.decode()
    assert "<script>alert(1)</script>" not in content
    assert "<p>ok</p>" in content
