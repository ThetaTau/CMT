from datetime import datetime, timezone
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.users.tests.factories import UserFactory

_CREDS = {"MAILJET_API_KEY": "k", "MAILJET_SECRET_KEY": "s"}


def _make_natoff(user):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    return user


@pytest.mark.django_db
def test_communication_requires_natoff(auto_login_user):
    client, _ = auto_login_user()  # plain member
    resp = client.get(reverse("email_tracking:member_communication"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_communication_natoff_can_access(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    resp = client.get(reverse("email_tracking:member_communication"))
    assert resp.status_code == 200
    assert b"Member Email Communication" in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_lookup_by_email(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    fake = {
        "data": [
            {
                "ID": "555",
                "arrived_at": datetime(2018, 1, 1, tzinfo=timezone.utc),
                "Status": "opened",
                "Subject": "Hello There",
            }
        ],
        "total": 1,
        "count": 1,
    }
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value=fake,
        ) as patched,
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=1,
        ),
    ):
        resp = client.get(
            reverse("email_tracking:member_communication_results"),
            {"email": "target@example.com"},
        )
    assert resp.status_code == 200
    patched.assert_called_once()
    assert patched.call_args[0][0] == "target@example.com"
    assert b"Hello There" in resp.content
    assert b"target@example.com" in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_lookup_by_member_uses_member_emails(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    target = UserFactory.create(email="picked@example.com", email_school="school@edu.example")
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value={"data": [], "total": 0, "count": 0},
        ) as patched,
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=0,
        ),
    ):
        resp = client.get(reverse("email_tracking:member_communication_results"), {"member": target.pk})
    assert resp.status_code == 200
    called_emails = {c.args[0] for c in patched.call_args_list}
    assert "picked@example.com" in called_emails
    assert "school@edu.example" in called_emails


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_paginates(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    fake = {
        "data": [
            {
                "ID": str(i),
                "arrived_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": f"Subject {i}",
            }
            for i in range(25)
        ],
        "total": 60,
        "count": 25,
    }
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value=fake,
        ) as patched,
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=200,
        ),
    ):
        resp = client.get(
            reverse("email_tracking:member_communication_results"),
            {"email": "t@example.com", "page": "2"},
        )
    assert resp.status_code == 200
    # page 2 -> offset 25
    assert patched.call_args.kwargs["offset"] == 25
    assert patched.call_args.kwargs["limit"] == 25
    assert b"Next" in resp.content
    assert b"page=3" in resp.content
    assert b"page=1" in resp.content
    # accurate total from countOnly is shown
    assert b"200" in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_next_available_when_count_unknown(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    # A full page (count == page_size) with no reliable total -> Next still works.
    fake = {
        "data": [
            {
                "ID": str(i),
                "arrived_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": f"S{i}",
            }
            for i in range(25)
        ],
        "total": 25,
        "count": 25,
    }
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value=fake,
        ),
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=None,
        ),
    ):
        resp = client.get(reverse("email_tracking:member_communication_results"), {"email": "t@example.com"})
    assert resp.status_code == 200
    assert b"on this page" in resp.content
    assert b"page=2" in resp.content


@pytest.mark.django_db
def test_communication_uses_internal_tracking_when_api_unconfigured(auto_login_user):
    from thetatauCMT.email_tracking.models import TrackedEmail

    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    TrackedEmail.objects.create(
        message_id="9001",
        recipient="local@example.com",
        subject="Local Only Message",
        open_count=2,
    )
    resp = client.get(reverse("email_tracking:member_communication_results"), {"email": "local@example.com"})
    assert resp.status_code == 200
    assert b"Local Only Message" in resp.content
    assert b"Internal" in resp.content


