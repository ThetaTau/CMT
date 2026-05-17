"""Smoke tests for core/signals.py (Phase 0.5.4).

core/signals.py provides SignalWatchMixin — an admin-action mixin that
creates / destroys email_signals Signal records for a chapter or user entity.
There are no @receiver-style Django signal handlers in the codebase.
"""
import pytest
from django.test import RequestFactory

from core.signals import CHAPTER_WATCHES, SignalWatchMixin, USER_WATCHES
from thetatauCMT.chapters.tests.factories import ChapterFactory


# ---------------------------------------------------------------------------
# Concrete test subclasses of SignalWatchMixin
# ---------------------------------------------------------------------------


class _ChapterWatcher(SignalWatchMixin):
    """Concrete mixin for chapter-level watches (mirrors ChapterAdmin usage)."""

    object_type = "chapter"

    def message_user(self, request, message):  # noqa: D401
        pass  # suppress ModelAdmin dependency


class _UserWatcher(SignalWatchMixin):
    """Concrete mixin for user-level watches."""

    object_type = "user"

    def message_user(self, request, message):
        pass


# ---------------------------------------------------------------------------
# Import / structure smoke tests (no DB)
# ---------------------------------------------------------------------------


def test_signals_module_imports():
    """core.signals imports cleanly and exposes expected symbols."""
    import core.signals as mod

    assert hasattr(mod, "CHAPTER_WATCHES")
    assert hasattr(mod, "USER_WATCHES")
    assert hasattr(mod, "SignalWatchMixin")


def test_chapter_watches_structure():
    """CHAPTER_WATCHES is a non-empty list of (app_label, model, field) 3-tuples."""
    assert isinstance(CHAPTER_WATCHES, list)
    assert len(CHAPTER_WATCHES) > 0
    for entry in CHAPTER_WATCHES:
        assert len(entry) == 3, f"Expected 3-tuple, got: {entry!r}"
        app, model, field = entry
        assert isinstance(app, str) and app
        assert isinstance(model, str) and model
        assert isinstance(field, str) and field


def test_user_watches_structure():
    """USER_WATCHES is a non-empty list of (app_label, model, field) 3-tuples."""
    assert isinstance(USER_WATCHES, list)
    assert len(USER_WATCHES) > 0
    for entry in USER_WATCHES:
        assert len(entry) == 3, f"Expected 3-tuple, got: {entry!r}"
        app, model, field = entry
        assert isinstance(app, str) and app
        assert isinstance(model, str) and model
        assert isinstance(field, str) and field


# ---------------------------------------------------------------------------
# DB tests — Signal row creation / deletion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_watch_notification_add_creates_signals():
    """watch_notification_add with 'apply' in POST creates Signal rows in the DB."""
    from email_signals.models import Signal

    chapter = ChapterFactory.create()
    queryset = type(chapter).objects.filter(pk=chapter.pk)

    factory = RequestFactory()
    request = factory.post(
        "/admin/chapters/chapter/",
        data={"apply": "1", "emails": "watch-test@thetatau.org"},
    )

    before = Signal.objects.count()

    watcher = _ChapterWatcher()
    response = watcher.watch_notification_add(request, queryset)

    after = Signal.objects.count()

    # At least one Signal should have been created
    assert after > before
    # The handler redirects after persisting
    assert response.status_code == 302


@pytest.mark.django_db
def test_watch_notification_remove_deletes_signals():
    """watch_notification_remove deletes previously created Signal rows."""
    from email_signals.models import Signal

    chapter = ChapterFactory.create()
    queryset = type(chapter).objects.filter(pk=chapter.pk)

    factory = RequestFactory()
    add_request = factory.post(
        "/admin/chapters/chapter/",
        data={"apply": "1", "emails": "watch-test@thetatau.org"},
    )
    remove_request = factory.get("/admin/chapters/chapter/")

    watcher = _ChapterWatcher()

    # Setup: add signals first
    watcher.watch_notification_add(add_request, queryset)
    after_add = Signal.objects.count()
    assert after_add > 0, "Precondition: signals must exist before removal"

    # Act: remove signals for the same entity
    watcher.watch_notification_remove(remove_request, queryset)
    after_remove = Signal.objects.count()

    assert after_remove < after_add
