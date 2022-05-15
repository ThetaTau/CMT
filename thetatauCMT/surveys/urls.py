from django.urls import path, include
from django.conf.urls import url
from survey.views import ConfirmView, SurveyCompleted, SurveyDetail
from . import views

app_name = "surveys"
urlpatterns = [
    path(
        "depledge/<str:user_id>",
        view=views.DepledgeSurveyCreateView.as_view(),
        name="depledge",
    ),
    path(r"<slug:slug>/", view=views.SurveyDetail.as_view(), name="survey-detail"),
    path(
        r"<slug:slug>/<int:step>/",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-step",
    ),
]
