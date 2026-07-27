from django.urls import path

from core.email import sync_email_provider

from . import views

app_name = "users"
urlpatterns = [
    path("", views.UserListView.as_view(), name="list"),
    path("gpas/", views.UserGPAFormSetView.as_view(), name="gpas"),
    path("service/", views.UserServiceFormSetView.as_view(), name="service"),
    path("orgs/", views.UserOrgListView.as_view(), name="orgs"),
    path("orgs/add/", views.UserOrgCreateView.as_view(), name="orgs_add"),
    path(
        "orgs/autocomplete/",
        views.OrganizationAutocomplete.as_view(create_field="name"),
        name="org-autocomplete",
    ),
    path("orgs/<int:pk>/delete/", views.UserOrgDeleteView.as_view(), name="orgs_delete"),
    path("redirect/", views.UserRedirectView.as_view(), name="redirect"),
    path(
        "unsubscribe/<str:token>/",
        views.UnsubscribeConfirmView.as_view(),
        name="unsubscribe",
    ),
    path("myinfo/", views.UserDetailUpdateView.as_view(), name="detail"),
    path("myinfo/profile-picture/", views.ProfilePictureUpdateView.as_view(), name="profile_picture"),
    path("profile/<str:username>/", views.UserProfileView.as_view(), name="profile"),
    path("memberinfo/<str:username>", views.UserProfileView.as_view(), name="info"),
    path("search/", views.UserSearchView.as_view(), name="search"),
    path("lookup-search/", views.UserLookupSearchView.as_view(), name="lookup_search"),
    path("badge-lookup/", views.UserBadgeLookupView.as_view(), name="badge_lookup"),
    path("lookup-select/", views.UserLookupSelectView.as_view(), name="lookup_select"),
    path("update/", views.UserLookupUpdateView.as_view(), name="update"),
    path(
        "update-review/<int:pk>/",
        views.UserUpdateDirectReview.as_view(),
        name="update_review",
    ),
    path("verify-form/", views.user_verify, name="user_verify"),
    path("autocomplete/", views.UserAutocomplete.as_view(), name="autocomplete"),
    path("alterchapter/", views.UserAlterView.as_view(), name="alterchapter"),
    path("toggle-natoff/", views.ToggleNatoffView.as_view(), name="toggle_natoff"),
    path(
        "sync_email_provider/<int:report_id>",
        sync_email_provider,
        name="sync_email_provider",
    ),
]
