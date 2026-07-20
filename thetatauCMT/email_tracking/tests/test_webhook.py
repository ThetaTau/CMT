import base64
import json

import pytest
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.email_tracking.models import EmailTrackingEvent, TrackedEmail


def _open_payload(message_id=111222333, email="a@b.com"):
    return {
        "event": "open",
        "email": email,
        "MessageID": message_id,
        "time": 1750000000,
        "agent": "Mozilla/5.0",
    }


def test_tracking_webhook_url_is_wired():
    # The anymail webhook must be reachable so Mailjet can post events.
    assert reverse("anymail:mailjet_tracking_webhook") == "/anymail/mailjet/tracking/"


@pytest.mark.django_db
def test_mailjet_tracking_webhook_records_open(client):
    url = reverse("anymail:mailjet_tracking_webhook")
    resp = client.post(url, data=json.dumps(_open_payload()), content_type="application/json")
    assert resp.status_code == 200
    assert EmailTrackingEvent.objects.filter(message_id="111222333", event_type="opened").exists()
    tracked = TrackedEmail.objects.get(message_id="111222333")
    assert tracked.open_count == 1
    assert tracked.recipient == "a@b.com"


@pytest.mark.django_db
@override_settings(ANYMAIL={"WEBHOOK_SECRET": "hookuser:hookpass"})
def test_webhook_rejects_missing_basic_auth(client):
    url = reverse("anymail:mailjet_tracking_webhook")
    resp = client.post(url, data=json.dumps(_open_payload(999)), content_type="application/json")
    assert resp.status_code == 400
    assert not EmailTrackingEvent.objects.filter(message_id="999").exists()


@pytest.mark.django_db
@override_settings(ANYMAIL={"WEBHOOK_SECRET": "hookuser:hookpass"})
def test_webhook_accepts_correct_basic_auth(client):
    url = reverse("anymail:mailjet_tracking_webhook")
    token = base64.b64encode(b"hookuser:hookpass").decode("ascii")
    resp = client.post(
        url,
        data=json.dumps(_open_payload(888)),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Basic {token}",
    )
    assert resp.status_code == 200
    assert EmailTrackingEvent.objects.filter(message_id="888").exists()
