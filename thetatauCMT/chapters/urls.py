from django.urls import path

from . import dashboard, views  # noqa: F401 Used to add dash app

app_name = "chapters"
urlpatterns = [
    path("", views.ChapterListView.as_view(), name="list"),
    path("~redirect/", views.ChapterRedirectView.as_view(), name="redirect"),
    path("activity/", views.ChapterActivityRedirectView.as_view(), name="activity_redirect"),
    path(
        "<slug:slug>/activity/",
        views.ChapterActivityView.as_view(),
        name="activity",
    ),
    path("audit/", views.ChapterAuditRedirectView.as_view(), name="audit_redirect"),
    path(
        "<slug:slug>/audit/",
        views.ChapterAuditView.as_view(),
        name="audit",
    ),
    path("<slug:slug>/", views.ChapterDetailView.as_view(), name="detail"),
]
