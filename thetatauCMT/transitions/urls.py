from django.urls import path

from . import views

app_name = "transitions"
urlpatterns = [
    path("", views.TransitionsListView.as_view(), name="list"),
    path("<int:pk>/compose/", views.ComposeReportView.as_view(), name="compose"),
    path("<int:pk>/close-vacant/", views.CloseNAVacantView.as_view(), name="close-vacant"),
    path("attachments/<int:pk>/delete/", views.AttachmentDeleteView.as_view(), name="attachment-delete"),
    path(
        "tag-autocomplete/",
        views.TransitionTagAutocomplete.as_view(create_field="name"),
        name="tag-autocomplete",
    ),
    path("packet/<int:chapter_pk>/<str:position_key>/", views.HandoffPacketView.as_view(), name="packet"),
    path("reports/<int:pk>/acknowledge/", views.AcknowledgeReportView.as_view(), name="acknowledge"),
    path("dashboard/chapter/<int:chapter_pk>/", views.ReportSearchView.as_view(), name="chapter-dashboard"),
    path("dashboard/rates/", views.ComplianceRatesView.as_view(), name="rates-dashboard"),
    path("search/", views.ReportSearchView.as_view(), name="search"),
    path("trends/", views.TrendView.as_view(), name="trends"),
]
