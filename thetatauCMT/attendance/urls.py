from django.urls import path

from . import views

app_name = "attendance"

# Event-scoped attendance pages use a non-enumerable date + slug route (mirrors
# the events detail/update URLs) so the attendance for a given event cannot be
# reached by simply incrementing an integer id.
_EVENT = "~<int:year>/<int:month>/<int:day>/<slug:event_slug>/"

urlpatterns = [
    path("guest-autocomplete/", views.GuestMemberAutocompleteView.as_view(), name="guest-autocomplete"),
    path(_EVENT, views.AttendanceRosterView.as_view(), name="roster"),
    path(_EVENT + "save/", views.AttendanceBulkSaveView.as_view(), name="save"),
    path(_EVENT + "update/", views.AttendanceBulkUpdateView.as_view(), name="bulk_update"),
    path(_EVENT + "rollup/", views.AttendanceRollupView.as_view(), name="rollup"),
    path(_EVENT + "guest/", views.AttendanceGuestAddView.as_view(), name="guest_add"),
]
