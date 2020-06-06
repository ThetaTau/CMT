"""
https://www.pythoncentral.io/writing-tests-for-your-django-applications-views/
https://django-testing-docs.readthedocs.io/en/latest/views.html
https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Testing
"""

import pytest
from django.urls import reverse
from .factories import ChapterFactory, ChapterCurriculaFactory


@pytest.mark.django_db
def test_chapter_detail_view(auto_login_user):
    client, user = auto_login_user()
    chapter = ChapterFactory()
    url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert f"{chapter.name} in the {chapter.region} Region" in response.content.decode(
        "UTF-8"
    )


def test_chapter_list_view_denied(auto_login_user):
    client, user = auto_login_user()
    url = reverse("chapters:list")
    response_no_redirect = client.get(url)
    assert response_no_redirect.status_code == 302
    assert response_no_redirect.url == r"/"
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert f"Only officers can edit this" in response.content.decode("UTF-8")


def test_chapter_list_view_chapter_officer(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    url = reverse("chapters:list")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert f"Filter Chapters" in response.content.decode("UTF-8")


def test_chapter_list_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    url = reverse("chapters:list")
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert f"Filter Chapters" in response.content.decode("UTF-8")
