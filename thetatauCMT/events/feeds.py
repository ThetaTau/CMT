"""iCalendar (``.ics``) subscription feeds (django-ical).

A member creates a :class:`~thetatauCMT.events.models.CalendarFeedSubscription`
and subscribes their calendar app to its private, token-scoped URL. The feed
only ever exposes cross-chapter-visible content (approved public events of the
selected chapters/regions + national events) and, optionally, the member's own
chapter to-dos (as VTODO items).

* **Private URLs** — the URL carries an unguessable ``uuid`` token, so the feed
  cannot be scraped by iterating ids.
* **Caching** — calendar apps poll frequently, so the view is wrapped with
  ``cache_page`` (keyed per token URL) to spare the database.
* **Date limits** — :meth:`items` only reaches back a few weeks (plus all future
  events) to keep the ``.ics`` payload small and fast to parse.
"""

import datetime

from django.urls import reverse
from django.utils import timezone as tz
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_page
from django_ical.views import ICalFeed

from .models import ICAL_FEED_PAST_WEEKS, CalendarFeedSubscription, Event

# Calendar clients poll often; 15 minutes is plenty fresh for event listings.
ICAL_CACHE_SECONDS = 60 * 15


class _FeedItem:
    """Lightweight wrapper so the feed methods can tell events from to-dos."""

    __slots__ = ("kind", "obj")

    def __init__(self, kind, obj):
        self.kind = kind
        self.obj = obj


def _event_items(start_date, queryset):
    """Wrap an event queryset (already date-filtered) as feed items."""
    return [_FeedItem("event", event) for event in queryset]


class _EventTodoFeedMixin:
    """Shared per-item rendering for event (VEVENT) and to-do (VTODO) items.

    ``django_ical`` emits a ``VTODO`` component whenever ``item_component_type``
    returns ``"todo"`` and a ``VEVENT`` otherwise.
    """

    def item_guid(self, item):
        return f"{item.kind}-{item.obj.pk}@cmt.thetatau.org"

    def item_title(self, item):
        if item.kind == "todo":
            return f"To-do: {item.obj.task.name}"
        return item.obj.name

    def item_description(self, item):
        if item.kind == "todo":
            return item.obj.task.description
        # The event description is rich text; .ics carries plain text only.
        return strip_tags(item.obj.description or "").strip()

    def item_component_type(self, item):
        return "todo" if item.kind == "todo" else None

    def item_start_datetime(self, item):
        # Timed events carry a real start/end; the rest stay all-day (DATE value).
        if item.kind != "event":
            return None
        return item.obj.start_datetime or item.obj.date

    def item_end_datetime(self, item):
        if item.kind != "event":
            return None
        end = item.obj.end_datetime
        if end is not None:
            # A zero-duration timed event still needs a non-empty span.
            start = item.obj.start_datetime
            return end if end > start else start + datetime.timedelta(hours=1)
        return item.obj.date + datetime.timedelta(days=1)

    def item_due(self, item):
        if item.kind == "todo":
            return item.obj.date
        return None

    def item_link(self, item):
        if item.kind == "todo":
            return reverse("tasks:list")
        return item.obj.get_absolute_url()


@method_decorator(cache_page(ICAL_CACHE_SECONDS), name="__call__")
class SubscriptionICalFeed(_EventTodoFeedMixin, ICalFeed):
    """Token-scoped iCal feed for a :class:`CalendarFeedSubscription`."""

    product_id = "-//Theta Tau CMT//Calendar Feed//EN"
    timezone = "UTC"

    def get_object(self, request, token):
        # DoesNotExist (an ObjectDoesNotExist) is turned into a 404 by ICalFeed.
        return CalendarFeedSubscription.objects.get(token=token)

    def title(self, obj):
        return obj.name

    def description(self, obj):
        return "Theta Tau events and to-dos you subscribed to via CMT."

    def items(self, obj):
        start = tz.localdate() - datetime.timedelta(weeks=ICAL_FEED_PAST_WEEKS)
        items = _event_items(start, obj.events_queryset(start))
        todos = obj.todos_queryset(start)
        if todos is not None:
            items += [_FeedItem("todo", todo) for todo in todos]
        return items


@method_decorator(cache_page(ICAL_CACHE_SECONDS), name="__call__")
class NationalICalFeed(_EventTodoFeedMixin, ICalFeed):
    """The single, always-available feed of all Theta Tau national events.

    No token or login is required — national events are organization-wide and
    public. Members who want a combined feed can instead add national events to
    a custom :class:`CalendarFeedSubscription`.
    """

    product_id = "-//Theta Tau CMT//National Events//EN"
    timezone = "UTC"
    title = "Theta Tau National Events"
    description = "All Theta Tau national (organization-wide) events."

    def items(self):
        start = tz.localdate() - datetime.timedelta(weeks=ICAL_FEED_PAST_WEEKS)
        national_events = Event.objects.national().filter(date__gte=start).order_by("date", "name")
        return _event_items(start, national_events)
