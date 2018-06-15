from django.conf.urls import url

from . import views

app_name = 'regions'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.RegionListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^~redirect/$',
        view=views.RegionRedirectView.as_view(),
        name='redirect'
    ),
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/$',
        view=views.RegionDetailView.as_view(),
        name='detail'
    ),
]
