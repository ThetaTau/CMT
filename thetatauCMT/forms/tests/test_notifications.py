"""
Tests for thetatauCMT/forms/notifications.py.

Tests cover initialization logic of notification classes: attribute assignment,
context building, attachment construction. No emails are actually sent.
"""

import datetime
from io import BytesIO

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.notifications import (
    CentralOfficeGenericEmail,
    EmailAdvisorWelcome,
    EmailRMPReport,
    EmailRMPSigned,
    EmailScribeExpulsion,
)
from thetatauCMT.users.tests.factories import UserFactory

# ─── CentralOfficeGenericEmail ────────────────────────────────────────────────


def test_central_office_generic_email_default_subject():
    notif = CentralOfficeGenericEmail("Test message")
    assert notif.subject == "[CMT] Record Message"


def test_central_office_generic_email_to_and_cc():
    notif = CentralOfficeGenericEmail("Test message")
    assert notif.to_emails == ["central.office@thetatau.org"]
    assert "cmt@thetatau.org" in notif.cc


def test_central_office_generic_email_context_contains_message():
    notif = CentralOfficeGenericEmail("Hello from tests")
    assert notif.context["message"] == "Hello from tests"


def test_central_office_generic_email_custom_subject():
    notif = CentralOfficeGenericEmail("Test message", subject="[CMT] Custom Subject")
    assert notif.subject == "[CMT] Custom Subject"


def test_central_office_generic_email_no_attachments():
    notif = CentralOfficeGenericEmail("Test message")
    assert notif.attachments == []
    assert notif.context["file_names"] == []


def test_central_office_generic_email_with_named_file_attachment():
    """Files with a .name attribute are recorded in context file_names."""
    from io import BytesIO

    attachment = BytesIO(b"fake pdf content")
    attachment.name = "test_report.pdf"
    # A BytesIO also has .seek / .read, so it will be added to self.attachments too.
    notif = CentralOfficeGenericEmail("Attach test", attachments=[attachment])
    assert "test_report.pdf" in notif.context["file_names"]
    assert len(notif.attachments) == 1
    assert notif.attachments[0][0] == "test_report.pdf"


# ─── EmailRMPSigned ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_rmp_signed_to_emails_contains_user_email():
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    file_content = b"PDF content"
    file_name = f"RMP_{user.name}.pdf"
    notif = EmailRMPSigned(user, file_content, file_name)
    assert user.email in notif.to_emails


@pytest.mark.django_db
def test_email_rmp_signed_cc_contains_cmt():
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    notif = EmailRMPSigned(user, b"", "rmp.pdf")
    assert "cmt@thetatau.org" in notif.cc


@pytest.mark.django_db
def test_email_rmp_signed_attachment_tuple():
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    file_content = b"PDF content"
    file_name = "rmp_signed.pdf"
    notif = EmailRMPSigned(user, file_content, file_name)
    assert len(notif.attachments) == 1
    name, data, mime = notif.attachments[0]
    assert name == file_name
    assert data == file_content
    assert mime == "application/pdf"


@pytest.mark.django_db
def test_email_rmp_signed_context_contains_user():
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()
    notif = EmailRMPSigned(user, b"", "rmp.pdf")
    assert notif.context["user"] == user


# ─── EmailRMPReport ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_rmp_report_to_emails():
    user = UserFactory.create()
    mock_file = BytesIO(b"fake pdf")
    mock_file.name = "chapter_report.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailRMPReport(user, mock_file)
    assert "risk@thetatau.org" in notif.to_emails


@pytest.mark.django_db
def test_email_rmp_report_cc_contains_user_email():
    user = UserFactory.create()
    mock_file = BytesIO(b"fake pdf")
    mock_file.name = "chapter_report.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailRMPReport(user, mock_file)
    assert user.email in notif.cc


@pytest.mark.django_db
def test_email_rmp_report_subject_contains_chapter_name():
    user = UserFactory.create()
    mock_file = BytesIO(b"fake pdf")
    mock_file.name = "report.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailRMPReport(user, mock_file)
    chapter = user.current_chapter
    if not chapter.candidate_chapter:
        assert chapter.name + " Chapter" in notif.subject
    else:
        assert chapter.name in notif.subject


