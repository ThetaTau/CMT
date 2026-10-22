"""CSSWI-11: two-factor sign-in for CSSs, Admins and National Officers (Q19, Q27 A)."""

import datetime

import pytest
from allauth.account.models import EmailAddress
from allauth.core import context
from allauth.socialaccount.internal.flows.login import complete_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from core.middleware import NATOFF_2FA_CONFIG_KEY, natoff_2fa_required_from
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.users.models import User, UserAlter
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, add_totp_device, make_css, make_regent

pytestmark = pytest.mark.django_db

PASSWORD = "strong-test-pass"


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    return User.objects.get(pk=user.pk)


def _require_natoffs_from(day):
    return Config.objects.create(key=NATOFF_2FA_CONFIG_KEY, value=day.isoformat(), description="test")


def _natoff():
    user = UserFactory(status="alumni")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(user)
    return _fresh(user)


def _person(who):
    if who == "css":
        user = make_css(two_factor=False)
        ChapterSupportAssignmentFactory(user=user, chapter=ChapterFactory(name="alpha"))
    elif who == "admin":
        user = UserFactory(status="alumni", is_superuser=True, is_staff=True)
    else:
        user = _natoff()
    return _fresh(user)


def _a_page(user):
    return reverse("users:profile", kwargs={"username": user.username})


# --- setup is required (Q19) ----------------------------------------------------------------


@pytest.mark.parametrize("who", ["css", "admin", "natoff"])
def test_they_are_sent_to_setup_until_they_have_a_device(auto_login_user, who):
    _require_natoffs_from(_days(-1))
    client, user = auto_login_user(user=_person(who))

    response = client.get(_a_page(user))
    assert response.status_code == 302 and response["Location"] == reverse("two-factor-setup")
    assert client.get(reverse("two-factor-setup")).status_code == 200

    add_totp_device(user)
    assert client.get(_a_page(user)).status_code == 200


@pytest.mark.parametrize("who", ["member", "regent"])
def test_members_and_chapter_officers_are_not_required(auto_login_user, who):
    _require_natoffs_from(_days(-1))
    user = UserFactory(status="active") if who == "member" else make_regent()
    client, _ = auto_login_user(user=user)

    assert client.get(_a_page(user)).status_code == 200


def test_national_officers_are_not_required_while_the_date_is_unset(auto_login_user):
    client, natoff = auto_login_user(user=_natoff())

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert 'id="natoff-2fa-banner"' not in response.content.decode()
    assert natoff_2fa_required_from() is None


def test_a_national_officer_viewing_as_a_member_is_still_required(auto_login_user):
    _require_natoffs_from(_days(-1))
    natoff = _natoff()
    UserAlter.objects.create(user=natoff, chapter=natoff.chapter, hide_natoff=True)
    client, _ = auto_login_user(user=_fresh(natoff))

    response = client.get(_a_page(natoff))

    assert response.status_code == 302 and response["Location"] == reverse("two-factor-setup")


def test_the_banner_shows_only_before_the_date(auto_login_user):
    setting = _require_natoffs_from(_days(14))
    client, natoff = auto_login_user(user=_natoff())

    content = client.get(reverse("home")).content.decode()
    assert 'id="natoff-2fa-banner"' in content and reverse("two-factor-setup") in content

    add_totp_device(natoff)
    assert 'id="natoff-2fa-banner"' not in client.get(reverse("home")).content.decode()

    setting.value = _days(-1).isoformat()
    setting.save()
    response = client.get(reverse("home"))
    assert response.status_code == 200 and 'id="natoff-2fa-banner"' not in response.content.decode()


def test_an_unreadable_date_means_no_requirement():
    Config.objects.create(key=NATOFF_2FA_CONFIG_KEY, value="next month", description="test")
    assert natoff_2fa_required_from() is None


def test_a_css_who_needs_both_sets_up_two_factor_before_the_rmp(client):
    css = _person("css")
    client.force_login(css)

    response = client.get(reverse("support:my_chapters"), follow=True)

    assert response.redirect_chain[-1][0] == reverse("two-factor-setup")
    assert response.status_code == 200


# --- the code is asked for at sign-in -------------------------------------------------------------


def _with_device(who):
    user = _person(who)
    user.set_password(PASSWORD)
    user.save()
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    add_totp_device(user)
    return user


@override_settings(DEBUG=True)  # the sign-in form only skips its captcha in DEBUG
@pytest.mark.parametrize("who", ["css", "admin", "natoff"])
def test_the_code_is_asked_for_after_a_password_sign_in(client, who):
    user = _with_device(who)

    response = client.post(reverse("login"), {"login": user.email, "password": PASSWORD})

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("two-factor-authenticate"))
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("who", ["css", "admin", "natoff"])
def test_the_code_is_asked_for_after_a_google_sign_in(who):
    user = _with_device(who)
    SocialAccount.objects.create(user=user, provider="google", uid=f"google-{user.pk}")
    callback = reverse("google_callback")
    request = RequestFactory().get(callback)
    request.user = AnonymousUser()
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    request.resolver_match = resolve(callback)
    # As the Google provider builds it: an unsaved user, swapped for the account's owner
    # when the existing social account is looked up.
    sociallogin = SocialLogin(
        user=User(email=user.email),
        account=SocialAccount(provider="google", uid=f"google-{user.pk}", extra_data={}),
    )
    sociallogin.state = {"process": "login"}

    with context.request_context(request):  # as allauth's AccountMiddleware does
        response = complete_login(request, sociallogin)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("two-factor-authenticate"))
    assert request.session["allauth_2fa_user_id"] == str(user.pk)
    assert "_auth_user_id" not in request.session
