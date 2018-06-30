from django.conf.urls import url

from . import views

app_name = 'events'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.EventListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^~redirect/$',
        view=views.EventRedirectView.as_view(),
        name='redirect'
    ),
    url(
        regex=r'^~update/$',
        view=views.EventUpdateView.as_view(),
        name='update'
    ),
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/$',
        view=views.EventDetailView.as_view(),
        name='detail'
    ),
]
