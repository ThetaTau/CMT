"""Tests for chapters/notifications.py."""

from email.mime.base import MIMEBase

import pytest

from .factories import ChapterFactory


@pytest.mark.django_db
def test_dues_reminder_init_sets_to_emails():
    """DuesReminder can be instantiated with a chapter and any attachment."""
    from thetatauCMT.chapters.notifications import DuesReminder

    chapter = ChapterFactory.create()
    # A simple MIME attachment object (what generate_dues_attachment() returns)
    attachment = MIMEBase("application", "csv")
    attachment.add_header("Content-Disposition", "attachment", filename="test_dues.csv")
    attachment.set_payload("col1,col2\nval1,val2")

    notif = DuesReminder(chapter, attachment)
    # to_emails is the council emails set (may be empty if no officers)
    assert isinstance(notif.to_emails, (set, list))
    assert notif.cc == ["accounting@thetatau.org"]
    assert notif.reply_to == ["accounting@thetatau.org"]


@pytest.mark.django_db
def test_dues_reminder_subject_contains_chapter_name():
    """DuesReminder subject includes the chapter name."""
    from thetatauCMT.chapters.notifications import DuesReminder

    chapter = ChapterFactory.create(candidate_chapter=False)
    attachment = MIMEBase("application", "csv")
    attachment.set_payload("")

    notif = DuesReminder(chapter, attachment)
    assert chapter.name in notif.subject
    assert "Dues Test Roster" in notif.subject


@pytest.mark.django_db
def test_dues_reminder_subject_candidate_chapter_no_suffix():
    """Candidate chapters don't have 'Chapter' appended to name in subject."""
    from thetatauCMT.chapters.notifications import DuesReminder

    chapter = ChapterFactory.create(candidate_chapter=True)
    attachment = MIMEBase("application", "csv")
    attachment.set_payload("")

    notif = DuesReminder(chapter, attachment)
    assert chapter.name in notif.subject
    # Candidate chapter: name should NOT have " Chapter" appended
    assert chapter.name + " Chapter" not in notif.subject


@pytest.mark.django_db
def test_dues_reminder_context_includes_chapter_name():
    """DuesReminder context has required keys."""
    from thetatauCMT.chapters.notifications import DuesReminder

    chapter = ChapterFactory.create(candidate_chapter=False)
    attachment = MIMEBase("application", "csv")
    attachment.set_payload("")

    notif = DuesReminder(chapter, attachment)
    assert "chapter" in notif.context
    assert "invoice_date" in notif.context
    assert "change_date" in notif.context
    assert notif.context["chapter"] == chapter.name + " Chapter"


@pytest.mark.django_db
def test_dues_reminder_attachment_is_set():
    """DuesReminder attachments list contains the passed attachment."""
    from thetatauCMT.chapters.notifications import DuesReminder

    chapter = ChapterFactory.create()
    attachment = MIMEBase("application", "csv")
    attachment.set_payload("a,b")

    notif = DuesReminder(chapter, attachment)
    assert len(notif.attachments) == 1
    assert notif.attachments[0] is attachment


@pytest.mark.django_db
def test_dues_reminder_get_demo_args():
    """DuesReminder.get_demo_args returns a list with chapter and attachment."""
    # Ensure there is at least one chapter in the DB (fixtures load them)
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.chapters.notifications import DuesReminder

    if not Chapter.objects.exists():
        pytest.skip("No chapters in DB")
    args = DuesReminder.get_demo_args()
    assert len(args) == 2
    chapter_arg, attachment_arg = args
    assert isinstance(chapter_arg, Chapter)