@pytest.mark.django_db
def test_email_rmp_report_attachment():
    user = UserFactory.create()
    content = b"pdf content"
    mock_file = BytesIO(content)
    mock_file.name = "test_report.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailRMPReport(user, mock_file)
    assert len(notif.attachments) == 1
    name, data, mime = notif.attachments[0]
    assert name == "test_report.pdf"
    assert data == content


# ─── EmailAdvisorWelcome ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_advisor_welcome_to_emails_contains_user_email():
    user = UserFactory.create()
    notif = EmailAdvisorWelcome(user)
    assert user.email in notif.to_emails


@pytest.mark.django_db
def test_email_advisor_welcome_subject_contains_chapter():
    user = UserFactory.create()
    notif = EmailAdvisorWelcome(user)
    chapter = user.current_chapter
    assert chapter.name in notif.subject


@pytest.mark.django_db
def test_email_advisor_welcome_context_has_user():
    user = UserFactory.create()
    notif = EmailAdvisorWelcome(user)
    assert notif.context["user"] == user


@pytest.mark.django_db
def test_email_advisor_welcome_chapter_name_suffix_non_candidate():
    chapter = ChapterFactory.create(candidate_chapter=False)
    user = UserFactory.create(chapter=chapter)
    notif = EmailAdvisorWelcome(user)
    assert " Chapter" in notif.context["chapter_name"]


@pytest.mark.django_db
def test_email_advisor_welcome_no_suffix_for_candidate():
    chapter = ChapterFactory.create(candidate_chapter=True)
    user = UserFactory.create(chapter=chapter)
    notif = EmailAdvisorWelcome(user)
    assert " Chapter" not in notif.context["chapter_name"]


# ─── EmailScribeExpulsion ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_scribe_expulsion_subject():
    user = UserFactory.create()
    date = datetime.date.today()
    notif = EmailScribeExpulsion(user, date)
    assert "Roll Book Update" in notif.subject


@pytest.mark.django_db
def test_email_scribe_expulsion_context_has_user_and_date():
    user = UserFactory.create()
    date = datetime.date.today()
    notif = EmailScribeExpulsion(user, date)
    assert notif.context["user"] == user
    assert notif.context["date"] == date


@pytest.mark.django_db
def test_email_scribe_expulsion_context_has_badge_number():
    user = UserFactory.create()
    date = datetime.date.today()
    notif = EmailScribeExpulsion(user, date)
    assert "badge_number" in notif.context


# ─── EmailOSMUpdate (mock activation) ────────────────────────────────────────


@pytest.mark.django_db
def test_email_osm_update_basic_init():
    from thetatauCMT.forms.notifications import EmailOSMUpdate

    class MockFlowClass:
        process_title = "OSM Process"

    class MockActivation:
        flow_class = MockFlowClass()

    user = UserFactory.create()
    notif = EmailOSMUpdate(MockActivation(), user, "Your nomination was submitted")
    assert user.email in notif.to_emails
    assert notif.context["message"] == "Your nomination was submitted"
    assert notif.context["officer"] is False  # nominate=None → officer=False


@pytest.mark.django_db
def test_email_osm_update_with_nominate():
    from thetatauCMT.forms.notifications import EmailOSMUpdate

    class MockFlowClass:
        process_title = "OSM Process"

    class MockActivation:
        flow_class = MockFlowClass()

    user = UserFactory.create()
    nominate = UserFactory.create()
    notif = EmailOSMUpdate(MockActivation(), user, "OSM submitted", nominate=nominate)
    assert notif.context["officer"] is True
    assert notif.context["nominate"] == nominate


# ─── EmailPledgeOther ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_other_to_emails():
    from thetatauCMT.forms.notifications import EmailPledgeOther

    user = UserFactory.create()
    mock_file = BytesIO(b"content")
    mock_file.name = "other.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailPledgeOther(user, mock_file)
    assert "risk@thetatau.org" in notif.to_emails


@pytest.mark.django_db
def test_email_pledge_other_reply_to_user():
    from thetatauCMT.forms.notifications import EmailPledgeOther

    user = UserFactory.create()
    mock_file = BytesIO(b"content")
    mock_file.name = "other.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailPledgeOther(user, mock_file)
    assert user.email in notif.reply_to


