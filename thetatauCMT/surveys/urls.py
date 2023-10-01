from django.urls import path, include
from django.conf.urls import url
from survey.views import ConfirmView, SurveyCompleted, SurveyDetail
from . import views

app_name = "surveys"
urlpatterns = [
    path(
        "depledge/<str:username>",
        view=views.DepledgeSurveyCreateView.as_view(),
        name="depledge",
    ),
    path(r"<slug:slug>/", view=views.SurveyDetail.as_view(), name="survey-detail"),
    path(
        r"<slug:slug>/<int:step>/",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-step",
    ),
    path(
        r"<slug:slug>/<str:user_pk>",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-member",
    ),
    path(
        r"<slug:slug>/<int:step>/<str:user_pk>",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-step-member",
    ),
]
