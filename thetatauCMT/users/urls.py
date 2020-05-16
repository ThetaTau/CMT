from django.conf.urls import url

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
    url(regex=r"^lookup/$", view=views.UserLookupView.as_view(), name="lookup"),
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
]
