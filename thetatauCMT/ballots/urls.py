from django.conf.urls import url

from . import views

app_name = 'events'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.BallotListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^add/$',
        view=views.BallotCreateView.as_view(),
        name='add'
    ),
    url(
        regex=r'^copy/(?P<pk>\d+)/$',
        view=views.BallotCopyView.as_view(),
        name='copy'
    ),
    url(
        regex=r'^redirect/$',
        view=views.BallotRedirectView.as_view(),
        name='redirect'
    ),
    url(
        regex=r'^update/(?P<pk>\d+)/$',
        view=views.BallotUpdateView.as_view(),
        name='update'
    ),
    url(
        regex=r'^~(?P<year>d{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<slug>[-w]+)/$',
        view=views.BallotDetailView.as_view(),
        name='detail'
    ),
]
