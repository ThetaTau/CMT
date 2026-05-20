from django.urls import path

from . import views

app_name = "submissions"
urlpatterns = [
    path("", views.SubmissionListView.as_view(), name="list"),
    path("add/", views.SubmissionCreateView.as_view(), name="add"),
    path("add/<slug:slug>", views.SubmissionCreateView.as_view(), name="add-direct"),
    path("redirect/", views.SubmissionRedirectView.as_view(), name="redirect"),
    path("update/<int:pk>/", views.SubmissionUpdateView.as_view(), name="update"),
    path(
        "~<int:year>/<int:month>/<int:day>/<slug:slug>/",
        views.SubmissionDetailView.as_view(),
        name="detail",
    ),
    path("gear", views.GearArticleFormView.as_view(), name="gear"),
    path("gearlist", views.GearArticleListView.as_view(), name="gearlist"),
    path(
        "gear-detail/<int:pk>",
        views.GearArticleDetailView.as_view(),
        name="gear_detail",
    ),
]
