from django.urls import path
from . import views

app_name = "surveys"
urlpatterns = [
    path(
        "depledge/<str:user_id>",
        view=views.DepledgeSurveyCreateView.as_view(),
        name="depledge",
    ),
]
