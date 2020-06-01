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
