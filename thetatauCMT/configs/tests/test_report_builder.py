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
    redirecting to /setup/ before reaching the report-builder endpoint. The
    ``view_user`` permission matters: report_builder short-circuits to an empty
    result set without ever running the query when the user cannot view the root
    model, which would hide any query error.
    """
    from django.contrib.auth.models import Permission

    from thetatauCMT.forms.models import RiskManagement
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create(is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(
            codename="view_user",
            content_type=ContentType.objects.get_for_model(user),
        )
    )
    RiskManagement.objects.get_or_create(
        user=user,
        defaults=dict(
            role="regent",
            submission=None,
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


@pytest.fixture
def array_filter_report(db):
    """A Report whose filter Postgres cannot run: Equals against the current_roles array."""
    from django.contrib.auth import get_user_model
    from report_builder.models import DisplayField, FilterField, Report

    User = get_user_model()
    ct = ContentType.objects.get_for_model(User)
    report = Report.objects.create(name="Broken Roles Report", root_model=ct)
    DisplayField.objects.create(report=report, name="Username", field="username", position=0)
    FilterField.objects.create(
        report=report,
        field="current_roles",
        filter_type="exact",
        filter_value="None",
        exclude=True,
        position=0,
    )
    return report


@pytest.fixture
def isnull_filter_report(db):
    """A Report with an "Is null" filter whose value report_builder cannot turn into a bool."""
    from django.contrib.auth import get_user_model
    from report_builder.models import DisplayField, FilterField, Report

    User = get_user_model()
    ct = ContentType.objects.get_for_model(User)
    report = Report.objects.create(name="Broken Isnull Report", root_model=ct)
    DisplayField.objects.create(report=report, name="Username", field="username", position=0)
    FilterField.objects.create(
        report=report,
        field="current_roles",
        filter_type="isnull",
        filter_value="True",
        position=0,
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


@pytest.mark.django_db
def test_generate_array_filter_returns_400_not_500(client, staff_user_with_rmp, array_filter_report):
    """An Equals filter on an array column is reported, not raised as a DataError 500."""
    client.force_login(staff_user_with_rmp)
    url = reverse("generate_report", kwargs={"report_id": array_filter_report.pk})
    response = client.get(url)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "current_roles" in detail
    assert "Contains (case-insensitive)" in detail


@pytest.mark.django_db
def test_download_array_filter_returns_400_not_500(client, staff_user_with_rmp, array_filter_report):
    """The download endpoint renders the explanation page instead of blowing up."""
    client.force_login(staff_user_with_rmp)
    url = reverse("report_download_file", kwargs={"pk": array_filter_report.pk, "filetype": "xlsx"})
    response = client.get(url)
    assert response.status_code == 400
    content = response.content.decode()
    assert "Report could not be run" in content
    assert "current_roles" in content


@pytest.mark.django_db
def test_generate_isnull_filter_returns_400_not_500(client, staff_user_with_rmp, isnull_filter_report):
    """An "Is null" filter value report_builder cannot coerce is reported, not raised."""
    client.force_login(staff_user_with_rmp)
    url = reverse("generate_report", kwargs={"report_id": isnull_filter_report.pk})
    response = client.get(url)
    assert response.status_code == 400
    assert "Is null" in response.json()["detail"]


@pytest.mark.django_db
def test_download_valid_report_still_works(client, staff_user_with_rmp, simple_report):
    """The hardened download view is transparent for a report that runs."""
    from report_builder.models import DisplayField

    DisplayField.objects.create(report=simple_report, name="Username", field="username", position=0)
    client.force_login(staff_user_with_rmp)
    url = reverse("report_download_file", kwargs={"pk": simple_report.pk, "filetype": "xlsx"})
    response = client.get(url)
    assert response.status_code == 200
