"""Auth & allauth smoke tests (Phase 0.5.2).

Goal: detect allauth 0.51 → 65 breakage in Phase 3.1.

Covers:
- GET login page renders
- POST valid / invalid credentials
- Logout
- Password-reset page
- Signup gate (disabled by default)
- AccountAdapter.is_open_for_signup
- SocialAccountAdapter.pre_social_login (four code-paths)
"""

from unittest.mock import MagicMock

import pytest
from django.test import override_settings
from django.urls import reverse

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_page_renders(client):
    """GET /accounts/login/ → 200 and includes a <form> element."""
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"<form" in response.content


@pytest.mark.django_db
# CaptchaLoginForm adds ReCaptchaField only when DEBUG=False; bypass it for
# this POST test so the form validates on credentials alone.
@override_settings(DEBUG=True)
def test_login_post_valid_credentials_redirects(client, user_factory, test_password):
    """POST correct email + password → allauth issues a 302 redirect."""
    user = user_factory.create(password=test_password)
    response = client.post(
        reverse("login"),
        {"login": user.email, "password": test_password},
    )
    # allauth redirects whether the email is verified or not
    # (to home or to the email-verification-pending page)
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_login_post_invalid_credentials_shows_error(client):
    """POST wrong credentials → 200 re-render with an error message."""
    response = client.post(
        reverse("login"),
        {"login": "nobody@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 200
    content = response.content.decode().lower()
    # allauth 65 renders: "The e-mail address and/or password you specified are not correct."
    assert any(kw in content for kw in ["incorrect", "invalid", "email address", "are not correct"])


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_clears_session(auto_login_user):
    """POST /accounts/logout/ → user is no longer authenticated."""
    client, user = auto_login_user()
    response = client.post(reverse("logout"), follow=True)
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_page_renders(client):
    """GET /password_reset/ → 200 and includes an email input."""
    response = client.get(reverse("password_reset"))
    assert response.status_code == 200
    assert b"email" in response.content.lower()


# ---------------------------------------------------------------------------
# Email confirmation
#
# Regression coverage for a production 404: allauth's ConfirmEmailView.post()
# doesn't guard get_object() the way GET does, so re-POSTing a key whose
# EmailAddress is already verified (double-click, revisited link, expired
# signature) raises a bare Http404 instead of the friendly "expired or
# invalid" page. ConfirmEmailView (thetatauCMT/users/views.py) fixes this.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_email_valid_key_confirms(client, user_factory):
    """POSTing a fresh, unconfirmed key verifies the email (no 404)."""
    from allauth.account.models import EmailAddress, EmailConfirmationHMAC

    user = user_factory.create()
    email_address = EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    key = EmailConfirmationHMAC(email_address).key

    response = client.post(reverse("account_confirm_email", args=[key]))

    assert response.status_code in (200, 302)
    email_address.refresh_from_db()
    assert email_address.verified is True


@pytest.mark.django_db
def test_confirm_email_already_confirmed_key_does_not_404(client, user_factory):
    """POSTing a key for an already-verified EmailAddress must not 404 (the
    production bug), and should say "already confirmed, log in" rather than
    the generic "expired or invalid, request a new one" (that message is
    wrong here: mandatory verification re-sends a fresh link on every
    unverified login attempt, so a member can hold several once-valid links
    for the same address; the first one used verifies it for all of them)."""
    from allauth.account.models import EmailAddress, EmailConfirmationHMAC

    user = user_factory.create()
    email_address = EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    key = EmailConfirmationHMAC(email_address).key

    response = client.post(reverse("account_confirm_email", args=[key]))

    assert response.status_code == 200
    content = response.content.decode().lower()
    assert "already been used" in content
    assert user.email.lower() in content
    assert "expired or is invalid" not in content


@pytest.mark.django_db
def test_confirm_email_bogus_key_does_not_404(client):
    """POSTing a garbage/tampered key shows the invalid page, not a 404."""
    response = client.post(reverse("account_confirm_email", args=["not-a-real-key"]))

    assert response.status_code == 200
    assert "expired or is invalid" in response.content.decode().lower()


@pytest.mark.django_db
def test_confirm_email_already_confirmed_key_get_shows_login_message(client, user_factory):
    """Same distinction on GET: revisiting (not just re-POSTing) an already-used
    link should say "log in", not "request a new confirmation"."""
    from allauth.account.models import EmailAddress, EmailConfirmationHMAC

    user = user_factory.create()
    email_address = EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    key = EmailConfirmationHMAC(email_address).key

    response = client.get(reverse("account_confirm_email", args=[key]))

    assert response.status_code == 200
    content = response.content.decode().lower()
    assert "already been used" in content
    assert "expired or is invalid" not in content


# ---------------------------------------------------------------------------
# Signup gate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_signup_page_disabled_by_default(client):
    """Signup is disabled (ACCOUNT_ALLOW_REGISTRATION=False in base.py).

    allauth either renders a 'signup closed' page or redirects; the active
    sign-up form (with password1 field) must NOT be present.
    """
    response = client.get(reverse("account_signup"), follow=True)
    assert response.status_code in (200, 302, 403)
    if response.status_code == 200:
        assert "password1" not in response.content.decode()


# ---------------------------------------------------------------------------
# AccountAdapter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_account_adapter_closed_for_signup(rf):
    """AccountAdapter.is_open_for_signup returns False when registration is off."""
    from thetatauCMT.users.adapters import AccountAdapter

    request = rf.get("/")
    adapter = AccountAdapter(request)
    with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
        assert adapter.is_open_for_signup(request) is False


@pytest.mark.django_db
def test_account_adapter_open_for_signup(rf):
    """AccountAdapter.is_open_for_signup returns True when registration is on."""
    from thetatauCMT.users.adapters import AccountAdapter

    request = rf.get("/")
    adapter = AccountAdapter(request)
    with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
        assert adapter.is_open_for_signup(request) is True


# ---------------------------------------------------------------------------
# SocialAccountAdapter.pre_social_login
# ---------------------------------------------------------------------------


def test_pre_social_login_existing_account_is_noop(rf):
    """pre_social_login returns immediately when sociallogin.is_existing is True."""
    from thetatauCMT.users.adapters import SocialAccountAdapter

    request = rf.get("/")
    adapter = SocialAccountAdapter(request)
    sociallogin = MagicMock()
    sociallogin.is_existing = True

    adapter.pre_social_login(request, sociallogin)

    sociallogin.connect.assert_not_called()


def test_pre_social_login_no_email_field_is_noop(rf):
    """pre_social_login returns early when extra_data contains no email keys."""
    from thetatauCMT.users.adapters import SocialAccountAdapter

    request = rf.get("/")
    adapter = SocialAccountAdapter(request)
    sociallogin = MagicMock()
    sociallogin.is_existing = False
    sociallogin.account.extra_data = {"name": "Alice"}  # neither 'email' nor 'emailAddress'

    adapter.pre_social_login(request, sociallogin)

    sociallogin.connect.assert_not_called()


@pytest.mark.django_db
def test_pre_social_login_links_to_existing_user(rf, user_factory):
    """pre_social_login connects the social account to an existing user by email.

    Note: the adapter checks 'emailAddress' as the gate key (code uses
    ``if / if / else`` rather than ``if / elif / else``), so we must supply
    'emailAddress' in extra_data for the connection path to execute.
    """
    from thetatauCMT.users.adapters import SocialAccountAdapter

    user = user_factory.create()
    request = rf.get("/")
    adapter = SocialAccountAdapter(request)
    sociallogin = MagicMock()
    sociallogin.is_existing = False
    sociallogin.account.extra_data = {"emailAddress": user.email}

    adapter.pre_social_login(request, sociallogin)

    sociallogin.connect.assert_called_once_with(request, user)


@pytest.mark.django_db
def test_pre_social_login_unknown_email_is_noop(rf):
    """pre_social_login does not call connect() when the email is not in the DB."""
    from thetatauCMT.users.adapters import SocialAccountAdapter

    request = rf.get("/")
    adapter = SocialAccountAdapter(request)
    sociallogin = MagicMock()
    sociallogin.is_existing = False
    sociallogin.account.extra_data = {"emailAddress": "ghost@example.com"}

    adapter.pre_social_login(request, sociallogin)

    sociallogin.connect.assert_not_called()


# ---------------------------------------------------------------------------
# AccountAdapter – OTPAdapter inheritance
# ---------------------------------------------------------------------------


def test_account_adapter_is_subclass_of_otp_adapter():
    """AccountAdapter inherits 2FA helpers from allauth_2fa's OTPAdapter base class."""
    from allauth_2fa.adapter import OTPAdapter

    from thetatauCMT.users.adapters import AccountAdapter

    assert issubclass(AccountAdapter, OTPAdapter)
    assert callable(getattr(AccountAdapter, "has_2fa_enabled", None))
    assert callable(getattr(AccountAdapter, "get_2fa_authenticate_url", None))


def test_account_adapter_2fa_methods_exist_on_instance(rf):
    """AccountAdapter instances expose has_2fa_enabled and get_2fa_authenticate_url."""
    from thetatauCMT.users.adapters import AccountAdapter

    request = rf.get("/")
    adapter = AccountAdapter(request)
    assert hasattr(adapter, "has_2fa_enabled")
    assert callable(adapter.has_2fa_enabled)
    assert hasattr(adapter, "get_2fa_authenticate_url")
    assert callable(adapter.get_2fa_authenticate_url)


@pytest.mark.django_db
def test_make_primary_email_via_account_email_view_syncs_username(auto_login_user):
    from allauth.account.models import EmailAddress

    client, user = auto_login_user()
    original = user.email
    assert user.username == original

    EmailAddress.objects.create(user=user, email=original, verified=True, primary=True)
    EmailAddress.objects.create(user=user, email="newprimary@example.edu", verified=True, primary=False)

    response = client.post(
        reverse("account_email"),
        {"action_primary": "", "email": "newprimary@example.edu"},
    )
    assert response.status_code in (200, 302)

    user.refresh_from_db()
    assert user.email == "newprimary@example.edu"
    assert user.username == "newprimary@example.edu"
