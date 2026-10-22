"""Admin pages may only reference static files collectstatic can collect.

Production serves static files through ``CompressedManifestStaticFilesStorage``,
which turns ``{% static %}`` on a path missing from ``staticfiles.json`` into
``ValueError: Missing staticfiles manifest entry`` (a 500). Locally the plain
storage just 404s the asset, so such pages only break in production.
"""

from urllib.parse import unquote, urlsplit

import pytest
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import override_settings
from django.urls import reverse


def _media_paths(media):
    return [str(path) for path in media._js] + [str(path) for paths in media._css.values() for path in paths]


def test_every_admin_media_file_exists():
    missing = sorted(
        f"{model._meta.label}: {path}"
        for model, model_admin in admin.site._registry.items()
        for path in _media_paths(model_admin.media)
        if not path.startswith(("http://", "https://", "/")) and not finders.find(path)
    )
    assert missing == []


@pytest.fixture
def strict_static(monkeypatch):
    """``{% static %}`` raises for an uncollectable file, as the production manifest storage does."""

    def url(name, *args, **kwargs):
        if not finders.find(urlsplit(unquote(name)).path):
            raise ValueError(f"Missing staticfiles manifest entry for '{name}'")
        return f"/static/{name}"

    monkeypatch.setattr(staticfiles_storage, "url", url)


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_email_signals_admin_pages_render_with_strict_static(strict_static, auto_login_user, admin_user):
    """Regression: django-email-signals 2.0.0 ships without the CSS/JS its
    ``SignalAdmin.Media`` names, and its TinyMCE widget's assets are never
    collected, so the Signal admin pages 500'd in production."""
    from django.contrib.contenttypes.models import ContentType
    from email_signals.models import Signal

    from thetatauCMT.chapters.models import Chapter

    signal = Signal.objects.create(
        name="Chapter Watch",
        content_type=ContentType.objects.get_for_model(Chapter),
        subject="Chapter updated",
        mailing_list="central.office@thetatau.org",
        signal_type="post_save",
        active=False,
    )
    client, _ = auto_login_user(user=admin_user)
    for url in (
        reverse("admin:email_signals_signal_changelist"),
        reverse("admin:email_signals_signal_add"),
        reverse("admin:email_signals_signal_change", args=[signal.pk]),
    ):
        response = client.get(url)
        assert response.status_code == 200, url
    assert 'name="html_message"' in response.content.decode()
