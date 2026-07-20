import pytest
from django.test import override_settings

from thetatauCMT.email_tracking import mailjet_api


class _FakeResult:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


class _FakeResource:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return self._result


class _FakeClient:
    def __init__(self, message_result=None, history_result=None):
        self.message = _FakeResource(message_result)
        self.messagehistory = _FakeResource(history_result)


@override_settings(ANYMAIL={"MAILJET_API_KEY": "k", "MAILJET_SECRET_KEY": "s"})
def test_is_configured_true_with_creds():
    assert mailjet_api.is_configured() is True


@override_settings(ANYMAIL={})
def test_is_configured_false_without_creds(monkeypatch):
    monkeypatch.delenv("MJ_APIKEY_PUBLIC", raising=False)
    monkeypatch.delenv("MJ_APIKEY_PRIVATE", raising=False)
    assert mailjet_api.is_configured() is False


@override_settings(ANYMAIL={})
def test_get_client_raises_without_creds(monkeypatch):
    monkeypatch.delenv("MJ_APIKEY_PUBLIC", raising=False)
    monkeypatch.delenv("MJ_APIKEY_PRIVATE", raising=False)
    with pytest.raises(mailjet_api.MailjetConfigurationError):
        mailjet_api.get_client()


@override_settings(ANYMAIL={})
def test_credentials_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("MJ_APIKEY_PUBLIC", "envkey")
    monkeypatch.setenv("MJ_APIKEY_PRIVATE", "envsecret")
    assert mailjet_api.is_configured() is True


def test_get_messages_for_email_filters_by_contactalt():
    result = _FakeResult(
        200,
        {
            "Data": [{"ID": "1", "ArrivedAt": "2018-01-01T00:00:00", "Status": "opened"}],
            "Total": 1,
        },
    )
    client = _FakeClient(message_result=result)
    resp = mailjet_api.get_messages_for_email("a@b.com", client=client)
    filters = client.message.calls[0]["filters"]
    assert filters["ContactAlt"] == "a@b.com"
    assert filters["ShowSubject"] == "true"
    assert resp["data"][0]["ID"] == "1"
    assert resp["data"][0]["arrived_at"] is not None
    assert resp["total"] == 1
    assert resp["count"] == 1


def test_get_messages_passes_limit_and_offset():
    client = _FakeClient(message_result=_FakeResult(200, {"Data": [], "Total": 0}))
    mailjet_api.get_messages_for_email("a@b.com", limit=25, offset=50, client=client)
    filters = client.message.calls[0]["filters"]
    assert filters["Limit"] == 25
    assert filters["Offset"] == 50


def test_get_messages_for_empty_email_returns_empty():
    assert mailjet_api.get_messages_for_email("", client=_FakeClient()) == {
        "data": [],
        "total": 0,
        "count": 0,
    }


def test_get_messages_date_filters_become_fromts_tots():
    import datetime as dt

    client = _FakeClient(message_result=_FakeResult(200, {"Data": [], "Total": 0}))
    mailjet_api.get_messages_for_email(
        "a@b.com",
        date_from=dt.date(2020, 1, 1),
        date_to=dt.date(2020, 1, 31),
        client=client,
    )
    filters = client.message.calls[0]["filters"]
    assert "FromTS" in filters and "ToTS" in filters
    assert filters["FromTS"] < filters["ToTS"]


def test_get_message_count_uses_countonly():
    client = _FakeClient(message_result=_FakeResult(200, {"Count": 347, "Data": [], "Total": 347}))
    total = mailjet_api.get_message_count("a@b.com", client=client)
    assert total == 347
    assert client.message.calls[0]["filters"]["countOnly"] == 1
    assert client.message.calls[0]["filters"]["ContactAlt"] == "a@b.com"


def test_get_message_count_returns_none_when_countonly_ignored():
    # Mailjet returned data -> countOnly was not honoured -> total unknown.
    client = _FakeClient(message_result=_FakeResult(200, {"Count": 10, "Data": [{"ID": "1"}], "Total": 10}))
    assert mailjet_api.get_message_count("a@b.com", client=client) is None


def test_get_message_count_empty_email():
    assert mailjet_api.get_message_count("", client=_FakeClient()) == 0


def test_get_message_history_by_id():
    result = _FakeResult(
        200,
        {
            "Data": [
                {"EventType": "sent", "EventAt": 1546958313},
                {"EventType": "opened", "EventAt": 1546958354},
            ]
        },
    )
    client = _FakeClient(history_result=result)
    data = mailjet_api.get_message_history("123", client=client)
    assert client.messagehistory.calls[0]["id"] == "123"
    assert data[0]["EventType"] == "sent"
    assert data[0]["event_at"] is not None


def test_api_error_on_non_200():
    client = _FakeClient(message_result=_FakeResult(401, {"ErrorMessage": "bad"}))
    with pytest.raises(mailjet_api.MailjetAPIError):
        mailjet_api.get_messages_for_email("a@b.com", client=client)
