"""The repair migration for CSS accounts made before emails were stored lowercase."""

import importlib

import pytest
from allauth.account.models import EmailAddress
from allauth.account.utils import filter_users_by_email
from django.apps import apps

from thetatauCMT.users.models import User
from thetatauCMT.users.tests.factories import UserFactory

from .factories import give_css_role, make_css

pytestmark = pytest.mark.django_db

repair = importlib.import_module("thetatauCMT.support.migrations.0002_lowercase_css_emails").lowercase_css_emails


def _made_before_the_fix(email, **kwargs):
    """A staff CSS as the old code stored it: the address as typed, verified and primary."""
    css = make_css(email=email, **kwargs)
    EmailAddress.objects.create(user=css, email=email, verified=True, primary=True)
    return User.objects.get(pk=css.pk)


def _reset_finds(typed):
    """The lookup allauth's password reset uses."""
    return filter_users_by_email(typed, is_active=True, prefer_verified=True)


def _addresses(user):
    return list(EmailAddress.objects.filter(user=user).values_list("email", "verified", "primary"))


def test_accounts_made_before_the_fix_are_found_after_it():
    css = _made_before_the_fix("Angela.Seegel@ThetaTau.engineering")
    assert _reset_finds("Angela.Seegel@ThetaTau.engineering") == []

    repair(apps, None)

    css = User.objects.get(pk=css.pk)
    assert css.email == css.username == "angela.seegel@thetatau.engineering"
    assert _addresses(css) == [("angela.seegel@thetatau.engineering", True, True)]
    assert _reset_finds("Angela.Seegel@ThetaTau.engineering") == [css]

    repair(apps, None)  # running it again changes nothing
    assert _addresses(css) == [("angela.seegel@thetatau.engineering", True, True)]


def test_a_lowercase_twin_row_is_kept_with_the_flags():
    css = make_css(email="Dana.Twin@Example.org")
    EmailAddress.objects.create(user=css, email="dana.twin@example.org", verified=False, primary=False)
    EmailAddress.objects.create(user=css, email="Dana.Twin@Example.org", verified=True, primary=True)

    repair(apps, None)

    assert _addresses(css) == [("dana.twin@example.org", True, True)]


def test_a_taken_username_is_left_and_the_address_still_fixed(capsys):
    UserFactory(email="someone@example.org", username="pat.taken@example.org")
    css = _made_before_the_fix("Pat.Taken@Example.org")

    repair(apps, None)

    css = User.objects.get(pk=css.pk)
    assert css.email == "pat.taken@example.org" and css.username == "Pat.Taken@Example.org"
    assert _reset_finds("pat.taken@example.org") == [css]
    assert f"Chapter Support Specialist {css.pk}: username 'pat.taken@example.org' is taken" in capsys.readouterr().out


def test_an_address_verified_by_another_account_is_left_for_an_admin(capsys):
    other = UserFactory(email="lee.shared@example.org")
    EmailAddress.objects.create(user=other, email="lee.shared@example.org", verified=True, primary=True)
    css = _made_before_the_fix("Lee.Shared@Example.org")

    repair(apps, None)

    assert _addresses(css) == [("Lee.Shared@Example.org", True, True)]
    assert _addresses(other) == [("lee.shared@example.org", True, True)]
    assert "'lee.shared@example.org' is verified on another account" in capsys.readouterr().out


def test_only_css_staff_accounts_change():
    member = UserFactory(status="active", email="Pat.Member@Example.org")
    member_css = UserFactory(status="alumni", email="Casey.Member@Example.org")
    give_css_role(member_css)

    repair(apps, None)

    assert User.objects.get(pk=member.pk).email == "Pat.Member@Example.org"
    assert User.objects.get(pk=member_css.pk).email == "Casey.Member@Example.org"
