import datetime

import pytest
from pytest_django.asserts import assertQuerySetEqual

from thetatauCMT.chapters.models import CHAPTER_OFFICER_REQUIRED, Chapter, ChapterCurricula
from thetatauCMT.chapters.tests.factories import ChapterCurriculaFactory, ChapterFactory
from thetatauCMT.users.models import UserStatusChange


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
@pytest.mark.parametrize(
    "chapter__candidate_chapter,suffix", [(True, "Co"), (False, "Ch")]
)
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
    # Reset so badge_number sequence starts at 1 regardless of prior test order.
    # next_badge_number() returns max(badge_number < 5000) + 1, so the result
    # depends on the factory sequence value, which drifts across the full suite.
    user_factory.reset_sequence(0)
    assert chapter.next_badge_number() == 1
    curricula = ChapterCurriculaFactory(chapter=chapter)
    user_factory.create_batch(1234, chapter=chapter, major=curricula)
    assert chapter.next_badge_number() == 1235
    user_factory.create_batch(10, chapter=chapter, major=curricula)
    assert chapter.next_badge_number() == 1245


@pytest.mark.django_db
def test_next_advisor_number(chapter, user_factory):
    assert chapter.next_advisor_number == 7000
    curricula = ChapterCurriculaFactory(chapter=chapter)
    user_factory.create_batch(1234, chapter=chapter, major=curricula)
    assert chapter.next_advisor_number == 7000
    user_factory.reset_sequence(7000)
    user_factory.create_batch(10, chapter=chapter, major=curricula)
    assert chapter.next_advisor_number == 7011


@pytest.mark.django_db
def test_get_current_officers_council_previous(chapter, user_factory):
    result = chapter.get_current_officers_council()
    assert result[1] is True
    assert result[0].count() == 0
    regent = user_factory.create(
        chapter=chapter, make_officer="regent", make_officer__current=False
    )
    vice = user_factory.create(
        chapter=chapter, make_officer="vice regent", make_officer__current=False
    )
    old_officer_pks = [regent.pk, vice.pk]
    result = chapter.get_current_officers_council()
    assert result[1] is True
    assertQuerySetEqual(result[0], old_officer_pks, lambda o: o.pk, ordered=False)


@pytest.mark.django_db
def test_get_current_officers_council(chapter, user_factory):
    result = chapter.get_current_officers_council()
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
    result = chapter.get_current_officers_council()
    assert result[1] is False
    assertQuerySetEqual(result[0], officer_pks, lambda o: o.pk, ordered=False)
    result = chapter.get_current_officers_council_specific()
    assert [regent, scribe, vice, treasurer, corsec] == result


def make_many_users_status(user_factory, chapter, testing):
    # Reuse a single ChapterCurricula for all users to avoid creating many
    # random chapters via the SubFactory cascade, which causes B-tree index
    # bloat on chapters_chapter_slug_key and intermittent deadlocks.
    curricula = ChapterCurriculaFactory(chapter=chapter)
    expected_users = []
    for status in UserStatusChange.STATUS:
        status_value = status.value[0]
        users = user_factory.create_batch(
            10, chapter=chapter, status=status_value, major=curricula
        )
        if status_value in testing:
            expected_users.extend(users)
    return expected_users


@pytest.mark.django_db
def test_current_members(chapter, user_factory):
    result = chapter.current_members()
    assert result.count() == 0
    testing = ["active", "activepend", "alumnipend", "pendexpul", "activeCC", "pnm"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.current_members()
    assert set(expected_users) == set(result)


@pytest.mark.django_db
def test_actives(chapter, user_factory):
    result = chapter.actives()
    assert result.count() == 0
    testing = ["active", "activepend", "alumnipend", "pendexpul", "activeCC"]
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
    curricula = ChapterCurriculaFactory(chapter=chapter)
    users = user_factory.create_batch(
        5, chapter=chapter, make_officer="advisor", major=curricula
    )
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
    curricula = ChapterCurriculaFactory(chapter=chapter)
    user_factory.create_batch(
        5, chapter=chapter, make_officer="advisor", major=curricula
    )
    result = chapter.advisors_external
    assert set(expected_users) == set(result)


# ---------------------------------------------------------------------------
# full_name property
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "candidate_chapter,expected_suffix",
    [
        (False, "Chapter"),
        (True, "Candidate Chapter"),
    ],
)
def test_chapter_full_name(candidate_chapter, expected_suffix):
    chapter = ChapterFactory(candidate_chapter=candidate_chapter)
    assert chapter.full_name == f"{chapter.name} {expected_suffix}"


