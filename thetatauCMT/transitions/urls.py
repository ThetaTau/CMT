from django.urls import path

from . import views

app_name = "transitions"
urlpatterns = [
    path("", views.TransitionsListView.as_view(), name="list"),
    path("<int:pk>/compose/", views.ComposeReportView.as_view(), name="compose"),
    path("<int:pk>/close-vacant/", views.CloseNAVacantView.as_view(), name="close-vacant"),
    path("attachments/<int:pk>/delete/", views.AttachmentDeleteView.as_view(), name="attachment-delete"),
]
