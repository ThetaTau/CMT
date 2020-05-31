import pytest
from chapters.tests.factories import ChapterFactory, ChapterCurriculaFactory
from chapters.models import Chapter, ChapterCurricula


@pytest.mark.django_db
def test_chapter_factory(chapter_factory):
    assert chapter_factory == ChapterFactory


@pytest.mark.django_db
def test_chapter_instance(chapter):
    assert isinstance(chapter, Chapter)


@pytest.mark.django_db
def test_chapter_curricula_factory(chapter_curricula_factory):
    assert chapter_curricula_factory == ChapterCurriculaFactory


@pytest.mark.django_db
def test_chapter_curricula_instance(chapter_curricula):
    assert isinstance(chapter_curricula, ChapterCurricula)


@pytest.mark.django_db
@pytest.mark.parametrize("chapter__name", ["Xi Beta"])
def test_chapter_str(chapter):
    assert chapter.name == "Xi Beta"
    assert str(chapter) == "Xi Beta"


@pytest.mark.django_db
@pytest.mark.parametrize("chapter_curricula__major", ["Electrical Engineering"])
def test_chapter_curricula_str(chapter_curricula):
    assert chapter_curricula.major == "Electrical Engineering"
    assert str(chapter_curricula) == "Electrical Engineering"