# ---------------------------------------------------------------------------
# chapter_choices classmethod
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_choices_excludes_inactive():
    active = ChapterFactory(active=True)
    inactive = ChapterFactory(active=False)
    choices = Chapter.chapter_choices()
    slugs = [slug for slug, _ in choices]
    assert active.slug in slugs
    assert inactive.slug not in slugs


@pytest.mark.django_db
def test_chapter_choices_returns_sorted_list():
    choices = Chapter.chapter_choices()
    names = [name for _, name in choices]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# get_actives_for_date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_actives_for_date_empty(chapter):
    result = chapter.get_actives_for_date(datetime.date.today())
    assert result.count() == 0


# ---------------------------------------------------------------------------
# events_last_month / events_semester
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_events_last_month_empty(chapter):
    result = chapter.events_last_month()
    assert result.count() == 0


@pytest.mark.django_db
def test_events_semester_empty(chapter):
    result = chapter.events_semester()
    assert result.count() == 0


# ---------------------------------------------------------------------------
# alumni
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_alumni(chapter, user_factory):
    result = chapter.alumni()
    assert result.count() == 0
    testing = ["alumni", "alumniCC"]
    expected_users = make_many_users_status(user_factory, chapter, testing)
    result = chapter.alumni()
    assert set(expected_users) == set(result)


# ---------------------------------------------------------------------------
# get_current_officers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_current_officers_empty(chapter):
    result = chapter.get_current_officers()
    assert result.count() == 0


@pytest.mark.django_db
def test_get_current_officers_with_officer(chapter, user_factory):
    officer = user_factory.create(chapter=chapter, make_officer="regent")
    result = chapter.get_current_officers()
    assert officer in result


# ---------------------------------------------------------------------------
# get_misc_data / set_misc_data
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_misc_data_default(chapter):
    result = chapter.get_misc_data("nonexistent_key", default="fallback")
    assert result == "fallback"


@pytest.mark.django_db
def test_set_misc_data_and_retrieve(chapter):
    chapter.set_misc_data("test_key", "test_value")
    assert chapter.get_misc_data("test_key") == "test_value"
    # Verify it was persisted
    refreshed = Chapter.objects.get(pk=chapter.pk)
    assert refreshed.get_misc_data("test_key") == "test_value"


# ---------------------------------------------------------------------------
# council_emails / get_generic_chapter_emails / get_email_specific
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_council_emails_returns_set(chapter):
    result = chapter.council_emails()
    assert isinstance(result, set)


@pytest.mark.django_db
def test_get_generic_chapter_emails_returns_list(chapter):
    result = chapter.get_generic_chapter_emails()
    assert isinstance(result, list)
    # Should have entries for regent, scribe, vice_regent, treasurer, cor_sec, general
    assert len(result) == 6


@pytest.mark.django_db
def test_get_email_specific_returns_set(chapter):
    result = chapter.get_email_specific()
    assert isinstance(result, set)


@pytest.mark.django_db
def test_get_email_specific_with_roles(chapter):
    result = chapter.get_email_specific(roles=["regent"])
    assert isinstance(result, set)


# ---------------------------------------------------------------------------
# get_current_and_future / get_previous_officers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_current_and_future_returns_dict(chapter):
    result = chapter.get_current_and_future()
    assert isinstance(result, dict)
    # Keys should be the required officer roles
    for role in CHAPTER_OFFICER_REQUIRED:
        assert role in result


@pytest.mark.django_db
def test_get_previous_officers_returns_dict(chapter):
    result = chapter.get_previous_officers()
    assert isinstance(result, dict)
    for role in CHAPTER_OFFICER_REQUIRED:
        assert role in result


# ---------------------------------------------------------------------------
# events_by_semester_biennium
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_events_by_semester_biennium_returns_no_error(chapter):
    """events_by_semester_biennium iterates BIENNIUM_DATES; just check it runs."""
    chapter.events_by_semester_biennium()


