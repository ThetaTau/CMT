from django.urls import path

from . import views

app_name = "scores"
urlpatterns = [
    path("", views.ScoreListView.as_view(), name="list"),
    path("chapters/", views.ChapterScoreListView.as_view(), name="chapterlist"),
    path("~redirect/", views.ScoreRedirectView.as_view(), name="redirect"),
    path("<slug:slug>/", views.ScoreDetailView.as_view(), name="detail"),
]
