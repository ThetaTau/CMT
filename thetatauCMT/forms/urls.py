from django.conf.urls import url

from . import views

app_name = 'forms'
urlpatterns = [
    # url(
    #     regex=r'^$',
    #     view=views.FormListView.as_view(),
    #     name='list'
    # ),
    url(
        regex=r'^~initiation/$',
        view=views.InitiationView.as_view(),
        name='initiation'
    ),
    # url(
    #     regex=r'^~status-change/$',
    #     view=views.StatusChangeView.as_view(),
    #     name='redirect'
    # ),
    # url(
    #     regex=r'^~/$',
    #     view=views.FormUpdateView.as_view(),
    #     name='update'
    # ),
    # url(
    #     regex=r'^(?P<year>d{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<slug>[-w]+)/$',
    #     view=views.EventDetailView.as_view(),
    #     name='detail'
    # ),
]
