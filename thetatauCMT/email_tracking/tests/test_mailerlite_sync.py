"""Tests for the higher-level MailerLite user-sync helpers.

These exercise the orchestration (iterating a user's emails, counting outcomes,
swallowing API/network errors, honouring configuration) with the thin API layer
monkeypatched — the API layer itself is covered by ``test_mailerlite_api``.
"""

from django.test import override_settings

from thetatauCMT.email_tracking import mailerlite_api, mailerlite_sync


class _User:
    def __init__(
        self,
        email="",
        email_school="",
        first_name="",
        last_name="",
        name="",
        pk=1,
    ):
        self.email = email
        self.email_school = email_school
        self.first_name = first_name
        self.last_name = last_name
        self.name = name
        self.pk = pk


@override_settings(MAILERLITE_API_KEY="")
def test_unsubscribe_user_noop_when_unconfigured(monkeypatch):
    calls = []
    monkeypatch.setattr(mailerlite_api, "unsubscribe", lambda *a, **k: calls.append(a) or True)
    assert mailerlite_sync.unsubscribe_user(_User(email="a@b.com")) == 0
    assert calls == []


@override_settings(MAILERLITE_API_KEY="k")
def test_unsubscribe_user_hits_each_distinct_email(monkeypatch):
    seen = []

    def fake(email, session=None):
        seen.append(email)
        return True

    monkeypatch.setattr(mailerlite_api, "unsubscribe", fake)
    changed = mailerlite_sync.unsubscribe_user(_User(email="a@b.com", email_school="a@school.edu"))
    assert changed == 2
    assert seen == ["a@b.com", "a@school.edu"]


@override_settings(MAILERLITE_API_KEY="k")
def test_unsubscribe_user_dedupes_case_insensitively(monkeypatch):
    seen = []

    def fake(email, session=None):
        seen.append(email)
        return False  # already unsubscribed -> not counted

    monkeypatch.setattr(mailerlite_api, "unsubscribe", fake)
    changed = mailerlite_sync.unsubscribe_user(_User(email="a@b.com", email_school="A@B.com"))
    assert seen == ["a@b.com"]
    assert changed == 0


@override_settings(MAILERLITE_API_KEY="k")
def test_unsubscribe_user_swallows_api_errors(monkeypatch):
    def boom(email, session=None):
        raise mailerlite_api.MailerLiteAPIError("nope")

    monkeypatch.setattr(mailerlite_api, "unsubscribe", boom)
    # Must never raise — the member's local opt-out has to succeed regardless.
    assert mailerlite_sync.unsubscribe_user(_User(email="a@b.com")) == 0


@override_settings(MAILERLITE_API_KEY="k")
def test_send_user_skips_when_no_email():
    assert mailerlite_sync.send_user(_User()) == "skipped"


@override_settings(MAILERLITE_API_KEY="k")
def test_send_user_uses_primary_email_and_name_fields(monkeypatch):
    captured = {}

    def fake(email, fields=None, session=None):
        captured["email"] = email
        captured["fields"] = fields
        return "added"

    monkeypatch.setattr(mailerlite_api, "subscribe_if_absent", fake)
    result = mailerlite_sync.send_user(
        _User(email="a@b.com", email_school="a@school.edu", first_name="Al", last_name="Bee")
    )
    assert result == "added"
    assert captured["email"] == "a@b.com"
    assert captured["fields"] == {"name": "Al", "last_name": "Bee"}


@override_settings(MAILERLITE_API_KEY="k")
def test_send_users_summary(monkeypatch):
    outcomes = {"a@b.com": "added", "c@d.com": "exists"}

    def fake(email, fields=None, session=None):
        return outcomes[email]

    monkeypatch.setattr(mailerlite_api, "subscribe_if_absent", fake)
    users = [
        _User(email="a@b.com"),
        _User(email="c@d.com"),
        _User(),  # no email -> skipped
    ]
    summary = mailerlite_sync.send_users(users)
    assert summary == {"added": 1, "exists": 1, "skipped": 1, "errors": 0}


@override_settings(MAILERLITE_API_KEY="k")
def test_send_users_counts_errors(monkeypatch):
    def boom(email, fields=None, session=None):
        raise mailerlite_api.MailerLiteAPIError("nope")

    monkeypatch.setattr(mailerlite_api, "subscribe_if_absent", boom)
    summary = mailerlite_sync.send_users([_User(email="a@b.com")])
    assert summary["errors"] == 1
