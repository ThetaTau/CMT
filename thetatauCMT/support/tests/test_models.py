import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.models import ChapterSupportAssignment, SupportDigestEntry
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, SupportDigestEntryFactory, give_css_role, make_css

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2026, 10, 22)


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def test_current_upcoming_and_ended_querysets():
    css = make_css()
    alpha, beta, delta, epsilon = (ChapterFactory(name=name) for name in ("alpha", "beta", "delta", "epsilon"))
    open_ended = ChapterSupportAssignmentFactory(user=css, chapter=alpha, start=_days(-10))
    ends_later = ChapterSupportAssignmentFactory(user=css, chapter=beta, start=_days(-10), end=_days(5))
    ended = ChapterSupportAssignmentFactory(user=css, chapter=delta, start=_days(-30), end=_days(-1))
    upcoming = ChapterSupportAssignmentFactory(user=css, chapter=epsilon, start=_days(3))
    assignments = ChapterSupportAssignment.objects.filter(user=css)

    assert set(assignments.current()) == {open_ended, ends_later}
    assert set(assignments.ended()) == {ended}
    assert set(assignments.upcoming()) == {upcoming}
    # The last day of an assignment still counts, the day after does not.
    assert set(assignments.current(on=_days(5))) == {open_ended, ends_later, upcoming}
    assert set(assignments.current(on=_days(6))) == {open_ended, upcoming}


def test_one_open_assignment_per_person_and_chapter():
    assignment = ChapterSupportAssignmentFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        ChapterSupportAssignment.objects.create(user=assignment.user, chapter=assignment.chapter)


def test_ended_assignments_do_not_block_a_new_one():
    assignment = ChapterSupportAssignmentFactory(start=_days(-20), end=_days(-10))
    again = ChapterSupportAssignment(user=assignment.user, chapter=assignment.chapter, start=_days(-5))
    again.full_clean()
    again.save()

    assert list(ChapterSupportAssignment.objects.filter(user=assignment.user).current()) == [again]


def test_database_refuses_an_end_before_the_start():
    assignment = ChapterSupportAssignmentFactory()
    assignment.end = assignment.start - datetime.timedelta(days=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        assignment.save()


def test_clean_refuses_an_end_before_the_start():
    assignment = ChapterSupportAssignmentFactory.build(
        user=make_css(), chapter=ChapterFactory(), start=_days(0), end=_days(-1)
    )
    with pytest.raises(ValidationError) as error:
        assignment.full_clean()
    assert "end" in error.value.message_dict


def test_clean_refuses_an_inactive_chapter():
    closed = ChapterFactory(name="omega", active=False)
    assignment = ChapterSupportAssignment(user=make_css(), chapter=closed)
    with pytest.raises(ValidationError) as error:
        assignment.full_clean()
    assert error.value.message_dict["chapter"] == ["Only active chapters can be assigned."]


def test_an_assignment_can_still_be_ended_after_its_chapter_closes():
    assignment = ChapterSupportAssignmentFactory()
    assignment.chapter.active = False
    assignment.chapter.save()

    assignment.end = timezone.localdate()
    assignment.full_clean()
    assignment.save()


def test_an_assignment_can_still_be_ended_after_the_role_ends():
    assignment = ChapterSupportAssignmentFactory()
    assignment.user.roles.update(end=_days(-1))

    assignment.end = _days(-1)
    assignment.full_clean()


def test_clean_refuses_the_persons_own_member_chapter():
    member = UserFactory(status="alumni")
    give_css_role(member)
    assignment = ChapterSupportAssignment(user=member, chapter=member.chapter)
    with pytest.raises(ValidationError) as error:
        assignment.full_clean()
    assert error.value.message_dict["chapter"] == [
        "This is the person's own chapter, so it cannot be assigned to them."
    ]


def test_a_member_who_holds_the_role_can_support_another_chapter():
    member = UserFactory(status="alumni", chapter=ChapterFactory(name="alpha"))
    give_css_role(member)
    assignment = ChapterSupportAssignment(user=member, chapter=ChapterFactory(name="beta"))
    assignment.full_clean()


def test_clean_requires_the_role_on_the_start_date():
    no_role = UserFactory(status="css")
    assignment = ChapterSupportAssignment(user=no_role, chapter=ChapterFactory())
    with pytest.raises(ValidationError) as error:
        assignment.full_clean()
    assert "user" in error.value.message_dict

    later_role = UserFactory(status="css")
    give_css_role(later_role, start=_days(10))
    too_early = ChapterSupportAssignment(user=later_role, chapter=ChapterFactory(), start=_days(0))
    with pytest.raises(ValidationError):
        too_early.full_clean()
    on_time = ChapterSupportAssignment(user=later_role, chapter=ChapterFactory(), start=_days(10))
    on_time.full_clean()


def test_clean_refuses_overlapping_dates_for_the_same_chapter():
    first = ChapterSupportAssignmentFactory(start=_days(-30), end=_days(10))
    overlapping = ChapterSupportAssignment(user=first.user, chapter=first.chapter, start=_days(5), end=_days(40))
    with pytest.raises(ValidationError) as error:
        overlapping.full_clean()
    assert "start" in error.value.message_dict

    after = ChapterSupportAssignment(user=first.user, chapter=first.chapter, start=_days(11))
    after.full_clean()


def test_editing_an_assignment_does_not_overlap_itself():
    assignment = ChapterSupportAssignmentFactory(start=_days(-30))
    assignment.notes = "Weekly calls with the Regent."
    assignment.full_clean()


def test_is_current_and_str():
    css = make_css(name="Casey Support")
    alpha = ChapterFactory(name="alpha")
    assignment = ChapterSupportAssignmentFactory(
        user=css, chapter=alpha, start=TODAY, end=TODAY + datetime.timedelta(days=30)
    )

    assert str(assignment) == f"Casey Support supports {alpha} from 2026-10-22 to 2026-11-21"
    assert assignment.is_current(on=TODAY)
    assert not assignment.is_current(on=TODAY - datetime.timedelta(days=1))
    assert not assignment.is_current(on=TODAY + datetime.timedelta(days=31))
    assignment.end = None
    assert str(assignment) == f"Casey Support supports {alpha} from 2026-10-22"


def test_digest_entries_default_to_digest_only_and_sort_oldest_first():
    newer = SupportDigestEntryFactory()
    older = SupportDigestEntryFactory(user=newer.user, created=timezone.now() - datetime.timedelta(hours=2))

    assert newer.realtime is False
    assert newer.daily_sent_at is None and newer.monthly_sent_at is None
    assert list(SupportDigestEntry.objects.filter(user=newer.user)) == [older, newer]
    assert str(newer).startswith(f"Monthly chapter officer email for {newer.user} ({newer.chapter}): ")