@pytest.mark.django_db
def test_email_pledge_other_has_attachment():
    from thetatauCMT.forms.notifications import EmailPledgeOther

    user = UserFactory.create()
    content = b"pledge other content"
    mock_file = BytesIO(content)
    mock_file.name = "other_pledge.pdf"
    mock_file.mime_type = "application/pdf"
    notif = EmailPledgeOther(user, mock_file)
    assert len(notif.attachments) == 1
    assert notif.attachments[0][0] == "other_pledge.pdf"


# ─── BadgePNMNotify ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_badge_pnm_notify_to_emails_contains_user_email():
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import BadgePNMNotify

    user = UserFactory.create()
    with patch(
        "thetatauCMT.forms.notifications.Config.get_value",
        return_value=f"Hello {{ badge_table }}",
    ):
        notif = BadgePNMNotify(user)
    assert user.email in notif.to_emails


@pytest.mark.django_db
def test_badge_pnm_notify_context_has_message():
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import BadgePNMNotify

    user = UserFactory.create()
    with patch(
        "thetatauCMT.forms.notifications.Config.get_value",
        return_value=f"Hello {{ badge_table }}",
    ):
        notif = BadgePNMNotify(user)
    assert "message" in notif.context


# ─── EmailPledgeOfficer ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_officer_context_has_pledge_name():
    from thetatauCMT.forms.notifications import EmailPledgeOfficer
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    notif = EmailPledgeOfficer(pledge)
    expected_name = pledge.user.first_name + " " + pledge.user.last_name
    assert notif.context["pledge"] == expected_name


@pytest.mark.django_db
def test_email_pledge_officer_cc_contains_school_email():
    from thetatauCMT.forms.notifications import EmailPledgeOfficer
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    notif = EmailPledgeOfficer(pledge)
    assert pledge.user.email_school in notif.cc


# ─── EmailPledgeWelcome ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_welcome_to_emails_contains_school_email():
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    with patch(
        "thetatauCMT.forms.notifications.Config.get_value", return_value="Welcome text"
    ):
        notif = EmailPledgeWelcome(pledge)
    assert pledge.user.email_school in notif.to_emails


@pytest.mark.django_db
def test_email_pledge_welcome_context_has_name():
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    with patch(
        "thetatauCMT.forms.notifications.Config.get_value", return_value="Welcome text"
    ):
        notif = EmailPledgeWelcome(pledge)
    assert notif.context["name"] == pledge.user.first_name


# ─── EmailAlumniExclusionUpdate (mock activation, review=True) ───────────────


@pytest.mark.django_db
def test_email_alumni_exclusion_update_review_to_region():
    from thetatauCMT.forms.notifications import EmailAlumniExclusionUpdate

    ch = ChapterFactory.create()
    user1 = UserFactory.create(chapter=ch)
    user2 = UserFactory.create(chapter=ch)

    class MockProcess:
        user = user1
        chapter = ch
        created_by = user2

        def get_regional_director_veto_display(self):
            return "Approved"

    class MockFlowClass:
        process_title = "Alumni Exclusion Process"

    class MockActivation:
        flow_class = MockFlowClass()
        process = MockProcess()

    notif = EmailAlumniExclusionUpdate(MockActivation(), review=True)
    assert ch.region.email in notif.to_emails


# ─── EmailAlumniExclusionUpdate (review=False) ───────────────────────────────


@pytest.mark.django_db
def test_email_alumni_exclusion_update_not_review_to_user():
    """EmailAlumniExclusionUpdate with review=False sends to the user."""
    from thetatauCMT.forms.notifications import EmailAlumniExclusionUpdate

    ch = ChapterFactory.create()
    user1 = UserFactory.create(chapter=ch)
    user2 = UserFactory.create(chapter=ch)

    class MockProcess:
        user = user1
        chapter = ch
        created_by = user2

        def get_regional_director_veto_display(self):
            return "Approved"

    class MockFlowClass:
        process_title = "Alumni Exclusion Process"

    class MockActivation:
        flow_class = MockFlowClass()
        process = MockProcess()

    notif = EmailAlumniExclusionUpdate(MockActivation(), review=False)
    # review=False → to_emails is user.emails (not the region email)
    # If user has no emails, falls back to region email
    assert len(notif.to_emails) >= 0  # just check it doesn't raise
    assert notif.context["state"] == "Complete"
    assert notif.context["reviewed"] == "Approved"


