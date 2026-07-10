from django.urls import path

from . import views

app_name = "contact_sync"

urlpatterns = [
    path(
        "region/<slug:region_slug>/vcard/",
        views.download_region_vcard,
        name="region_vcard",
    ),
    path(
        "national/vcard/",
        views.download_national_vcard,
        name="national_vcard",
    ),
    path("status/", views.sync_status, name="status"),
    # Provider-specific OAuth + sync endpoints. Kept as flat named URLs so the
    # provider registry can reverse them as f"contact_sync:{key}_..." without
    # dispatching through a converter.
    path("google/authorize/", views.oauth_authorize, {"provider_key": "google"}, name="google_authorize"),
    path("google/callback/", views.oauth_callback, {"provider_key": "google"}, name="google_callback"),
    path("google/sync/", views.provider_sync, {"provider_key": "google"}, name="google_sync"),
    path("google/disconnect/", views.oauth_disconnect, {"provider_key": "google"}, name="google_disconnect"),
    path("google/auto-sync/", views.provider_auto_sync, {"provider_key": "google"}, name="google_auto_sync"),
    path("microsoft/authorize/", views.oauth_authorize, {"provider_key": "microsoft"}, name="microsoft_authorize"),
    path("microsoft/callback/", views.oauth_callback, {"provider_key": "microsoft"}, name="microsoft_callback"),
    path("microsoft/sync/", views.provider_sync, {"provider_key": "microsoft"}, name="microsoft_sync"),
    path("microsoft/disconnect/", views.oauth_disconnect, {"provider_key": "microsoft"}, name="microsoft_disconnect"),
    path("microsoft/auto-sync/", views.provider_auto_sync, {"provider_key": "microsoft"}, name="microsoft_auto_sync"),
]
