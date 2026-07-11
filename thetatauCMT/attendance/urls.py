from django.urls import path

from . import views

app_name = "attendance"

# Event-scoped attendance pages use a non-enumerable date + slug route (mirrors
# the events detail/update URLs) so the attendance for a given event cannot be
# reached by simply incrementing an integer id.
_EVENT = "~<int:year>/<int:month>/<int:day>/<slug:event_slug>/"

urlpatterns = [
    path("guest-autocomplete/", views.GuestMemberAutocompleteView.as_view(), name="guest-autocomplete"),
    # WI-7 — National event bulk upload + manual match queue (National Officers).
    path("national/upload/", views.NationalAttendanceUploadView.as_view(), name="national_upload"),
    path("national/queue/", views.MatchQueueListView.as_view(), name="match_queue"),
    path("national/queue/resolve/", views.MatchQueueResolveView.as_view(), name="match_queue_resolve"),
    path(
        "national/member-autocomplete/",
        views.NationalMemberAutocompleteView.as_view(),
        name="national-member-autocomplete",
    ),
    # WI-8 — Member self-service attendance logging at existing events.
    path("member-event-autocomplete/", views.MemberEventAutocomplete.as_view(), name="member-event-autocomplete"),
    path("member/<str:username>/add/", views.MemberAttendanceAddView.as_view(), name="member_add"),
    path(_EVENT, views.AttendanceRosterView.as_view(), name="roster"),
    path(_EVENT + "save/", views.AttendanceBulkSaveView.as_view(), name="save"),
    path(_EVENT + "update/", views.AttendanceBulkUpdateView.as_view(), name="bulk_update"),
    path(_EVENT + "rollup/", views.AttendanceRollupView.as_view(), name="rollup"),
    path(_EVENT + "guest/", views.AttendanceGuestAddView.as_view(), name="guest_add"),
]
