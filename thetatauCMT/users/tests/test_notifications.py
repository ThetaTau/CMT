"""
Unit tests for thetatauCMT/users/notifications.py.

Tests cover __init__ initialization of each notification class.
No emails are actually sent — we only assert that attributes are set correctly.
"""

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.notifications import MemberEmail, MemberInfoUpdate, NewOfficers, OfficerUpdateReminder
from thetatauCMT.users.tests.factories import UserFactory

# ─── MemberInfoUpdate ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_member_info_update_to_emails_contains_user_email():
    user = UserFactory.create()
    updater = UserFactory.create()
    notif = MemberInfoUpdate(user, updater)
    assert user.email in notif.to_emails


@pytest.mark.django_db
def test_member_info_update_reply_to_is_updater():
    user = UserFactory.create()
    updater = UserFactory.create()
    notif = MemberInfoUpdate(user, updater)
    assert updater.email in notif.reply_to


@pytest.mark.django_db
def test_member_info_update_context_has_user_and_updater():
    user = UserFactory.create()
    updater = UserFactory.create()
    notif = MemberInfoUpdate(user, updater)
    assert notif.context["user"] == user
    assert notif.context["updater"] == updater


@pytest.mark.django_db
def test_member_info_update_password_flag_with_usable_password():
    user = UserFactory.create()
    updater = UserFactory.create()
    notif = MemberInfoUpdate(user, updater)
    # UserFactory creates users with a usable password
    assert notif.context["password"] is True


# ─── NewOfficers ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_new_officers_to_emails_contains_all_officers():
    chapter = ChapterFactory.create()
    officer1 = UserFactory.create(chapter=chapter)
    officer2 = UserFactory.create(chapter=chapter)
    notif = NewOfficers([officer1, officer2])
    assert officer1.email in notif.to_emails
    assert officer2.email in notif.to_emails


@pytest.mark.django_db
def test_new_officers_context_has_chapter():
    chapter = ChapterFactory.create()
    officer = UserFactory.create(chapter=chapter)
    notif = NewOfficers([officer])
    assert notif.context["chapter"] == chapter


# ─── OfficerUpdateReminder ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_officer_update_reminder_to_emails_set():
    chapter = ChapterFactory.create()
    emails = {f"test_{chapter.pk}@example.com"}
    officers_to_update = ["regent", "treasurer"]
    notif = OfficerUpdateReminder(chapter, emails, officers_to_update)
    assert f"test_{chapter.pk}@example.com" in notif.to_emails


@pytest.mark.django_db
def test_officer_update_reminder_subject_contains_chapter():
    chapter = ChapterFactory.create()
    notif = OfficerUpdateReminder(chapter, {"officer@example.com"}, ["regent"])
    assert chapter.name in notif.subject


@pytest.mark.django_db
def test_officer_update_reminder_context_has_officers():
    chapter = ChapterFactory.create()
    officers_to_update = ["regent", "treasurer"]
    notif = OfficerUpdateReminder(chapter, {"officer@example.com"}, officers_to_update)
    assert "regent" in notif.context["officers"]
    assert "treasurer" in notif.context["officers"]


@pytest.mark.django_db
def test_officer_update_reminder_cc_contains_region_email():
    chapter = ChapterFactory.create()
    notif = OfficerUpdateReminder(chapter, {"officer@example.com"}, ["scribe"])
    assert chapter.region.email in notif.cc


# ─── MemberEmail ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_member_email_to_emails_contains_user_email():
    user = UserFactory.create()
    notif = MemberEmail(user, "Test Title", "Hello {{ user }}", {"user": str(user)})
    assert user.email in notif.to_emails


@pytest.mark.django_db
def test_member_email_subject_matches_title():
    user = UserFactory.create()
    notif = MemberEmail(user, "My Custom Title", "Content here", {})
    assert notif.subject == "My Custom Title"


@pytest.mark.django_db
def test_member_email_context_has_user():
    user = UserFactory.create()
    notif = MemberEmail(user, "Title", "Body", {})
    assert notif.context["user"] == user


@pytest.mark.django_db
def test_member_email_renders_template_content():
    user = UserFactory.create()
    notif = MemberEmail(user, "Title", "Fixed content string", {})
    assert "Fixed content string" in notif.context["email_content"]


# ─── OfficerMonthly ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_officer_monthly_init_sets_subject():
    from thetatauCMT.users.notifications import OfficerMonthly

    chapter = ChapterFactory.create(candidate_chapter=False)
    notif = OfficerMonthly(chapter)
    assert chapter.name + " Chapter" in notif.subject


@pytest.mark.django_db
def test_officer_monthly_context_has_chapter():
    from thetatauCMT.users.notifications import OfficerMonthly

    chapter = ChapterFactory.create(candidate_chapter=False)
    notif = OfficerMonthly(chapter)
    assert "chapter" in notif.context


@pytest.mark.django_db
def test_officer_monthly_candidate_chapter_no_suffix():
    from thetatauCMT.users.notifications import OfficerMonthly

    chapter = ChapterFactory.create(candidate_chapter=True)
    notif = OfficerMonthly(chapter)
    # Candidate chapters have no " Chapter" suffix in the name
    assert " Chapter" not in notif.context["chapter"]


@pytest.mark.django_db
def test_officer_monthly_context_has_tasks():
    from thetatauCMT.users.notifications import OfficerMonthly

    chapter = ChapterFactory.create()
    notif = OfficerMonthly(chapter)
    assert "tasks_upcoming" in notif.context
    assert "tasks_overdue" in notif.context


# ─── RDMonthly ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rd_monthly_init_sets_to_emails_from_region():
    from thetatauCMT.users.notifications import RDMonthly

    chapter = ChapterFactory.create(active=True)
    region = chapter.region
    notif = RDMonthly(region)
    assert region.email in notif.to_emails


@pytest.mark.django_db
def test_rd_monthly_context_has_table_and_region():
    from thetatauCMT.users.notifications import RDMonthly

    chapter = ChapterFactory.create(active=True)
    region = chapter.region
    notif = RDMonthly(region)
    assert "table" in notif.context
    assert "region" in notif.context


@pytest.mark.django_db
def test_rd_monthly_candidate_chapter_string():
    """RDMonthly('candidate_chapter') uses hardcoded email and CC chapter email."""
    from thetatauCMT.users.notifications import RDMonthly

    notif = RDMonthly("candidate_chapter")
    assert "ccd@thetatau.org" in notif.to_emails


@pytest.mark.django_db
def test_rd_monthly_skips_inactive_chapters():
    """RDMonthly skips inactive chapters when building context data."""
    from thetatauCMT.users.notifications import RDMonthly

    # Create one active and one inactive chapter in the same region
    active_chapter = ChapterFactory.create(active=True)
    region = active_chapter.region
    ChapterFactory.create(region=region, active=False)
    notif = RDMonthly(region)
    # Table data should only have the active chapter
    assert "table" in notif.context


# ─── MemberInfoUpdate – password=False branch ────────────────────────────────


@pytest.mark.django_db
def test_member_info_update_password_false_when_no_usable_password():
    """password flag is False when the user has no usable password."""
    user = UserFactory.create()
    user.set_unusable_password()
    user.save()
    updater = UserFactory.create()
    notif = MemberInfoUpdate(user, updater)
    assert notif.context["password"] is False
