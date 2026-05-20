from django.urls import path

from . import views

app_name = "notes"
urlpatterns = [
    path("add/<slug:slug>/", views.ChapterNoteCreateView.as_view(), name="add"),
    path("add_user/<str:username>", views.UserNoteCreateView.as_view(), name="add_user"),
    path("detail/<int:pk>/", views.ChapterNoteDetailView.as_view(), name="detail"),
]
