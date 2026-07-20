from django.urls import path

from . import feeds, views

app_name = "events"
urlpatterns = [
    path("", views.EventListView.as_view(), name="list"),
    path("all/", views.EventListAllView.as_view(), name="list_all"),
    # WI-10 — cross-chapter public events calendar (any member).
    path("calendar/", views.EventCalendarView.as_view(), name="calendar"),
    # iCal subscription feeds (private, per-member UUID token URLs).
    path("ical/national/", feeds.NationalICalFeed(), name="ical_national"),
    path("ical/<uuid:token>/", feeds.SubscriptionICalFeed(), name="ical"),
    path("feeds/", views.CalendarFeedListView.as_view(), name="feeds"),
    path("feeds/tasks/", views.TaskFeedCreateView.as_view(), name="feed_tasks"),
    path("feeds/<int:pk>/edit/", views.CalendarFeedUpdateView.as_view(), name="feed_edit"),
    path(
        "feeds/subscribe-chapter/",
        views.ChapterFeedSubscribeView.as_view(),
        name="feed_subscribe_chapter",
    ),
    path("feeds/<int:pk>/delete/", views.CalendarFeedDeleteView.as_view(), name="feed_delete"),
    path(
        "chapter-feed-autocomplete/",
        views.ChapterFeedAutocomplete.as_view(),
        name="chapter-feed-autocomplete",
    ),
    path(
        "region-feed-autocomplete/",
        views.RegionFeedAutocomplete.as_view(),
        name="region-feed-autocomplete",
    ),
    path("pending/", views.EventPendingListView.as_view(), name="pending"),
    path("approve/<int:pk>/", views.EventApproveView.as_view(), name="approve"),
    path("reject/<int:pk>/", views.EventRejectView.as_view(), name="reject"),
    path("autocomplete/", views.EventAutocomplete.as_view(), name="event-autocomplete"),
    path("add/", views.EventCreateView.as_view(), name="add"),
    path("copy/<int:pk>/", views.EventCopyView.as_view(), name="copy"),
    path("redirect/", views.EventRedirectView.as_view(), name="redirect"),
    # Non-enumerable edit URL (date + slug), mirroring the detail URL so the
    # page cannot be reached by simply incrementing an integer id.
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:event_slug>/edit/",
        views.EventUpdateView.as_view(),
        name="update",
    ),
    # Non-enumerable soft-delete confirmation URL (date + slug).
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:event_slug>/delete/",
        views.EventDeleteView.as_view(),
        name="delete",
    ),
    # Converted to path with int and slug converters
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:slug>/",
        views.EventDetailView.as_view(),
        name="detail",
    ),
]
