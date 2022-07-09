from django.urls import path

from . import views

app_name = "trainings"
urlpatterns = [
    path("", views.TrainingListView.as_view(), name="list"),
]