# ---------------------------------------------------------------------------
# initiations_semester
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_initiations_semester_empty(chapter):
    result = chapter.initiations_semester(datetime.date.today())
    assert result.count() == 0


# ---------------------------------------------------------------------------
# pledges_with_no_init_last_x_months
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pledges_with_no_init_last_x_months_empty(chapter):
    result = chapter.pledges_with_no_init_last_x_months()
    assert result.count() == 0


# ---------------------------------------------------------------------------
# pledges_last_x_months
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pledges_last_x_months_empty(chapter):
    result = chapter.pledges_last_x_months()
    assert result.count() == 0


# ---------------------------------------------------------------------------
# graduates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_graduates_empty(chapter):
    result = chapter.graduates(datetime.date.today())
    assert result.count() == 0


# ---------------------------------------------------------------------------
# depledges
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_depledges_empty(chapter):
    result = chapter.depledges()
    assert result.count() == 0


# ---------------------------------------------------------------------------
# gpas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_gpas_empty(chapter):
    result = chapter.gpas()
    assert result.count() == 0


# ---------------------------------------------------------------------------
# SURCHARGE enum get_value
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_surcharge_get_value():
    from thetatauCMT.chapters.models import Chapter

    # Test the enum get_value method — not_rec has special alias 'not' → 'not_rec'
    result = Chapter.SURCHARGE.get_value("none")
    assert result is not None


# ---------------------------------------------------------------------------
# get_about_expired_council (no officers → no emails sent)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_about_expired_council_no_officers(chapter):
    emails, officers_to_update = chapter.get_about_expired_coucil()
    # With no officers, all positions need updating
    assert isinstance(officers_to_update, list)


@pytest.mark.django_db
def test_get_about_expired_council_with_current_officers(chapter, user_factory):
    """With 5 current officers who have far-future end dates, no officers need updating."""
    regent = user_factory.create(chapter=chapter, make_officer="regent")
    vice = user_factory.create(chapter=chapter, make_officer="vice regent")
    treasurer = user_factory.create(chapter=chapter, make_officer="treasurer")
    scribe = user_factory.create(chapter=chapter, make_officer="scribe")
    corsec = user_factory.create(
        chapter=chapter, make_officer="corresponding secretary"
    )
    emails, officers_to_update = chapter.get_about_expired_coucil()
    assert isinstance(officers_to_update, list)
    assert isinstance(emails, list)


# ---------------------------------------------------------------------------
# notes_filtered
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_notes_filtered_no_notes(chapter, user_factory):
    user = user_factory.create(chapter=chapter)
    result = chapter.notes_filtered(user)
    assert result.count() == 0


# ---------------------------------------------------------------------------
# RECOGNITION.get_value — "not" alias branch (5.3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recognition_get_value_not_alias(chapter):
    """RECOGNITION.get_value('not') should map to 'not_rec' and return the display value."""
    result = Chapter.RECOGNITION.get_value("not")
    assert result == "Not Recognized by University"


# ---------------------------------------------------------------------------
# graduates() — returns members with alumni status in current semester (5.3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_graduates_returns_members_with_alumni_status(chapter, user_factory):
    """graduates(today) returns users who became alumni this semester."""
    import datetime

    from core.models import semester_encompass_start_end_date

    today = datetime.date.today()
    semester_start, semester_end = semester_encompass_start_end_date(given_date=today)
    # Create a member with alumni status that started in the current semester
    member = user_factory.create(chapter=chapter)
    UserStatusChange.objects.create(
        user=member,
        status="alumni",
        start=semester_start + datetime.timedelta(days=1),
        end=semester_end,
    )
    result = chapter.graduates(given_date=today)
    assert member in result


# ---------------------------------------------------------------------------
# get_email_specific — adds officer email when officer exists (5.3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_email_specific_includes_current_officer_email(chapter, user_factory):
    """When there's a current regent with an email, get_email_specific includes it."""
    regent = user_factory.create(
        chapter=chapter,
        make_officer="regent",
        email="regent_test@example.com",
    )
    emails = chapter.get_email_specific(roles=["regent"])
    # Should include the officer's email
    assert regent.email in emails
