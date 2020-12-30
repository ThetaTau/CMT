import datetime
import pytest
import factory
from faker import Faker
from django.utils.text import slugify
from events.tests.factories import EventFactory
from events.models import Event
from scores.models import ScoreType

fake = Faker()


@pytest.mark.django_db
def test_event_factory(event_factory):
    assert event_factory == EventFactory


@pytest.mark.django_db
def test_event_instance(event):
    assert isinstance(event, Event)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event__name,event__date", [("Very Special event", datetime.date(2016, 10, 1))]
)
def test_event_str(event):
    assert str(event) == "Very Special event on 2016-10-01"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event__name,event__date", [("Very Special event", datetime.date(2016, 10, 1))]
)
def test_get_absolute_url(event):
    assert event.get_absolute_url() == (
        "events:detail",
        (),
        {
            "year": 2016,
            "month": "10",
            "day": "01",
            "slug": slugify("Very Special event"),
        },
    )


@pytest.mark.django_db
def test_chapter_events(chapter, event_factory):
    expected_events = event_factory.create_batch(10, chapter=chapter)
    actual_events = Event.chapter_events(chapter)
    assert set(list(actual_events)) == set(expected_events)


@pytest.mark.django_db
def test_calculate_meeting_attendance(
    chapter, event_factory, user_status_change_factory
):
    score_type = ScoreType.objects.get(name="Attendance at meetings")
    user_status_change_factory.create_batch(
        20,
        status="active",
        user__chapter=chapter,
        start=factory.Faker("date_between", start_date="-1y", end_date="today"),
        end=factory.Faker("date_between", start_date="today", end_date="+1y"),
    )
    event_factory.create_batch(
        10,
        calculate_score=False,
        type=score_type,
        members=5,
        chapter=chapter,
        date=factory.Faker("date_between", start_date="-15d", end_date="-5d"),
    )
    date = fake.date_between(start_date="-15d", end_date="-5d")
    actual_score = Event.calculate_meeting_attendance(chapter, date)
    # 10 events at 25% attendance each eval "15*MEETINGS"
    # Total score is 3.75 and individual event is 3.75/10=0.38
    assert actual_score == 0.39


@pytest.mark.django_db
def test_calculate_meeting_attendance_no_events(chapter, user_status_change_factory):
    user_status_change_factory.create_batch(
        20,
        status="active",
        user__chapter=chapter,
        start=factory.Faker("date_between", start_date="-1y", end_date="today"),
        end=factory.Faker("date_between", start_date="today", end_date="+1y"),
    )
    date = fake.date_between(start_date="-15d", end_date="-5d")
    actual_score = Event.calculate_meeting_attendance(chapter, date)
    # No events, should be 0 score
    assert actual_score == 0
