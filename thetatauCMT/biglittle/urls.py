from django.urls import path

from . import views

app_name = "biglittle"
urlpatterns = [
    path("", views.BigLittleListView.as_view(), name="list"),
    path("record/", views.BigLittleRecordView.as_view(), name="record"),
    path("upload/", views.BigLittleUploadView.as_view(), name="upload"),
    path("upload/template.csv", views.BigLittleUploadTemplateView.as_view(), name="upload_template"),
    path("review/", views.PendingPairingReviewView.as_view(), name="review"),
    path("member-autocomplete/", views.BigLittleMemberAutocomplete.as_view(), name="member-autocomplete"),
    path("member/<int:pk>/", views.MemberProfileRedirectView.as_view(), name="member"),
    path("<int:pk>/remove/", views.BigLittleRemoveView.as_view(), name="remove"),
    path("<slug:slug>/tree/", views.FamilyTreeView.as_view(), name="tree"),
    path("<slug:slug>/tree/members/", views.FamilyTreeMemberAutocomplete.as_view(), name="tree-members"),
]
