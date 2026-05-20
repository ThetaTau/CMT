from django.urls import path

from . import views

app_name = "ballots"
urlpatterns = [
    path("list/", views.BallotListView.as_view(), name="list"),
    path("create/", views.BallotCreateView.as_view(), name="create"),
    path("copy/<int:pk>/", views.BallotCopyView.as_view(), name="copy"),
    path("redirect/", views.BallotRedirectView.as_view(), name="redirect"),
    path(
        "update/<int:pk>/",
        views.BallotUpdateView.as_view(),
        name="update",
    ),
    path(
        "details/<slug:slug>/",
        views.BallotDetailView.as_view(),
        name="detail",
    ),
    path("", views.BallotUserListView.as_view(), name="votelist"),
    path(
        "vote/<slug:slug>/",
        views.BallotCompleteCreateView.as_view(),
        name="vote",
    ),
]
