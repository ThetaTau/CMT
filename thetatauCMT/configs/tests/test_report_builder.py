"""
End-to-end test for the django-report-builder integration (Section 6.1.6).

Creates a minimal Report definition against a real ContentType,
hits the generate endpoint as a staff user with a valid RiskManagement
record (to pass RMPSignMiddleware), and asserts:
  - HTTP 200
  - Response body is non-empty JSON with a "data" key
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone


@pytest.fixture
def staff_user_with_rmp(db):
    """A staff user with a current-semester RiskManagement record.

    is_superuser is intentionally False to avoid RequireSuperuser2FAMiddleware
    redirecting to /setup/ before reaching the report-builder endpoint.
    """
    from thetatauCMT.users.tests.factories import UserFactory
    from thetatauCMT.forms.models import RiskManagement

    user = UserFactory.create(is_staff=True)
    RiskManagement.objects.get_or_create(
        user=user,
        defaults=dict(
            role="regent",
            submission=None,
            date=timezone.now().date(),
            alcohol=False, hosting=False, monitoring=False, member=False,
            officer=False, abusive=False, hazing=False, substances=False,
            high_risk=False, transportation=False, property_management=False,
            guns=False, trademark=False, social=False, indemnification=False,
            agreement=False, electronic_agreement=False, terms_agreement=False,
            typed_name="test user",
        ),
    )
    return user


@pytest.fixture
def simple_report(db):
    """A minimal Report with no display fields (generates empty-body rows)."""
    from django.contrib.auth import get_user_model
    from report_builder.models import Report

    User = get_user_model()
    ct = ContentType.objects.get_for_model(User)
    report = Report.objects.create(
        name="Test Report",
        root_model=ct,
    )
    return report


@pytest.mark.django_db
def test_report_builder_generate_returns_200(client, staff_user_with_rmp, simple_report):
    """GenerateReport endpoint returns 200 with a JSON body for a staff user."""
    client.force_login(staff_user_with_rmp)
    url = reverse("generate_report", kwargs={"report_id": simple_report.pk})
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
