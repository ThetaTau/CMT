"""Shared herald helpers in :mod:`core.notifications`."""

from core.notifications import MAX_RECIPIENT_CHARS, capped_recipients


def test_capped_recipients_sorts_and_deduplicates():
    emails = ["b@example.com", "a@example.com", "b@example.com"]
    assert capped_recipients(emails) == ["a@example.com", "b@example.com"]


def test_capped_recipients_drops_blank_addresses():
    assert capped_recipients(["", None, "a@example.com"]) == ["a@example.com"]


def test_capped_recipients_of_an_empty_list_is_empty():
    assert capped_recipients([]) == []


def test_capped_recipients_never_exceeds_the_column():
    """herald stores the joined list in a varchar(2000); overflow is a DataError."""
    kept = capped_recipients([f"user-{index}@example.com" for index in range(500)])
    assert len(kept) < 500
    assert len(",".join(kept)) <= MAX_RECIPIENT_CHARS


def test_capped_recipients_warns_when_it_trims(caplog):
    capped_recipients([f"user-{index}@example.com" for index in range(500)], context="a big send")
    assert "recipient list too long for a big send" in caplog.text