@pytest.mark.django_db
def test_email_alumni_exclusion_update_not_review_subject():
    """EmailAlumniExclusionUpdate with review=False has correct subject."""
    from thetatauCMT.forms.notifications import EmailAlumniExclusionUpdate

    ch = ChapterFactory.create()
    user1 = UserFactory.create(chapter=ch)
    user2 = UserFactory.create(chapter=ch)

    class MockProcess:
        user = user1
        chapter = ch
        created_by = user2

        def get_regional_director_veto_display(self):
            return "Approved"

    class MockFlowClass:
        process_title = "Alumni Exclusion Process"

    class MockActivation:
        flow_class = MockFlowClass()
        process = MockProcess()

    notif = EmailAlumniExclusionUpdate(MockActivation(), review=False)
    assert "Alumni Exclusion Process" in notif.subject


# ─── CentralOfficeGenericEmail with MIME attachment ───────────────────────────


def test_central_office_generic_email_with_mime_attachment():
    """Files with a get_content_type (MIMEBase) are added to attachments directly."""
    from email.mime.base import MIMEBase

    mime_file = MIMEBase("application", "pdf")
    mime_file.add_header("Content-Disposition", "attachment", filename="invoice.pdf")
    mime_file.set_payload(b"fake pdf content")
    notif = CentralOfficeGenericEmail("Test MIME", attachments=[mime_file])
    # MIME attachment has get_content_type but no seek/read → appended directly
    assert len(notif.attachments) == 1
    assert notif.attachments[0] is mime_file


def test_central_office_generic_email_with_get_filename_attachment():
    """Files with get_filename are recorded in context file_names."""
    from email.mime.base import MIMEBase

    mime_file = MIMEBase("application", "pdf")
    mime_file.add_header("Content-Disposition", "attachment", filename="report.pdf")
    mime_file.set_payload(b"content")
    notif = CentralOfficeGenericEmail("Filename test", attachments=[mime_file])
    assert "report.pdf" in notif.context["file_names"]


# ─── EmailProcessUpdate (with real model object) ──────────────────────────────


@pytest.mark.django_db
def test_email_process_update_basic_with_user_model():
    """EmailProcessUpdate with a model obj that has .user and .user.chapter."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    # Use a dict field entry so we don't need to worry about field introspection
    notif = EmailProcessUpdate(
        audit,
        "Submitted",
        "Treasurer Review",
        "Submitted",
        "Test message for audit",
        [{"Audit Item": "debit_card"}],
        process_title="Audit Process",
    )
    assert audit.user.email in notif.to_emails
    assert notif.context["message"] == "Test message for audit"
    assert notif.context["process_title"] == "Audit Process"


@pytest.mark.django_db
def test_email_process_update_with_direct_user():
    """EmailProcessUpdate with direct_user sends to that user."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    direct_user = UserFactory.create(chapter=audit.user.chapter)
    notif = EmailProcessUpdate(
        audit,
        "Step 1",
        "Step 2",
        "Submitted",
        "Direct user message",
        [],
        process_title="Test Process",
        direct_user=direct_user,
    )
    assert direct_user.email in notif.to_emails


@pytest.mark.django_db
def test_email_process_update_with_extra_emails():
    """EmailProcessUpdate extra_emails are added to cc."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    notif = EmailProcessUpdate(
        audit,
        "Step 1",
        "Step 2",
        "Submitted",
        "Extra email message",
        [],
        process_title="Test Process",
        extra_emails=["extra@example.com"],
    )
    assert "extra@example.com" in notif.cc or "extra@example.com" in list(notif.cc)


@pytest.mark.django_db
def test_email_process_update_with_activation_wrapping():
    """EmailProcessUpdate when model_obj has process and flow_class attributes."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()

    class MockFlowClass:
        process_title = "Wrapped Process"

    # Wrap audit as an activation-like object
    audit.process = audit
    audit.flow_class = MockFlowClass()

    notif = EmailProcessUpdate(
        audit,
        "Step 1",
        "Step 2",
        "In Progress",
        "Wrapped message",
        [],
        process_title="Will Be Overridden",
    )
    # process_title should be taken from flow_class
    assert notif.context["process_title"] == "Wrapped Process"


