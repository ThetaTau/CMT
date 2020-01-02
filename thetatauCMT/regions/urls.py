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
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/officers/$',
        view=views.RegionOfficerView.as_view(),
        name='officers'
    ),
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/advisors/$',
        view=views.RegionAdvisorView.as_view(),
        name='advisors'
    ),
    url(
        regex=r'^(?P<slug>[\w.@+-]+)/tasks/$',
        view=views.RegionTaskView.as_view(),
        name='tasks'
    ),
]
