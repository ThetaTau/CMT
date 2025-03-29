from django.conf.urls import url
from django.urls import path

from . import views

app_name = "jobs"
urlpatterns = [
    url(regex=r"^$", view=views.JobListView.as_view(), name="list"),
    url(regex=r"^search/$", view=views.JobSearchListView.as_view(), name="search"),
    url(
        r"^keyword-autocomplete/$",
        views.KeywordAutocomplete.as_view(create_field="name"),
        name="keyword-autocomplete",
    ),
    url(
        r"^keyword-autocomplete-ro/$",
        views.KeywordAutocomplete.as_view(),
        name="keyword-autocomplete-ro",
    ),
    url(
        r"^major-autocomplete/$",
        views.MajorAutocomplete.as_view(create_field="name"),
        name="major-autocomplete",
    ),
    url(regex=r"^add/$", view=views.JobCreateView.as_view(), name="add"),
    url(
        regex=r"^add-search/$",
        view=views.JobSearchCreateView.as_view(),
        name="add_search",
    ),
    url(regex=r"^copy/(?P<pk>\d+)/$", view=views.JobCopyView.as_view(), name="copy"),
    url(regex=r"^redirect/$", view=views.JobRedirectView.as_view(), name="redirect"),
    url(
        regex=r"^update/(?P<pk>\d+)/$",
        view=views.JobUpdateView.as_view(),
        name="update",
    ),
    url(
        regex=r"^update-search/(?P<pk>\d+)/$",
        view=views.JobSearchUpdateView.as_view(),
        name="update_search",
    ),
    path("<int:pk>/<slug:slug>/", view=views.JobDetailView.as_view(), name="detail"),
]
