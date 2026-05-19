from django.urls import path

from . import views

app_name = "surveys"
urlpatterns = [
    path(
        "depledge/<str:username>",
        view=views.DepledgeSurveyCreateView.as_view(),
        name="depledge",
    ),
    path("<slug:slug>/", view=views.SurveyDetail.as_view(), name="survey-detail"),
    path(
        "<slug:slug>/<int:step>/",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-step",
    ),
    path(
        "<slug:slug>/<str:user_pk>",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-member",
    ),
    path(
        "<slug:slug>/<int:step>/<str:user_pk>",
        view=views.SurveyDetail.as_view(),
        name="survey-detail-step-member",
    ),
]
