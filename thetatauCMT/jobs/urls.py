from django.urls import path

from . import views

app_name = "jobs"
urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("search/", views.JobSearchListView.as_view(), name="search"),
    path(
        "search/<int:pk>/",
        views.JobListView.as_view(),
        name="search_filter",
    ),
    path(
        "keyword-autocomplete/",
        views.KeywordAutocomplete.as_view(create_field="name"),
        name="keyword-autocomplete",
    ),
    path(
        "keyword-autocomplete-ro/",
        views.KeywordAutocomplete.as_view(),
        name="keyword-autocomplete-ro",
    ),
    path(
        "major-autocomplete/",
        views.MajorAutocomplete.as_view(create_field="name"),
        name="major-autocomplete",
    ),
    path("add/", views.JobCreateView.as_view(), name="add"),
    path(
        "add-search/",
        views.JobSearchCreateView.as_view(),
        name="add_search",
    ),
    path("copy/<int:pk>/", views.JobCopyView.as_view(), name="copy"),
    path("redirect/", views.JobRedirectView.as_view(), name="redirect"),
    path(
        "update/<int:pk>/",
        views.JobUpdateView.as_view(),
        name="update",
    ),
    path(
        "update-search/<int:pk>/",
        views.JobSearchUpdateView.as_view(),
        name="update_search",
    ),
    path(
        "report/<int:pk>/",
        views.JobReportView.as_view(),
        name="report",
    ),
    path(
        "approve/<int:pk>/",
        views.JobApproveView.as_view(),
        name="approve",
    ),
    path(
        "delete/<int:pk>/",
        views.JobDeleteView.as_view(),
        name="delete",
    ),
    path(
        "ban/<int:pk>/",
        views.JobBanUserView.as_view(),
        name="ban",
    ),
    path("<int:pk>/<slug:slug>/", views.JobDetailView.as_view(), name="detail"),
]
