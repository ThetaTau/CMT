from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.EventListView.as_view(), name="list"),
    path("all/", views.EventListAllView.as_view(), name="list_all"),
    # WI-10 — cross-chapter public events calendar (any member).
    path("calendar/", views.EventCalendarView.as_view(), name="calendar"),
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
    # Converted to path with int and slug converters
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:slug>/",
        views.EventDetailView.as_view(),
        name="detail",
    ),
]