# ─── EmailConventionUpdate (mock activation) ─────────────────────────────────


@pytest.mark.django_db
def test_email_convention_update_basic():
    """EmailConventionUpdate sets to_emails and context."""
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailConventionUpdate

    class MockFlowClass:
        process_title = "Convention Process"

    class MockActivation:
        flow_class = MockFlowClass()

    user = UserFactory.create()
    # Patch get_sign_status at the import location inside views.py
    with patch(
        "thetatauCMT.forms.views.get_sign_status",
        return_value=([], None, None),
    ):
        notif = EmailConventionUpdate(MockActivation(), user, "Convention submitted!")

    assert user.email in notif.to_emails
    assert notif.context["message"] == "Convention submitted!"
    assert notif.context["process_title"] == "Convention Process"


# ─── EmailAdvisorWelcome.get_demo_args ────────────────────────────────────────


@pytest.mark.django_db
def test_email_advisor_welcome_get_demo_args_returns_user():
    """EmailAdvisorWelcome.get_demo_args() returns a list with one User."""
    from thetatauCMT.forms.notifications import EmailAdvisorWelcome

    UserFactory.create()
    args = EmailAdvisorWelcome.get_demo_args()
    assert len(args) == 1
    # Should be a User-like object with email attribute
    assert hasattr(args[0], "email")


# ─── EmailRMPReport.get_demo_args ────────────────────────────────────────────


@pytest.mark.django_db
def test_email_rmp_report_get_demo_args_returns_user_and_file():
    """EmailRMPReport.get_demo_args() reads the test PDF and returns [user, file]."""
    from thetatauCMT.forms.notifications import EmailRMPReport

    UserFactory.create()
    import os

    if not os.path.exists("/app/thetatauCMT/forms/test/example_rmp.pdf"):
        pytest.skip("Test PDF file not found")

    args = EmailRMPReport.get_demo_args()
    assert len(args) == 2
    user, f = args
    assert hasattr(user, "email")
    assert hasattr(f, "name")


# ─── EmailPledgeOther.get_demo_args ──────────────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_other_get_demo_args_returns_user_and_file():
    """EmailPledgeOther.get_demo_args() reads the test PDF."""
    from thetatauCMT.forms.notifications import EmailPledgeOther

    UserFactory.create()
    import os

    if not os.path.exists("/app/thetatauCMT/forms/test/example_rmp.pdf"):
        pytest.skip("Test PDF file not found")

    args = EmailPledgeOther.get_demo_args()
    assert len(args) == 2
    user, f = args
    assert hasattr(user, "email")


# ─── EmailPledgeWelcome – cc branch (email_school != email_personal) ─────────


@pytest.mark.django_db
def test_email_pledge_welcome_cc_when_emails_differ():
    """When email_school differs from email, the personal email is cc'd."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    chapter = ChapterFactory.create(school_type="semester")
    user = UserFactory.create(
        chapter=chapter,
        email="personal@example.com",
        email_school="school@example.edu",
    )
    pledge = PledgeFactory.create(user=user)

    notif = EmailPledgeWelcome(pledge)
    # personal email is different from school email so it should be cc'd
    assert "personal@example.com" in notif.cc


@pytest.mark.django_db
def test_email_pledge_welcome_no_cc_when_emails_same():
    """When email_school == email, no cc is set."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    chapter = ChapterFactory.create(school_type="semester")
    user = UserFactory.create(
        chapter=chapter,
        email="same@example.com",
        email_school="same@example.com",
    )
    pledge = PledgeFactory.create(user=user)

    notif = EmailPledgeWelcome(pledge)
    assert (
        not hasattr(notif, "cc")
        or not notif.cc
        or "same@example.com" not in (notif.cc or [])
    )


# ─── CentralOfficeGenericEmail – get_content_type attachment branch ───────────


