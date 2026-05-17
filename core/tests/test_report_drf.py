"""Report-builder & DRF smoke tests (Phase 0.5.7).

Canary for Phase 3.3 (django-report-builder) and 3.4 (DRF):
- Verifies the report-builder SPA view boots and serves HTML for a staff user.
- Verifies the DRF config endpoint returns valid JSON for an authenticated admin.
Neither test requires seeded report data — they exercise the stack, not the data.
"""
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from thetatauCMT.users.tests.factories import UserFactory


def _make_rmp_signed_staff():
    """Create a staff user with a current-semester RMP record.

    RMPSignMiddleware redirects any authenticated user who has not signed the
    RMP this semester, so every view test needs this setup.
    """
    from thetatauCMT.forms.models import RiskManagement

    user = UserFactory.create(is_staff=True)
    # All BooleanFields on RiskManagement lack a DB default and must be explicit.
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
    return user


@pytest.mark.django_db
def test_report_builder_index_returns_200():
    """GET /report_builder/ renders the SPA shell (200) for a staff user."""
    staff = _make_rmp_signed_staff()
    client = Client()
    client.force_login(staff)
    response = client.get(reverse("report_builder"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_drf_config_endpoint_returns_200():
    """GET /report_builder/api/config/ returns 200 JSON for an admin user."""
    staff = _make_rmp_signed_staff()
    api_client = APIClient()
    api_client.force_authenticate(user=staff)
    response = api_client.get("/report_builder/api/config/")
    assert response.status_code == 200
    data = response.json()
    assert "async_report" in data
