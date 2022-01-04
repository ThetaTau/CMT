from django.conf.urls import url
from django.urls import path

from . import views

app_name = "submissions"
urlpatterns = [
    url(regex=r"^$", view=views.SubmissionListView.as_view(), name="list"),
    url(regex=r"^add/$", view=views.SubmissionCreateView.as_view(), name="add"),
    url(
        regex=r"^add/(?P<slug>[-\w]+)$",
        view=views.SubmissionCreateView.as_view(),
        name="add-direct",
    ),
    url(
        regex=r"^redirect/$",
        view=views.SubmissionRedirectView.as_view(),
        name="redirect",
    ),
    url(
        regex=r"^update/(?P<pk>\d+)/$",
        view=views.SubmissionUpdateView.as_view(),
        name="update",
    ),
    url(
        regex=r"^~(?P<year>d{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<slug>[-w]+)/$",
        view=views.SubmissionDetailView.as_view(),
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
