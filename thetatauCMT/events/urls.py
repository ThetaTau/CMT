from django.conf.urls import url

from . import views

app_name = "events"
urlpatterns = [
    url(regex=r"^$", view=views.EventListView.as_view(), name="list"),
    url(regex=r"^add/$", view=views.EventCreateView.as_view(), name="add"),
    url(regex=r"^copy/(?P<pk>\d+)/$", view=views.EventCopyView.as_view(), name="copy"),
    url(regex=r"^redirect/$", view=views.EventRedirectView.as_view(), name="redirect"),
    url(
        regex=r"^update/(?P<pk>\d+)/$",
        view=views.EventUpdateView.as_view(),
        name="update",
    ),
    url(
        regex=r"^~(?P<year>d{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<slug>[-w]+)/$",
        view=views.EventDetailView.as_view(),
        name="detail",
    ),
]