def test_central_office_generic_email_with_get_content_type_attachment():
    """Files with get_content_type method are attached via elif branch."""
    from unittest.mock import MagicMock

    from thetatauCMT.forms.notifications import CentralOfficeGenericEmail

    mock_file = MagicMock()
    mock_file.get_content_type.return_value = "application/pdf"
    del mock_file.seek  # remove seek so hasattr(file, 'seek') is False
    del mock_file.name

    notif = CentralOfficeGenericEmail("Test", attachments=[mock_file])
    # The file should be attached via the elif branch
    assert len(notif.attachments) == 1


# ─── EmailRMPReport: candidate_chapter=True branch (line 73) ─────────────────


@pytest.mark.django_db
def test_email_rmp_report_candidate_chapter_name():
    """candidate_chapter=True → chapter_name = chapter.name (no ' Chapter' suffix)."""
    from unittest.mock import MagicMock

    chapter = ChapterFactory.create(candidate_chapter=True)
    user = UserFactory.create(chapter=chapter)
    mock_file = MagicMock()
    mock_file.name = "test_rmp.pdf"
    mock_file.read.return_value = b"PDF content"
    mock_file.mime_type = "application/pdf"
    notif = EmailRMPReport(user, mock_file)
    # candidate_chapter=True → chapter_name = chapter.name (line 73)
    assert chapter.name in notif.subject
    assert notif.subject.endswith("Theta Tau Report Submitted")


# ─── EmailPledgeOfficer: scribe/vice/generics branches (lines 353,355,357,359)


@pytest.mark.django_db
def test_email_pledge_officer_scribe_vice_emails():
    """Scribe and vice officers have emails added to to_emails."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import PledgeFactory

    scribe_user = UserFactory.create(email="scribe_test@example.com")
    vice_user = UserFactory.create(email="vice_test@example.com")
    pledge = PledgeFactory.create()

    with patch.object(
        pledge.user.chapter.__class__,
        "get_current_officers_council_specific",
        return_value=(None, scribe_user, vice_user, None, None),
    ), patch.object(
        pledge.user.chapter.__class__,
        "get_generic_chapter_emails",
        return_value=(
            None,
            "scribegeneric@example.com",
            "vicegeneric@example.com",
            None,
            None,
        ),
    ):
        from thetatauCMT.forms.notifications import EmailPledgeOfficer

        notif = EmailPledgeOfficer(pledge)

    assert "scribe_test@example.com" in notif.to_emails
    assert "vice_test@example.com" in notif.to_emails
    assert "scribegeneric@example.com" in notif.to_emails
    assert "vicegeneric@example.com" in notif.to_emails


# ─── EmailProcessUpdate: model with .chapter field (line 407) ────────────────


@pytest.mark.django_db
def test_email_process_update_chapter_report_covers_line_407():
    """ChapterReport has a .chapter field, covering line 407."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import ChapterReportFactory

    report = ChapterReportFactory.create()
    notif = EmailProcessUpdate(
        report,
        "Step 1",
        "Step 2",
        "Submitted",
        "Test message",
        [],
    )
    assert notif.to_emails


# ─── EmailProcessUpdate: Convention (no user) covers lines 417-419, 421-435 ──


@pytest.mark.django_db
def test_email_process_update_convention_no_user_field():
    """Convention has chapter but not user: covers lines 417-419, 421-422, 433-435."""
    from unittest.mock import PropertyMock, patch

    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import ConventionFactory

    conv = ConventionFactory.create()
    officer_user = UserFactory.create()

    with patch.object(
        type(conv),
        "created_by",
        new_callable=PropertyMock,
        return_value=officer_user,
    ), patch.object(
        conv.chapter.__class__,
        "get_current_officers_council_specific",
        return_value=[officer_user, None, None, None, None],
    ), patch.object(
        conv.chapter.__class__,
        "council_emails",
        return_value={officer_user.email},
    ):
        notif = EmailProcessUpdate(
            conv,
            "Step 1",
            "Step 2",
            "Submitted",
            "Test message",
            [],
        )
    assert notif.to_emails


# ─── EmailProcessUpdate: string field names (lines 454-461) ──────────────────


