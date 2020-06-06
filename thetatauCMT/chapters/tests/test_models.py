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
@pytest.mark.parametrize("chapter__colony,suffix", [(True, "Co"), (False, "Ch")])
def test_chapter_account(chapter, suffix):
    assert chapter.account == f"{chapter.greek}0{suffix}"


@pytest.mark.django_db
@pytest.mark.parametrize("chapter_curricula__major", ["Electrical Engineering"])
def test_chapter_curricula_str(chapter_curricula):
    assert chapter_curricula.major == "Electrical Engineering"
    assert str(chapter_curricula) == "Electrical Engineering"


@pytest.mark.django_db
def test_get_school_chapter(chapter):
    chapter_result = Chapter.get_school_chapter(chapter.school)
    assert chapter_result == chapter


@pytest.mark.django_db
def test_get_school_chapter_missing():
    with pytest.warns(UserWarning):
        chapter_result = Chapter.get_school_chapter("Does not exist")
    assert chapter_result is None


@pytest.mark.django_db
def test_next_badge_number(chapter, user_factory):
    assert chapter.next_badge_number() == 1
    user_factory.create_batch(1234, chapter=chapter)
    assert chapter.next_badge_number() == 1235
    user_factory.create_batch(10, chapter=chapter)
    assert chapter.next_badge_number() == 1245


@pytest.mark.django_db
def test_next_advisor_number(chapter, user_factory):
    assert chapter.next_advisor_number == 7000
    user_factory.create_batch(1234, chapter=chapter)
    assert chapter.next_advisor_number == 7000
    user_factory.reset_sequence(7000)
    user_factory.create_batch(10, chapter=chapter)
    assert chapter.next_advisor_number == 7011
