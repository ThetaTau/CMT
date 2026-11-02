from io import StringIO

import pytest
from django.core.management import call_command

from thetatauCMT.trainings.models import EdCourse, Training
from thetatauCMT.users.tests.factories import UserFactory


@pytest.fixture
def recorded_enrollments(monkeypatch):
    """Stub Open edX: map each enrolled user's pk to the course ids it was sent."""
    calls = {}
    monkeypatch.setattr(Training, "_ed_authenticate_header", staticmethod(lambda: {"Authorization": "JWT t"}))

    def fake_enroll(user, courses=None, header=None, request=None):
        calls[user.pk] = sorted(courses)
        return [(course_id, "pending", "") for course_id in courses]

    monkeypatch.setattr(Training, "enroll_user_ed", staticmethod(fake_enroll))
    return calls


@pytest.mark.django_db
def test_enroll_all_ed_applies_every_member_and_role_rules(recorded_enrollments):
    EdCourse.objects.all().delete()
    everyone = EdCourse.objects.create(
        course_id="course-v1:ThetaTau+TT101+intro", title="Intro", assign_to_all_members=True
    )
    treasurers = EdCourse.objects.create(
        course_id="course-v1:ThetaTau+TT801+money", title="Money", assign_to_roles=["treasurer"]
    )
    EdCourse.objects.create(
        course_id="course-v1:ThetaTau+TT802+old", title="Old", assign_to_roles=["treasurer"], active=False
    )
    member = UserFactory.create()
    treasurer = UserFactory.create(current_roles=["treasurer"])

    call_command("enroll_all_ed", stdout=StringIO())

    assert recorded_enrollments[member.pk] == [everyone.course_id]
    assert recorded_enrollments[treasurer.pk] == sorted([everyone.course_id, treasurers.course_id])


@pytest.mark.django_db
def test_enroll_all_ed_gives_new_member_and_national_officer_courses_only_to_current_holders(recorded_enrollments):
    EdCourse.objects.all().delete()
    new_members = EdCourse.objects.create(
        course_id="course-v1:ThetaTau+HS101+online", title="New member H&S", assign_to_new_members=True
    )
    natoffs = EdCourse.objects.create(
        course_id="course-v1:ThetaTau+NO101+natoff", title="NatOff 101", assign_to_national_officers=True
    )
    pnm = UserFactory.create(current_status="pnm")
    regional_director = UserFactory.create(current_status="alumni", current_roles=["regional director"])
    active = UserFactory.create(current_status="active", current_roles=["regent"])

    call_command("enroll_all_ed", stdout=StringIO())

    assert recorded_enrollments[pnm.pk] == [new_members.course_id]
    assert recorded_enrollments[regional_director.pk] == [natoffs.course_id]
    assert active.pk not in recorded_enrollments


@pytest.mark.django_db
def test_enroll_all_ed_course_option_limits_the_run_to_that_course(recorded_enrollments):
    EdCourse.objects.all().delete()
    EdCourse.objects.create(course_id="course-v1:ThetaTau+TT101+intro", title="Intro", assign_to_all_members=True)
    treasurers = EdCourse.objects.create(
        course_id="course-v1:ThetaTau+TT801+money", title="Money", assign_to_roles=["treasurer"]
    )
    member = UserFactory.create()
    treasurer = UserFactory.create(current_roles=["treasurer"])

    call_command("enroll_all_ed", "--course", treasurers.course_id, stdout=StringIO())

    assert member.pk not in recorded_enrollments
    assert recorded_enrollments[treasurer.pk] == [treasurers.course_id]


@pytest.mark.django_db
def test_enroll_all_ed_does_nothing_without_matching_courses(recorded_enrollments):
    EdCourse.objects.all().delete()
    UserFactory.create()
    out = StringIO()

    call_command("enroll_all_ed", stdout=out)

    assert recorded_enrollments == {}
    assert "Nobody to enroll" in out.getvalue()
