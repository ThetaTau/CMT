from django.urls import path

from . import views

app_name = "objectives"
urlpatterns = [
    path("", views.ObjectiveListView.as_view(), name="list"),
    path("create", views.ObjectiveCreateView.as_view(), name="create"),
    path("detail/<int:pk>/", views.ObjectiveDetailView.as_view(), name="detail"),
]
