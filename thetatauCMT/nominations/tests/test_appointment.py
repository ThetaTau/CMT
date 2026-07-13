"""VWI-9: Appointment processing node (checklist)."""

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.services import add_to_natoff_lists, try_complete_appointment
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, done_task, start_nomination

pytestmark = pytest.mark.django_db


def _at_appointment(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "appointment")
    return process


def _processor_client(auto_login_user):
    processor = UserFactory.create(username="processor@example.com")
    Config.objects.create(key="AppointmentProcessor", value="processor@example.com", description="a")
    client, _ = auto_login_user(user=processor)
    return client, processor


def test_letter_upload_and_email_recorded(auto_login_user, mailoutbox):
    client, _ = _processor_client(auto_login_user)
    nominee = UserFactory.create()
    process = _at_appointment(nominee=nominee)
    url = reverse("nominations:appointment", kwargs={"process_pk": process.pk})

    client.post(url, {"action": "upload_letter", "appointment_letter": SimpleUploadedFile("letter.pdf", b"PDF")})
    process.refresh_from_db()
    assert process.appointment_letter

    mailoutbox.clear()
    client.post(url, {"action": "email_letter"})
    process.refresh_from_db()
    assert process.appointment_letter_sent_at is not None
    assert len(mailoutbox) == 1
    assert nominee.email in mailoutbox[0].to


def test_chapter_notification_triggered(auto_login_user, mailoutbox):
    client, _ = _processor_client(auto_login_user)
    nominee = UserFactory.create()
    nominee.chapter.email = "chapter@example.com"
    nominee.chapter.save(update_fields=["email"])
    process = _at_appointment(nominee=nominee)
    url = reverse("nominations:appointment", kwargs={"process_pk": process.pk})

    mailoutbox.clear()
    client.post(url, {"action": "notify_chapters"})
    process.refresh_from_db()
    assert process.chapters_notified is True
    assert any("chapter@example.com" in m.to for m in mailoutbox)


def test_ppm_and_natoff_steps_tracked(auto_login_user):
    client, _ = _processor_client(auto_login_user)
    nominee = UserFactory.create()
    process = _at_appointment(nominee=nominee)
    url = reverse("nominations:appointment", kwargs={"process_pk": process.pk})

    client.post(url, {"action": "order_ppm"})
    client.post(url, {"action": "add_natoff"})
    process.refresh_from_db()
    assert process.ppm_ordered is True
    assert process.added_to_natoff_lists is True
    # Integrated with the existing natoff group mechanism.
    assert Group.objects.get(name="natoff").user_set.filter(pk=nominee.pk).exists()


def test_completion_ends_flow_as_appointed(auto_login_user):
    client, _ = _processor_client(auto_login_user)
    nominee = UserFactory.create()
    process = _at_appointment(nominee=nominee)
    url = reverse("nominations:appointment", kwargs={"process_pk": process.pk})

    client.post(url, {"action": "upload_letter", "appointment_letter": SimpleUploadedFile("l.pdf", b"x")})
    client.post(url, {"action": "email_letter"})
    client.post(url, {"action": "notify_chapters"})
    client.post(url, {"action": "order_ppm"})
    assert active_task(process, NominationFlow.appointment) is not None  # not yet complete
    client.post(url, {"action": "add_natoff"})

    process.refresh_from_db()
    assert process.appointed is True
    assert active_task(process, NominationFlow.appointment) is None
    assert done_task(process, NominationFlow.appointed) is not None
    assert process.finished is not None


def test_try_complete_appointment_requires_all_items():
    process = _at_appointment()
    assert try_complete_appointment(process) is False
    # Satisfy every checklist item directly, then it completes.
    process.appointment_letter = SimpleUploadedFile("l.pdf", b"x")
    from django.utils import timezone

    process.appointment_letter_sent_at = timezone.now()
    process.chapters_notified = True
    process.ppm_ordered = True
    process.save()
    add_to_natoff_lists(process)
    assert try_complete_appointment(process) is True
    process.refresh_from_db()
    assert process.appointed is True


def test_appointment_view_permission_gating(auto_login_user):
    UserFactory.create(username="processor@example.com")
    Config.objects.create(key="AppointmentProcessor", value="processor@example.com", description="a")
    process = _at_appointment()
    url = reverse("nominations:appointment", kwargs={"process_pk": process.pk})
    client, _other = auto_login_user()
    assert client.get(url).status_code == 403
