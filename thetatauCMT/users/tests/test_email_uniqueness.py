"""Regression tests for Cluster E — allauth ``EmailAddress`` duplicate / multiple crashes.

Rollbar issues this locks in:
- #967, #1030 — ``MultipleObjectsReturned: get() returned more than one EmailAddress``
- #1027 — ``IntegrityError: duplicate key value violates unique constraint
  "account_emailaddress_email_key"``

These crashes originated on the pre-upgrade (django-allauth 0.51 / Python 3.9) stack.
They were structurally resolved by the **django-allauth 65 upgrade**, whose ``account``
migrations:

- ``0004_alter_emailaddress_drop_unique_email`` dropped the old global
  ``UNIQUE(email)`` constraint (``account_emailaddress_email_key``) that #1027 hit, and
- ``0006_emailaddress_lower`` lowercased every ``EmailAddress.email`` and ``User.email``,

and whose model now enforces ``UNIQUE(user_id, email)`` plus a partial
``UNIQUE(email) WHERE verified``. Because allauth also lowercases the address at every
entry point (``AddEmailForm``/``BaseSignupForm.clean_email`` and the
``EmailAddress`` manager), the same address can exist at most once per user, so
``get_for_user()`` (which looks up ``email=email.lower()``) can never return two rows.

These tests assert those guarantees so a future settings or dependency change cannot
silently reintroduce the crashes.
"""

import pytest
from allauth.account.models import EmailAddress
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def test_add_email_is_idempotent_across_case(user_factory):
    """#967/#1030: adding the same address in different case yields a single row.

    ``EmailAddressManager.add_email`` lowercases and ``get_or_create``s, so a
    second add with different casing returns the *same* row instead of creating a
    duplicate that would later make ``get_for_user`` raise ``MultipleObjectsReturned``.
    """
    user = user_factory.create()

    first = EmailAddress.objects.add_email(None, user, "Casey.Jones@Example.EDU")
    second = EmailAddress.objects.add_email(None, user, "casey.jones@example.edu")

    assert first.pk == second.pk
    rows = EmailAddress.objects.filter(user=user, email__iexact="casey.jones@example.edu")
    assert rows.count() == 1
    # Stored lowercase (allauth 65 normalization).
    assert rows.first().email == "casey.jones@example.edu"


def test_get_for_user_is_case_insensitive_and_single(user_factory):
    """#967/#1030: ``get_for_user`` resolves case-insensitively to exactly one row."""
    user = user_factory.create()
    EmailAddress.objects.create(user=user, email="pat@example.edu", verified=True)

    found = EmailAddress.objects.get_for_user(user, "PAT@EXAMPLE.EDU")

    assert found.email == "pat@example.edu"


def test_unique_together_blocks_duplicate_email_for_same_user(user_factory):
    """``UNIQUE(user_id, email)`` prevents a duplicate row for one user."""
    user = user_factory.create()
    EmailAddress.objects.create(user=user, email="dup@example.edu")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailAddress.objects.create(user=user, email="dup@example.edu")


def test_same_unverified_email_allowed_for_two_users(user_factory):
    """#1027: the old global ``UNIQUE(email)`` is gone.

    Two accounts may hold the *same unverified* address without an
    ``IntegrityError`` — this is exactly the constraint (``account_emailaddress_email_key``)
    that #1027 crashed on, now removed by allauth migration 0004.
    """
    user_one = user_factory.create()
    user_two = user_factory.create()
    EmailAddress.objects.create(user=user_one, email="shared@example.edu", verified=False)

    # Must not raise.
    EmailAddress.objects.create(user=user_two, email="shared@example.edu", verified=False)

    assert EmailAddress.objects.filter(email="shared@example.edu").count() == 2


def test_email_cannot_be_verified_for_two_users(user_factory):
    """``unique_verified_email``: an address may be *verified* for only one account."""
    user_one = user_factory.create()
    user_two = user_factory.create()
    EmailAddress.objects.create(user=user_one, email="one@example.edu", verified=True)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailAddress.objects.create(user=user_two, email="one@example.edu", verified=True)
