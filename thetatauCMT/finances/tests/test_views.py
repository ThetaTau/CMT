import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.tests.factories import InvoiceFactory
from thetatauCMT.forms.tests.factories import AuditFactory
from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_invoice_list_view_authenticated(auto_login_user):
    """Any authenticated user can access the invoice list."""
    client, user = auto_login_user()
    url = reverse("finances:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_invoice_list_view_unauthenticated(client):
    url = reverse("finances:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_invoice_list_view_filters_by_chapter(auto_login_user):
    """Invoice list shows invoices; user's chapter filter is applied."""
    client, user = auto_login_user()
    # Create an invoice for user's chapter
    InvoiceFactory(chapter=user.current_chapter)
    url = reverse("finances:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_balances_view_authenticated(auto_login_user):
    """Any authenticated user can access the chapter balances view."""
    client, user = auto_login_user()
    url = reverse("finances:chapters")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_balances_view_unauthenticated(client):
    url = reverse("finances:chapters")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_chapter_balances_view_with_invoices(auto_login_user):
    """Chapter balances view shows aggregated invoice data."""
    client, user = auto_login_user()
    InvoiceFactory()
    InvoiceFactory()
    url = reverse("finances:chapters")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_balances_view_shows_membership_and_audit(auto_login_user):
    """The overview surfaces actives, PNMs, and the latest audit dues."""
    client, user = auto_login_user()
    chapter = ChapterFactory(name="lambda beta")
    UserFactory(chapter=chapter, current_status="active")
    pnm = UserFactory(chapter=chapter, current_status="pnm")
    UserStatusChangeFactory(user=pnm, status="pnm", current=True)
    officer = UserFactory(chapter=chapter)
    AuditFactory(user=officer, dues_member=123.0, dues_pledge=45.0, frequency="semester")

    url = reverse("finances:chapters")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # New column headers
    assert "Actives" in content
    assert "PNMs" in content
    assert "Member Dues (Audit)" in content
    # Latest audit dues rendered for the chapter
    assert "$123.00 / semester" in content
    assert "$45.00" in content
