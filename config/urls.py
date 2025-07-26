from django.conf import settings
from django.urls import path, re_path
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth.views import (
    PasswordResetConfirmView,
    PasswordResetCompleteView,
    PasswordResetView,
    PasswordResetDoneView,
)
from oauth2_provider import urls as oauth2_urls
from allauth.account.views import LogoutView
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from material.frontend.urls import modules
from core.views import HomeView
from core.address import ZipCodeAutocomplete
from users.views import UserLookupLoginView
from django.views import defaults as default_views


def home_redirect(request):
    return redirect("http://127.0.0.1")


urlpatterns = [
    path("django_plotly_dash/", include("django_plotly_dash.urls")),
    path("o/", include(oauth2_urls)),
    path(
        "zipcode-autocomplete/",
        ZipCodeAutocomplete.as_view(),
        name="zipcode-autocomplete",
    ),
    path("", HomeView.as_view(template_name="pages/home.html"), name="home"),
    path("", include("allauth_2fa.urls")),
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=settings.STATIC_URL + "images/favicon.png", permanent=True
        ),
    ),
    # wp-content/* must remain re_path due to wildcard
    re_path(r"^wp-content/*", home_redirect),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    path("help/", TemplateView.as_view(template_name="pages/help.html"), name="help"),
    path(
        "electronic_terms/",
        TemplateView.as_view(template_name="pages/electronic_terms.html"),
        name="electronic_terms",
    ),
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="account/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(
            template_name="account/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        "password_reset/",
        PasswordResetView.as_view(template_name="account/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        PasswordResetDoneView.as_view(template_name="account/password_reset_done.html"),
        name="password_reset_done",
    ),
    # Django Admin, use {% url 'admin:index' %}
    # If settings.ADMIN_URL is a simple string, use path. Otherwise, keep re_path.
    re_path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("users.urls", namespace="users")),
    path("accounts/login/", UserLookupLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
    # Your stuff: custom urls includes go here
    path("", RedirectView.as_view(url="/workflow/", permanent=False)),
    path("report_builder/", include("report_builder.urls")),
    path("", include((modules.urls))),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("email-signals/", include("email_signals.urls")),
    path("terms/", include("termsandconditions.urls")),
    path(
        "privacy/",
        RedirectView.as_view(url="/terms/view/privacy/", permanent=True),
        name="privacy",
    ),
    path(
        "eula/",
        RedirectView.as_view(url="/terms/view/eula/", permanent=True),
        name="eula",
    ),
    path("regions/", include("regions.urls", namespace="regions")),
    path("chapters/", include("chapters.urls", namespace="chapters")),
    path("events/", include("events.urls", namespace="events")),
    path("jobs/", include("jobs.urls", namespace="jobs")),
    path("notes/", include("notes.urls", namespace="notes")),
    path("goals/", include("objectives.urls", namespace="objectives")),
    path("trainings/", include("trainings.urls", namespace="trainings")),
    path("finances/", include("finances.urls", namespace="finances")),
    path("scores/", include("scores.urls", namespace="scores")),
    path("submissions/", include("submissions.urls", namespace="submissions")),
    path("surveys/", include("surveys.urls", namespace="surveys")),
    path("forms/", include("forms.urls", namespace="forms")),
    path("tasks/", include("tasks.urls", namespace="tasks")),
    path("ballots/", include("ballots.urls", namespace="ballots")),
    path(
        "rmp/",
        RedirectView.as_view(pattern_name="forms:rmp", permanent=True),
        name="rmp",
    ),
    path(
        "initiation/",
        RedirectView.as_view(pattern_name="forms:initiation", permanent=True),
    ),
    path(
        "officer/",
        RedirectView.as_view(pattern_name="forms:officer", permanent=True),
    ),
    path("status/", RedirectView.as_view(pattern_name="forms:status", permanent=True)),
    path(
        "pledgeform/",
        RedirectView.as_view(pattern_name="forms:pledgeform", permanent=True),
    ),
    path(
        "pledgeform-alt/",
        RedirectView.as_view(pattern_name="forms:pledgeform-alt", permanent=True),
    ),
    path(
        "report/",
        RedirectView.as_view(
            pattern_name="viewflow:forms:hseducation:start", permanent=False
        ),
    ),
    path(
        "education/",
        RedirectView.as_view(
            pattern_name="viewflow:forms:hseducation:start", permanent=True
        ),
    ),
    path(
        "nme-program/",
        RedirectView.as_view(
            pattern_name="viewflow:forms:pledgeprogramprocess:start", permanent=True
        ),
    ),
    path(
        "conventionform/",
        RedirectView.as_view(
            pattern_name="viewflow:forms:convention:start", permanent=True
        ),
        name="conventionform",
    ),
    path(
        "osmform/",
        RedirectView.as_view(pattern_name="viewflow:forms:osm:start", permanent=True),
        name="osmform",
    ),
    path(
        "alumniexclusionform/",
        RedirectView.as_view(
            pattern_name="viewflow:forms:alumniexclusion:start", permanent=True
        ),
        name="alumniexclusion",
    ),
    path(
        "gear/",
        RedirectView.as_view(pattern_name="submissions:gear", permanent=True),
        name="gear",
    ),
    path(
        "update/",
        RedirectView.as_view(pattern_name="users:lookup_search", permanent=True),
        name="update_lookup",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns

if settings.DEBUG or "staging" in settings.SETTINGS_MODULE:
    urlpatterns += [
        path("herald/", include("herald.urls")),
    ]
