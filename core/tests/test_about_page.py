"""The About page.

Static prose, but two things about it can break silently: a ``{% url %}`` in it
can start raising ``NoReverseMatch`` on a page anonymous visitors can reach, and
the page can go back to being unreachable -- it shipped as an empty stub that
nothing linked to.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_about_renders_for_an_anonymous_visitor(client):
    """This is the "what is this thing?" page, so it cannot be login-gated."""
    response = client.get(reverse("about"))

    assert response.status_code == 200
    assert "Chapter Management Tool" in response.content.decode()


@pytest.mark.django_db
def test_about_asks_for_help_on_github(client):
    body = client.get(reverse("about")).content.decode()

    assert "github.com/VenturaFranklin/thetatauCMT/issues" in body
    assert "CONTRIBUTING.md" in body
    assert "cmt@thetatau.org" in body


@pytest.mark.django_db
def test_the_footer_links_about_from_every_page(client):
    """An unlinked page is an unread page; that is how this one sat empty."""
    assert f'href="{reverse("about")}"' in client.get(reverse("help")).content.decode()


@pytest.mark.django_db
def test_about_does_not_send_an_anonymous_reader_to_a_login_wall(client):
    """``RoleGuideIndexView`` is login-required while this page is not."""
    body = client.get(reverse("about")).content.decode()

    assert f'href="{reverse("guides:role-guides")}"' not in body
    assert reverse("account_login") in body


def test_about_links_the_role_guides_once_you_are_signed_in(db, client):
    from core.tests.test_journeys import _setup_user

    client.force_login(_setup_user())

    body = client.get(reverse("about")).content.decode()

    assert f'href="{reverse("guides:role-guides")}"' in body