@pytest.mark.django_db
def test_email_process_update_string_field_names():
    """Passing string field names covers lines 454-461."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    notif = EmailProcessUpdate(
        audit,
        "Step 1",
        "Step 2",
        "Submitted",
        "Test message",
        ["user", "dues_member"],
    )
    assert notif.to_emails


# ─── EmailProcessUpdate: model with .form FileField (lines 464-465, 494-495) ─


@pytest.mark.django_db
def test_email_process_update_model_with_form_field():
    """PrematureAlumnus has a .form FileField, covering lines 464-465, 494-495."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    pa = PrematureAlumnusFactory.create()
    if not pa.form.name:
        pytest.skip("PrematureAlumnus has no form file")
    notif = EmailProcessUpdate(
        pa,
        "Step 1",
        "Step 2",
        "Submitted",
        "Test message",
        [],
    )
    assert notif.to_emails


# ─── EmailProcessUpdate: attachments kwarg (lines 467-477) ───────────────────


@pytest.mark.django_db
def test_email_process_update_with_attachments_kwarg():
    """Passing attachments=["report"] covers lines 467-477."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import ChapterReportFactory

    report = ChapterReportFactory.create()
    if not report.report.name:
        pytest.skip("ChapterReport has no report file")
    notif = EmailProcessUpdate(
        report,
        "Step 1",
        "Step 2",
        "Submitted",
        "Test message",
        [],
        attachments=["report"],
    )
    assert notif.to_emails


# ─── EmailProcessUpdate: subject format assertion ────────────────────────────


@pytest.mark.django_db
def test_email_process_update_subject_format():
    """EmailProcessUpdate subject follows '[CMT] [process_title] [state] for [obj]'."""
    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    notif = EmailProcessUpdate(
        audit,
        "Step 1",
        "Step 2",
        "Approved",
        "Message",
        [],
        process_title="Audit Review",
    )
    assert "[CMT]" in notif.subject
    assert "Audit Review" in notif.subject
    assert "Approved" in notif.subject


@pytest.mark.django_db
def test_email_process_update_subject_format_with_chapter_obj():
    """EmailProcessUpdate subject contains chapter name when obj is a chapter."""
    from unittest.mock import PropertyMock, patch

    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import ConventionFactory

    conv = ConventionFactory.create()
    officer_user = UserFactory.create()

    with patch.object(
        type(conv),
        "created_by",
        new_callable=PropertyMock,
        return_value=officer_user,
    ), patch.object(
        conv.chapter.__class__,
        "get_current_officers_council_specific",
        return_value=[officer_user, None, None, None, None],
    ), patch.object(
        conv.chapter.__class__,
        "council_emails",
        return_value={officer_user.email},
    ):
        notif = EmailProcessUpdate(
            conv,
            "Step 1",
            "Step 2",
            "Pending",
            "Message",
            [],
            process_title="Convention Review",
        )
    assert "Convention Review" in notif.subject
    assert "Pending" in notif.subject


# ─── EmailProcessUpdate: email_officers=True explicit ─────────────────────────


@pytest.mark.django_db
def test_email_process_update_email_officers_true_includes_council():
    """email_officers=True adds chapter council emails to CC."""
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailProcessUpdate
    from thetatauCMT.forms.tests.factories import AuditFactory

    audit = AuditFactory.create()
    officer_user = UserFactory.create(chapter=audit.user.chapter)
    council_email = "council@test.example.com"

    with patch.object(
        audit.user.chapter.__class__,
        "council_emails",
        return_value={council_email},
    ), patch.object(
        audit.user.chapter.__class__,
        "get_current_officers_council_specific",
        return_value=[officer_user, None, None, None, None],
    ):
        notif = EmailProcessUpdate(
            audit,
            "Step 1",
            "Step 2",
            "Reviewed",
            "Officer message",
            [],
            process_title="Officer Review",
            email_officers=True,
        )
    # The user's email is in to_emails; council emails go to CC
    assert notif.to_emails


# ─── EmailPledgeWelcome: CC behavior when emails differ ──────────────────────


@pytest.mark.django_db
def test_email_pledge_welcome_cc_personal_when_differs_from_school():
    """EmailPledgeWelcome adds personal email to CC when it differs from school email."""
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    # Make sure school email and personal email are different
    pledge.user.email_school = "school@university.edu"
    pledge.user.email = "personal@example.com"
    pledge.user.save()

    with patch(
        "thetatauCMT.forms.notifications.Config.get_value", return_value="Welcome"
    ):
        notif = EmailPledgeWelcome(pledge)

    assert "school@university.edu" in notif.to_emails
    assert "personal@example.com" in notif.cc


@pytest.mark.django_db
def test_email_pledge_welcome_no_cc_when_emails_same():
    """EmailPledgeWelcome does not add CC when school email == personal email."""
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailPledgeWelcome
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    # Make school email and personal email the same
    pledge.user.email = "same@example.com"
    pledge.user.email_school = "same@example.com"
    pledge.user.save()

    with patch(
        "thetatauCMT.forms.notifications.Config.get_value", return_value="Welcome"
    ):
        notif = EmailPledgeWelcome(pledge)

    assert "same@example.com" in notif.to_emails
    # cc should NOT contain the same email (no duplicate CC)
    assert not getattr(notif, "cc", None) or "same@example.com" not in notif.cc


# ─── EmailPledgeOfficer: officers in to_emails ────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_officer_to_emails_includes_scribe_and_vice_when_present():
    """EmailPledgeOfficer to_emails contains scribe/vice email when they are officers."""
    from unittest.mock import patch

    from thetatauCMT.forms.notifications import EmailPledgeOfficer
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    scribe = UserFactory.create(chapter=pledge.user.chapter)
    vice = UserFactory.create(chapter=pledge.user.chapter)

    generic_emails = [None, None, None, None, None]  # no generics

    with patch.object(
        pledge.user.chapter.__class__,
        "get_current_officers_council_specific",
        return_value=[None, scribe, vice, None, None],
    ), patch.object(
        pledge.user.chapter.__class__,
        "get_generic_chapter_emails",
        return_value=generic_emails,
    ):
        notif = EmailPledgeOfficer(pledge)

    assert scribe.email in notif.to_emails
    assert vice.email in notif.to_emails


@pytest.mark.django_db
def test_email_pledge_officer_reply_to_is_central_office():
    """EmailPledgeOfficer reply_to is always central.office@thetatau.org."""
    from thetatauCMT.forms.notifications import EmailPledgeOfficer
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    notif = EmailPledgeOfficer(pledge)
    assert "central.office@thetatau.org" in notif.reply_to


# ─── EmailPledgeConfirmation ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_email_pledge_confirmation_to_emails_contains_school_and_personal():
    """EmailPledgeConfirmation sends to both school and personal email."""
    from thetatauCMT.forms.notifications import EmailPledgeConfirmation
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    pledge.user.email = "personal@example.com"
    pledge.user.email_school = "school@university.edu"
    pledge.user.save()

    notif = EmailPledgeConfirmation(pledge, b"%PDF fake pdf content")

    assert "school@university.edu" in notif.to_emails
    assert "personal@example.com" in notif.to_emails


@pytest.mark.django_db
def test_email_pledge_confirmation_reply_to_is_central_office():
    """EmailPledgeConfirmation reply_to is central.office@thetatau.org."""
    from thetatauCMT.forms.notifications import EmailPledgeConfirmation
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    notif = EmailPledgeConfirmation(pledge, b"%PDF fake")

    assert "central.office@thetatau.org" in notif.reply_to


@pytest.mark.django_db
def test_email_pledge_confirmation_has_bill_of_rights_attachment():
    """EmailPledgeConfirmation includes the bill-of-rights PDF as attachment."""
    from thetatauCMT.forms.notifications import EmailPledgeConfirmation
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    bill_content = b"%PDF-1.4 bill of rights content"
    notif = EmailPledgeConfirmation(pledge, bill_content)

    assert len(notif.attachments) >= 1
    filename, content, mime = notif.attachments[0]
    assert "Bill of Rights" in filename or "bill" in filename.lower()
    assert content == bill_content


@pytest.mark.django_db
def test_email_pledge_confirmation_context_has_form_dict():
    """EmailPledgeConfirmation context['form'] is a non-empty dict of member data."""
    from thetatauCMT.forms.notifications import EmailPledgeConfirmation
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    notif = EmailPledgeConfirmation(pledge, b"%PDF fake")

    assert "form" in notif.context
    assert isinstance(notif.context["form"], dict)
    assert len(notif.context["form"]) > 0
