import pytest
from django.test import override_settings

from thetatauCMT.email_tracking import mailerlite_api


class _FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.text = text

    def json(self):
        return self._data


class _FakeSession:
    """Routes GET calls by URL to canned responses; records the calls."""

    def __init__(self, subscriber=None, activity=None, subscriber_status=200):
        self._subscriber = subscriber
        self._activity = activity or []
        self._subscriber_status = subscriber_status
        self.calls = []
        self.posts = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/activity-log"):
            return _FakeResponse(200, {"data": self._activity})
        if self._subscriber_status == 404:
            return _FakeResponse(404, {}, "not found")
        return _FakeResponse(200, {"data": self._subscriber})

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        body = kwargs.get("json", {})
        data = {
            "id": "42",
            "email": body.get("email"),
            "status": body.get("status", "active"),
        }
        return _FakeResponse(201, {"data": data})


@override_settings(MAILERLITE_API_KEY="test-key")
def test_is_configured_true():
    assert mailerlite_api.is_configured() is True


@override_settings(MAILERLITE_API_KEY="")
def test_is_configured_false():
    assert mailerlite_api.is_configured() is False


@override_settings(MAILERLITE_API_KEY="test-key")
def test_get_subscriber_found_encodes_email():
    session = _FakeSession(subscriber={"id": "42", "email": "a@b.com"})
    sub = mailerlite_api.get_subscriber("a@b.com", session=session)
    assert sub["id"] == "42"
    assert "subscribers/a%40b.com" in session.calls[0][0]


@override_settings(MAILERLITE_API_KEY="test-key")
def test_get_subscriber_not_found_returns_none():
    session = _FakeSession(subscriber_status=404)
    assert mailerlite_api.get_subscriber("nope@b.com", session=session) is None


@override_settings(MAILERLITE_API_KEY="test-key")
def test_get_activity_for_email_looks_up_subscriber_then_activity():
    activity = [
        {
            "log_name": "email_open",
            "created_at": "2026-05-15 13:17:18",
            "properties": {"campaign_name": "Velocitas"},
        }
    ]
    session = _FakeSession(subscriber={"id": "42"}, activity=activity)
    result = mailerlite_api.get_activity_for_email("a@b.com", session=session)
    assert result[0]["log_name"] == "email_open"
    assert any(url.endswith("/subscribers/42/activity-log") for url, _ in session.calls)


@override_settings(MAILERLITE_API_KEY="test-key")
def test_get_activity_404_returns_empty():
    class _NoActivitySession(_FakeSession):
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if url.endswith("/activity-log"):
                return _FakeResponse(404, {}, "not found")
            return _FakeResponse(200, {"data": self._subscriber})

    session = _NoActivitySession(subscriber={"id": "42"})
    assert mailerlite_api.get_activity_for_email("a@b.com", session=session) == []


@override_settings(MAILERLITE_API_KEY="test-key")
def test_get_activity_for_non_subscriber_is_empty():
    session = _FakeSession(subscriber_status=404)
    assert mailerlite_api.get_activity_for_email("nope@b.com", session=session) == []


@override_settings(MAILERLITE_API_KEY="")
def test_get_subscriber_raises_without_key():
    with pytest.raises(mailerlite_api.MailerLiteConfigurationError):
        mailerlite_api.get_subscriber("a@b.com", session=_FakeSession(subscriber={"id": "1"}))


@override_settings(MAILERLITE_API_KEY="test-key")
def test_api_error_on_500():
    class _ErrSession(_FakeSession):
        def get(self, url, **kwargs):
            return _FakeResponse(500, {}, "boom")

    with pytest.raises(mailerlite_api.MailerLiteAPIError):
        mailerlite_api.get_subscriber("a@b.com", session=_ErrSession())


def test_parse_date():
    parsed = mailerlite_api.parse_date("2023-01-08T12:00:00Z")
    assert parsed is not None and parsed.year == 2023 and parsed.tzinfo is not None
    assert mailerlite_api.parse_date("2023-01-08 12:00:00") is not None
    assert mailerlite_api.parse_date(None) is None


def test_activity_subject():
    assert mailerlite_api.activity_subject({"properties": {"campaign_name": "Velocitas"}}) == "Velocitas"
    assert mailerlite_api.activity_subject({"report": {"subject": "Camp"}}) == "Camp"
    assert mailerlite_api.activity_subject({"campaign": {"name": "N"}}) == "N"
    assert mailerlite_api.activity_subject({}) == ""


@override_settings(MAILERLITE_API_KEY="test-key")
def test_upsert_subscriber_posts_payload():
    session = _FakeSession()
    data = mailerlite_api.upsert_subscriber("a@b.com", fields={"name": "Al"}, status="active", session=session)
    assert data["email"] == "a@b.com"
    url, kwargs = session.posts[0]
    assert url.endswith("/subscribers")
    assert kwargs["json"] == {
        "email": "a@b.com",
        "fields": {"name": "Al"},
        "status": "active",
    }


@override_settings(MAILERLITE_API_KEY="test-key")
def test_unsubscribe_existing_subscriber():
    session = _FakeSession(subscriber={"id": "42", "email": "a@b.com", "status": "active"})
    assert mailerlite_api.unsubscribe("a@b.com", session=session) is True
    url, kwargs = session.posts[0]
    assert url.endswith("/subscribers")
    assert kwargs["json"]["status"] == "unsubscribed"
    assert kwargs["json"]["email"] == "a@b.com"


@override_settings(MAILERLITE_API_KEY="test-key")
def test_unsubscribe_non_subscriber_is_noop():
    session = _FakeSession(subscriber_status=404)
    assert mailerlite_api.unsubscribe("nope@b.com", session=session) is False
    assert session.posts == []


@override_settings(MAILERLITE_API_KEY="test-key")
def test_unsubscribe_already_unsubscribed_is_noop():
    session = _FakeSession(subscriber={"id": "42", "status": "unsubscribed"})
    assert mailerlite_api.unsubscribe("a@b.com", session=session) is False
    assert session.posts == []


@override_settings(MAILERLITE_API_KEY="test-key")
def test_subscribe_if_absent_adds_new():
    session = _FakeSession(subscriber_status=404)
    result = mailerlite_api.subscribe_if_absent("new@b.com", fields={"name": "New"}, session=session)
    assert result == "added"
    _url, kwargs = session.posts[0]
    assert kwargs["json"]["status"] == "active"
    assert kwargs["json"]["fields"] == {"name": "New"}


@override_settings(MAILERLITE_API_KEY="test-key")
def test_subscribe_if_absent_skips_existing():
    session = _FakeSession(subscriber={"id": "42", "status": "active"})
    result = mailerlite_api.subscribe_if_absent("a@b.com", session=session)
    assert result == "exists"
    assert session.posts == []
