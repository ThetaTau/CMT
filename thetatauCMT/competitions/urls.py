from django.urls import path

from . import views

app_name = "competitions"
urlpatterns = [
    path("", views.CompetitionListView.as_view(), name="list"),
    path("current/", views.CurrentCompetitionView.as_view(), name="current"),
    path("current/submit/", views.CurrentCompetitionView.as_view(target="submit"), name="submit_current"),
    path("current/manage/", views.CurrentCompetitionView.as_view(target="manage"), name="manage_current"),
    path("current/results/", views.CurrentCompetitionView.as_view(target="results"), name="results_current"),
    path("current/scores/", views.CurrentCompetitionView.as_view(target="scores"), name="scores_current"),
    path("member-autocomplete/", views.MemberAutocomplete.as_view(), name="member-autocomplete"),
    path("judge-autocomplete/", views.JudgeAutocomplete.as_view(), name="judge-autocomplete"),
    path("entry/<uuid:public_id>/", views.EntryDetailView.as_view(), name="entry"),
    path("file/<uuid:public_id>/", views.EntryFileView.as_view(), name="file"),
    path("judging/", views.MyJudgingView.as_view(), name="judging"),
    path("judging/<uuid:public_id>/", views.ScorecardView.as_view(), name="scorecard"),
    path("<slug:slug>/", views.CompetitionDetailView.as_view(), name="detail"),
    path("<slug:slug>/intent/", views.IntentView.as_view(), name="intent"),
    path("<slug:slug>/manage/", views.ManageView.as_view(), name="manage"),
    path("<slug:slug>/export/<str:kind>/", views.ExportView.as_view(), name="export"),
    path("<slug:slug>/round/<int:number>/submit/", views.SubmitView.as_view(), name="submit"),
    path(
        "<slug:slug>/round/<int:number>/submit/<slug:chapter>/",
        views.SubmitView.as_view(),
        name="submit_on_behalf",
    ),
    path("<slug:slug>/round/<int:number>/extension/<slug:chapter>/", views.ExtensionView.as_view(), name="extension"),
    path("<slug:slug>/round/<int:number>/results/", views.ResultsView.as_view(), name="results"),
    path("<slug:slug>/round/<int:number>/judges/", views.JudgesView.as_view(), name="judges"),
    path("<slug:slug>/round/<int:number>/scores/", views.ScoresView.as_view(), name="scores"),
]
