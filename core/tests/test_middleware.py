"""Smoke tests for core/middleware.py (Phase 0.5.4).

Exercises OfficerMiddleware and RMPSignMiddleware via RequestFactory.
Canary: if Django 4.2 breaks MiddlewareMixin.__call__, process_request
injection, or the request-attribute contract, these tests fail immediately.
"""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from core.middleware import OfficerMiddleware, RMPSignMiddleware
from thetatauCMT.users.tests.factories import UserFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_RESPONSE = HttpResponse("OK", status=200)


def _get_response(_request):
    return _DUMMY_RESPONSE


def _make_request(factory, path="/some-page/"):
    """RequestFactory request pre-loaded with an in-memory messages backend."""
    request = factory.get(path)
    # messages.add_message() requires a storage backend on the request
    request._messages = CookieStorage(request)
    return request


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


def test_middleware_module_imports():
    """core.middleware imports cleanly — both classes present."""
    import core.middleware as mod

    assert hasattr(mod, "OfficerMiddleware")
    assert hasattr(mod, "RMPSignMiddleware")
    assert hasattr(mod, "RequireSuperuser2FAMiddleware")


# ---------------------------------------------------------------------------
# OfficerMiddleware
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_officer_middleware_anonymous_noop():
    """Anonymous request: process_request is a no-op — no flags injected."""
    factory = RequestFactory()
    request = factory.get("/")
    request.user = AnonymousUser()

    OfficerMiddleware(get_response=_get_response).process_request(request)

    assert not hasattr(request, "is_officer")
    assert not hasattr(request, "is_nat_officer")


@pytest.mark.django_db
def test_officer_middleware_non_officer_no_flags():
    """Authenticated user in no special groups: no officer flags injected."""
    user = UserFactory.create()
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user

    OfficerMiddleware(get_response=_get_response).process_request(request)

    assert not hasattr(request, "is_officer")
    assert not hasattr(request, "is_nat_officer")


@pytest.mark.django_db
def test_officer_middleware_chapter_officer_sets_flag():
    """User in 'officer' group → request.is_officer=True; is_nat_officer not set."""
    user = UserFactory.create()
    officer_group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(officer_group)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = user

    OfficerMiddleware(get_response=_get_response).process_request(request)

    assert getattr(request, "is_officer", False) is True
    assert not hasattr(request, "is_nat_officer")


@pytest.mark.django_db
def test_officer_middleware_natoff_sets_both_flags():
    """User in 'natoff' group → both is_officer and is_nat_officer are True."""
    user = UserFactory.create()
    natoff_group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(natoff_group)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = user

    OfficerMiddleware(get_response=_get_response).process_request(request)

    assert getattr(request, "is_officer", False) is True
    assert getattr(request, "is_nat_officer", False) is True


# ---------------------------------------------------------------------------
# RMPSignMiddleware
# ---------------------------------------------------------------------------


def test_rmp_middleware_anonymous_passes_through():
    """Anonymous user: middleware returns get_response result unchanged."""
    factory = RequestFactory()
    request = _make_request(factory, "/some-page/")
    request.user = AnonymousUser()

    response = RMPSignMiddleware(get_response=_get_response)(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_rmp_middleware_excluded_path_passes_through():
    """Path in TERMS_EXCLUDE_URL_LIST: RMP check is skipped even if not signed."""
    user = UserFactory.create()  # no RiskManagement record → unsigned

    factory = RequestFactory()
    request = _make_request(factory, "/rmp/")
    request.user = user

    response = RMPSignMiddleware(get_response=_get_response)(request)

    # No redirect — excluded path returns the original response
    assert response.status_code == 200


@pytest.mark.django_db
def test_rmp_middleware_unsigned_redirects():
    """Authenticated user with no RMP for this semester is redirected to /rmp/."""
    user = UserFactory.create()  # no RiskManagement record

    factory = RequestFactory()
    request = _make_request(factory, "/chapter/dashboard/")
    request.user = user

    response = RMPSignMiddleware(get_response=_get_response)(request)

    assert response.status_code == 302
    assert "/rmp/" in response["Location"]


@pytest.mark.django_db
def test_rmp_middleware_alumni_without_role_not_required():
    """An alumnus holding no current role is exempt from the RMP requirement."""
    user = UserFactory.create(status="alumni")  # no RiskManagement record

    factory = RequestFactory()
    request = _make_request(factory, "/chapter/dashboard/")
    request.user = user

    response = RMPSignMiddleware(get_response=_get_response)(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_rmp_middleware_alumni_with_role_still_redirects():
    """An alumnus who still holds a role must sign the RMP."""
    user = UserFactory.create(status="alumni", make_officer="adviser")

    factory = RequestFactory()
    request = _make_request(factory, "/chapter/dashboard/")
    request.user = user

    response = RMPSignMiddleware(get_response=_get_response)(request)

    assert response.status_code == 302
    assert "/rmp/" in response["Location"]


@pytest.mark.django_db
def test_rmp_middleware_signed_passes_through():
    """Authenticated user who has signed the RMP this semester gets normal response."""
    from thetatauCMT.forms.models import RiskManagement

    user = UserFactory.create()
    # Create a minimal RMP record dated today so user_signed_this_semester returns truthy
    RiskManagement.objects.create(
        user=user,
        role="member",
        date=timezone.now().date(),
        alcohol=False,
        hosting=False,
        monitoring=False,
        member=False,
        officer=False,
        abusive=False,
        hazing=False,
        substances=False,
        high_risk=False,
        transportation=False,
        property_management=False,
        guns=False,
        trademark=False,
        social=False,
        indemnification=False,
        agreement=False,
        electronic_agreement=False,
        terms_agreement=False,
        typed_name="Smoke Test",
    )

    factory = RequestFactory()
    request = _make_request(factory, "/chapter/dashboard/")
    request.user = user

    response = RMPSignMiddleware(get_response=_get_response)(request)

    assert response.status_code == 200
