from django.conf.urls import url
from core.email import sync_email_provider

from . import views

app_name = "users"
urlpatterns = [
    url(regex=r"^$", view=views.UserListView.as_view(), name="list"),
    url(regex=r"gpas/$", view=views.UserGPAFormSetView.as_view(), name="gpas"),
    url(
        regex=r"service/$", view=views.UserServiceFormSetView.as_view(), name="service"
    ),
    url(regex=r"orgs/$", view=views.UserOrgsFormSetView.as_view(), name="orgs"),
    url(regex=r"^redirect/$", view=views.UserRedirectView.as_view(), name="redirect"),
    url(regex=r"^myinfo/$", view=views.UserDetailUpdateView.as_view(), name="detail"),
    url(
        regex=r"^memberinfo/(?P<user_id>[\w.@+-]+)$",
        view=views.UserDetailView.as_view(),
        name="info",
    ),
    url(regex=r"^search/$", view=views.UserSearchView.as_view(), name="search"),
    url(regex=r"^lookup/$", view=views.UserLookupView.as_view(), name="lookup"),
    url(regex=r"^verify-form/$", view=views.user_verify, name="user_verify"),
    url(
        regex=r"^autocomplete/$",
        view=views.UserAutocomplete.as_view(),
        name="autocomplete",
    ),
    url(
        regex=r"^alterchapter/$",
        view=views.UserAlterView.as_view(),
        name="alterchapter",
    ),
    url(
        regex=r"^sync_email_provider/(?P<report_id>\d+)$",
        view=sync_email_provider,
        name="sync_email_provider",
    ),
]
