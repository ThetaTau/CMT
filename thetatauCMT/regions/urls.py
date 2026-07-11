from django.urls import path

from . import dashboard, views  # noqa: F401  dashboard import registers the DjangoDash app

app_name = "regions"
urlpatterns = [
    path("", views.RegionListView.as_view(), name="list"),
    path("~redirect/", views.RegionRedirectView.as_view(), name="redirect"),
    # WI-9 — events + attendance dashboard. Must precede the "<slug:slug>/"
    # catch-all below, otherwise "event-attendance" is swallowed as a region slug.
    path("event-attendance/", views.EventAttendanceDashboardView.as_view(), name="event_attendance"),
    path("<slug:slug>/", views.RegionDetailView.as_view(), name="detail"),
    path("<slug:slug>/officers/", views.RegionOfficerView.as_view(), name="officers"),
    path("<slug:slug>/advisors/", views.RegionAdvisorView.as_view(), name="advisors"),
    path("<slug:slug>/tasks/", views.RegionTaskView.as_view(), name="tasks"),
]
