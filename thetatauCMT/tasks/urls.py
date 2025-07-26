from django.urls import path

from . import views

app_name = "tasks"
urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("complete/<int:pk>/", views.TaskCompleteView.as_view(), name="complete"),
    path("detail/<int:pk>/", views.TaskDetailView.as_view(), name="detail"),
]
