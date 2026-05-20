import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.finances.tests.factories import InvoiceFactory


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
