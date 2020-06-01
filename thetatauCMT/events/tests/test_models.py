import datetime
import pytest
from django.utils.text import slugify
from events.tests.factories import EventFactory
from events.models import Event


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
    assert str(event) == f"Very Special event on 2016-10-01"


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
