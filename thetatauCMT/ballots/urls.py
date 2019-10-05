from django.conf.urls import url

from . import views

app_name = 'ballots'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.BallotListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^create/$',
        view=views.BallotCreateView.as_view(),
        name='create'
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
        regex=r'^(?P<slug>[\w.@+-]+)/$',
        view=views.BallotDetailView.as_view(),
        name='detail'
    ),
]
