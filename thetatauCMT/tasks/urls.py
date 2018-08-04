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
        regex=r'^~add/$',
        view=views.TaskCompleteView.as_view(),
        name='add'
    ),
]
