import pytest
from pytest_django.asserts import assertQuerysetEqual
from chapters.tests.factories import ChapterFactory, ChapterCurriculaFactory
from chapters.models import Chapter, ChapterCurricula
from users.models import UserStatusChange


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


@pytest.mark.django_db
def test_get_current_officers_council_previous(chapter, user_factory):
    result = chapter.get_current_officers_council(combine=False)
    assert result[1] is True
    assert result[0].count() == 0
    regent = user_factory.create(
        chapter=chapter, make_officer="regent", make_officer__current=False
    )
    vice = user_factory.create(
        chapter=chapter, make_officer="vice regent", make_officer__current=False
    )
    old_officer_pks = [regent.pk, vice.pk]
    result = chapter.get_current_officers_council(combine=False)
    assert result[1] is True
    assertQuerysetEqual(result[0], old_officer_pks, lambda o: o.pk, ordered=False)


@pytest.mark.django_db
def test_get_current_officers_council(chapter, user_factory):
    result = chapter.get_current_officers_council(combine=False)
    assert result[1] is True
    assert result[0].count() == 0
    regent = user_factory.create(chapter=chapter, make_officer="regent")
    vice = user_factory.create(chapter=chapter, make_officer="vice regent")
    treasurer = user_factory.create(chapter=chapter, make_officer="treasurer")
    scribe = user_factory.create(chapter=chapter, make_officer="scribe")
    corsec = user_factory.create(
        chapter=chapter, make_officer="corresponding secretary"
    )
    officer_pks = [regent.pk, vice.pk, treasurer.pk, scribe.pk, corsec.pk]
    result = chapter.get_current_officers_council(combine=False)
    assert result[1] is False
    assertQuerysetEqual(result[0], officer_pks, lambda o: o.pk, ordered=False)
    result = chapter.get_current_officers_council_specific()
    assert [regent, scribe, vice, treasurer] == result


def make_many_users_status(user_factory, chapter, testing):
    expected_users = []
    for status in UserStatusChange.STATUS:
        status = status[0]
        users = user_factory.create_batch(10, chapter=chapter, status=status)
        if status in testing:
            expected_users.extend(users)
    return expected_users


@pytest.mark.django_db
def test_current_members(chapter, user_factory):
    result = chapter.current_members()
    assert result.count() == 0
    testing = ["active", "activepend", "alumnipend", "pnm"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.current_members()
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_actives(chapter, user_factory):
    result = chapter.actives()
    assert result.count() == 0
    testing = ["active", "activepend", "alumnipend"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.actives()
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_active_actives(chapter, user_factory):
    result = chapter.active_actives()
    assert result.count() == 0
    testing = ["active", "activepend"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.active_actives()
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_pledges(chapter, user_factory):
    result = chapter.pledges()
    assert result.count() == 0
    testing = ["pnm"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.pledges()
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_advisors_all(chapter, user_factory):
    result = chapter.advisors
    assert result.count() == 0
    testing = ["advisor"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.advisors
    assert set(expected_users) == set(result)
    users = user_factory.create_batch(5, chapter=chapter, make_officer="advisor")
    expected_users.extend(users)
    result = chapter.advisors
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_advisors_external(chapter, user_factory):
    result = chapter.advisors_external
    assert result.count() == 0
    testing = ["advisor"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.advisors_external
    assert set(expected_users) == set(result)
    # External advisors should NOT include members with advisor role
    user_factory.create_batch(5, chapter=chapter, make_officer="advisor")
    result = chapter.advisors_external
    assert set(expected_users) == set(result)
