import pytest
from django.utils.text import slugify

from thetatauCMT.announcements.models import Announcement


def _make_announcement(title="Test Announcement", content="<p>Hello</p>"):
    ann = Announcement(
        title=title,
        content=content,
        priority=5,
    )
    ann.save()
    return ann


# ---------------------------------------------------------------------------
# Announcement.save — slug generation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_announcement_save_sets_slug():
    ann = _make_announcement(title="My Great Announcement")
    assert ann.slug == slugify("My Great Announcement")
    assert ann.slug == "my-great-announcement"


@pytest.mark.django_db
def test_announcement_slug_unique_increments_counter():
    """Two announcements with the same title get distinct slugs."""
    ann1 = _make_announcement(title="Duplicate Title")
    ann2 = _make_announcement(title="Duplicate Title")
    assert ann1.slug != ann2.slug
    assert ann2.slug.startswith("duplicate-title")


@pytest.mark.django_db
def test_announcement_save_does_not_change_slug_on_update():
    """Re-saving an existing announcement does NOT regenerate the slug."""
    ann = _make_announcement(title="Stable Slug")
    original_slug = ann.slug
    ann.content = "<p>Updated content</p>"
    ann.save()
    ann.refresh_from_db()
    assert ann.slug == original_slug


# ---------------------------------------------------------------------------
# Announcement ordering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_announcement_ordering_by_priority():
    high = _make_announcement(title="High Priority")
    high.priority = 1
    high.save()
    low = _make_announcement(title="Low Priority")
    low.priority = 9
    low.save()
    announcements = list(Announcement.objects.filter(pk__in=[high.pk, low.pk]))
    assert announcements[0].priority <= announcements[1].priority


# ---------------------------------------------------------------------------
# Announcement.__unicode__
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_announcement_unicode():
    ann = _make_announcement(title="Unicode Test")
    assert ann.__unicode__() == "Announcement: Unicode Test"
