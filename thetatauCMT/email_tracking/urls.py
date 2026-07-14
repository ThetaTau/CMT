from django.urls import path

from . import views

app_name = "email_tracking"

urlpatterns = [
    path(
        "communication/",
        views.MemberCommunicationView.as_view(),
        name="member_communication",
    ),
    path(
        "communication/results/",
        views.MemberCommunicationResultsView.as_view(),
        name="member_communication_results",
    ),
    path(
        "message/<str:message_id>/history/",
        views.MessageHistoryView.as_view(),
        name="message_history",
    ),
]
