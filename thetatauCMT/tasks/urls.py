from django.conf.urls import url

from . import views

app_name = 'tasks'
urlpatterns = [
    url(
        regex=r'^$',
        view=views.TaskListView.as_view(),
        name='list'
    ),
    url(
        regex=r'^complete/(?P<pk>\d+)/$',
        view=views.TaskCompleteView.as_view(),
        name='complete'
    ),
    url(
        regex=r'^detail/(?P<pk>\d+)/$',
        view=views.TaskDetailView.as_view(),
        name='detail'
    ),
]
