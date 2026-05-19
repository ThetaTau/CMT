from django.urls import path

from . import dashboard, views  # noqa: F401 Used to add dash app

app_name = "chapters"
urlpatterns = [
    path("", views.ChapterListView.as_view(), name="list"),
    path("~redirect/", views.ChapterRedirectView.as_view(), name="redirect"),
    path("<slug:slug>/", views.ChapterDetailView.as_view(), name="detail"),
]
