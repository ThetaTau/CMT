from django.urls import path

from . import views

app_name = "awards"

urlpatterns = [
    path("grant/", views.DirectGrantView.as_view(), name="direct_grant"),
    path("nominate/eligible-recipients/", views.EligibleRecipientsView.as_view(), name="eligible_recipients"),
    path(
        "nominate/recipient-member-autocomplete/",
        views.AwardRecipientMemberAutocomplete.as_view(),
        name="recipient_member_autocomplete",
    ),
    path("grant/<int:grant_pk>/certificates/", views.GrantArtifactView.as_view(), name="grant_artifacts"),
    path(
        "certificate/<int:artifact_pk>/download/", views.GrantArtifactDownloadView.as_view(), name="artifact_download"
    ),
    # Public awards dashboard / directory (AWI-11)
    path("catalog/", views.AwardCatalogView.as_view(), name="catalog"),
    path("directory/", views.AwardDirectoryView.as_view(), name="directory"),
    path("directory/type/<int:pk>/", views.AwardTypeWinnersView.as_view(), name="type_winners"),
    path("directory/cycle/<int:pk>/", views.AwardCycleWinnersView.as_view(), name="cycle_winners"),
    # Reports / exports + award history (AWI-12)
    path("export/", views.AwardExportView.as_view(), name="export"),
    path("history/member/<str:username>/", views.MemberAwardHistoryView.as_view(), name="member_history"),
    path("history/chapter/<slug:slug>/", views.ChapterAwardHistoryView.as_view(), name="chapter_history"),
    # Legacy / historical bulk import (AWI-13, Admin-only)
    path("import/", views.AwardImportUploadView.as_view(), name="import_upload"),
    path("import/queue/", views.AwardImportQueueListView.as_view(), name="import_queue"),
    path("import/queue/resolve/", views.AwardImportQueueResolveView.as_view(), name="import_resolve"),
]