@pytest.mark.django_db
def test_communication_warns_when_mailjet_not_configured(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    resp = client.get(reverse("email_tracking:member_communication"), {"email": "x@example.com"})
    assert resp.status_code == 200
    assert b"not configured" in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_message_history_json(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    events = [
        {"EventType": "sent", "event_at": datetime(2019, 1, 8, tzinfo=timezone.utc)},
        {"EventType": "opened", "event_at": None},
    ]
    with mock.patch(
        "thetatauCMT.email_tracking.mailjet_api.get_message_history",
        return_value=events,
    ):
        resp = client.get(reverse("email_tracking:message_history", args=["999"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] == "999"
    assert data["events"][0]["event_type"] == "sent"
    assert data["events"][0]["event_at"] is not None
    assert data["events"][1]["event_at"] is None


@pytest.mark.django_db
def test_message_history_falls_back_to_internal_events(auto_login_user):
    from django.utils import timezone

    from thetatauCMT.email_tracking.models import EmailTrackingEvent

    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    EmailTrackingEvent.objects.create(
        message_id="7001",
        recipient="x@example.com",
        event_type="opened",
        timestamp=timezone.now(),
    )
    # No Mailjet creds configured -> history comes from internal tracking.
    resp = client.get(reverse("email_tracking:message_history", args=["7001"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"][0]["event_type"] == "opened"
    assert data["events"][0]["source"] == "Internal"


@pytest.mark.django_db
def test_message_history_requires_natoff(auto_login_user):
    client, _ = auto_login_user()  # plain member
    resp = client.get(reverse("email_tracking:message_history", args=["1"]))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_profile_shows_communication_link_for_natoff(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    target = UserFactory.create()
    resp = client.get(reverse("users:profile", args=[target.username]))
    assert resp.status_code == 200
    assert reverse("email_tracking:member_communication").encode() in resp.content
    assert f"member={target.id}".encode() in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_gathers_all_user_emails(auto_login_user):
    from allauth.account.models import EmailAddress

    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    target = UserFactory.create(email="primary@example.com", email_school="school@edu.example")
    EmailAddress.objects.create(user=target, email="extra@personal.com", verified=True)
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value={"data": [], "total": 0, "count": 0},
        ) as patched,
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=0,
        ),
    ):
        resp = client.get(reverse("email_tracking:member_communication_results"), {"member": target.pk})
    assert resp.status_code == 200
    called = {c.args[0] for c in patched.call_args_list}
    assert "primary@example.com" in called
    assert "school@edu.example" in called
    assert "extra@personal.com" in called


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_subject_search_filters_results(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    fake = {
        "data": [
            {
                "ID": "1",
                "arrived_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": "Your invoice is ready",
            },
            {
                "ID": "2",
                "arrived_at": datetime(2020, 1, 2, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": "Welcome to Theta Tau",
            },
        ],
        "total": 2,
        "count": 2,
    }
    with mock.patch(
        "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
        return_value=fake,
    ):
        resp = client.get(
            reverse("email_tracking:member_communication_results"),
            {"email": "t@example.com", "subject": "invoice"},
        )
    assert resp.status_code == 200
    assert b"Your invoice is ready" in resp.content
    assert b"Welcome to Theta Tau" not in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_communication_date_search_filters_results(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    fake = {
        "data": [
            {
                "ID": "1",
                "arrived_at": datetime(2020, 3, 15, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": "In range",
            },
            {
                "ID": "2",
                "arrived_at": datetime(2019, 1, 1, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": "Too old",
            },
        ],
        "total": 2,
        "count": 2,
    }
    with mock.patch(
        "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
        return_value=fake,
    ):
        resp = client.get(
            reverse("email_tracking:member_communication_results"),
            {"email": "t@example.com", "date_from": "2020-01-01"},
        )
    assert resp.status_code == 200
    assert b"In range" in resp.content
    assert b"Too old" not in resp.content


@pytest.mark.django_db
def test_communication_subject_search_over_internal_tracking(auto_login_user):
    from thetatauCMT.email_tracking.models import TrackedEmail

    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    TrackedEmail.objects.create(message_id="a1", recipient="local@example.com", subject="Invoice attached")
    TrackedEmail.objects.create(message_id="a2", recipient="local@example.com", subject="Meeting notes")
    # No Mailjet creds -> search runs over the internal tracking (SQL icontains).
    resp = client.get(
        reverse("email_tracking:member_communication_results"),
        {"email": "local@example.com", "subject": "invoice"},
    )
    assert resp.status_code == 200
    assert b"Invoice attached" in resp.content
    assert b"Meeting notes" not in resp.content


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_shell_page_does_not_call_mailjet(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    with (
        mock.patch("thetatauCMT.email_tracking.mailjet_api.get_messages_for_email") as messages,
        mock.patch("thetatauCMT.email_tracking.mailjet_api.get_message_count") as count,
    ):
        resp = client.get(
            reverse("email_tracking:member_communication"),
            {"email": "target@example.com"},
        )
    assert resp.status_code == 200
    # The shell renders without touching the Mailjet API (table loads via AJAX).
    messages.assert_not_called()
    count.assert_not_called()
    assert b'id="comm-results"' in resp.content
    assert b'data-searched="1"' in resp.content


@pytest.mark.django_db
def test_results_endpoint_requires_natoff(auto_login_user):
    client, _ = auto_login_user()  # plain member
    resp = client.get(
        reverse("email_tracking:member_communication_results"),
        {"email": "x@example.com"},
    )
    assert resp.status_code == 302


@pytest.mark.django_db
@override_settings(ANYMAIL=_CREDS)
def test_results_endpoint_returns_fragment_only(auto_login_user):
    natoff = _make_natoff(UserFactory.create())
    client, _ = auto_login_user(user=natoff)
    fake = {
        "data": [
            {
                "ID": "9",
                "arrived_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "Status": "sent",
                "Subject": "Fragment Row",
            }
        ],
        "total": 1,
        "count": 1,
    }
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_messages_for_email",
            return_value=fake,
        ),
        mock.patch(
            "thetatauCMT.email_tracking.mailjet_api.get_message_count",
            return_value=1,
        ),
    ):
        resp = client.get(
            reverse("email_tracking:member_communication_results"),
            {"email": "t@example.com"},
        )
    assert resp.status_code == 200
    assert b"Fragment Row" in resp.content
    # It's a bare fragment: no base-page shell markup.
    assert b"Member Email Communication" not in resp.content
    assert b"<html" not in resp.content
