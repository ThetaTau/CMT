from django.urls import path

from . import views

app_name = "transitions"
# NOTE (2026-09): compose/close-vacant/attachment-delete/acknowledge deliberately
# use <uuid:pk> rather than <int:pk>. The URL kwarg is still spelled "pk" (so
# `reverse(..., kwargs={"pk": ...})` call sites didn't all need renaming), but the
# value is each model's own `public_id` UUID field, not the real integer database
# id -- a sequential integer in a URL lets a bad actor enumerate every obligation/
# report/attachment (incrementing /1/compose/, /2/compose/, ...) to probe for
# existence even though the views themselves are access-controlled; the views look
# these objects up by `public_id=`, never by the real `pk=`. `chapter_pk` below is
# untouched -- Chapter's own pk is shared across the entire codebase, well beyond
# this app's scope.
urlpatterns = [
    path("", views.TransitionsListView.as_view(), name="list"),
    path("<uuid:pk>/compose/", views.ComposeReportView.as_view(), name="compose"),
    path("<uuid:pk>/close-vacant/", views.CloseNAVacantView.as_view(), name="close-vacant"),
    path("attachments/<uuid:pk>/delete/", views.AttachmentDeleteView.as_view(), name="attachment-delete"),
    path(
        "tag-autocomplete/",
        views.TransitionTagAutocomplete.as_view(create_field="name"),
        name="tag-autocomplete",
    ),
    path("packet/<int:chapter_pk>/<str:position_key>/", views.HandoffPacketView.as_view(), name="packet"),
    path("reports/<uuid:pk>/acknowledge/", views.AcknowledgeReportView.as_view(), name="acknowledge"),
    path("dashboard/chapter/<int:chapter_pk>/", views.ReportSearchView.as_view(), name="chapter-dashboard"),
    path("dashboard/rates/", views.ComplianceRatesView.as_view(), name="rates-dashboard"),
    path("search/", views.ReportSearchView.as_view(), name="search"),
    path("trends/", views.TrendView.as_view(), name="trends"),
]
