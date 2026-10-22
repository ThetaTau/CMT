import datetime

import pytest
from django.utils import timezone

from core.models import (
    ADVISOR_ROLES,
    ALL_OFFICERS,
    ALL_ROLES,
    ALL_ROLES_CHOICES,
    CHAPTER_OFFICER,
    CHAPTER_ROLES,
    CHAPTER_ROLES_CHOICES,
    COUNCIL,
    CSS_ROLE,
    CSS_STANDS_IN_AS,
    NAT_OFFICERS,
    SUPPORT_ROLES,
    user_is_national_officer,
)
from thetatauCMT.forms.models import StatusChange
from thetatauCMT.users.forms import status_options
from thetatauCMT.users.models import UserStatusChange

from .factories import give_css_role, make_css


def test_css_role_is_a_known_role_outside_every_officer_and_advisor_set():
    assert SUPPORT_ROLES == {CSS_ROLE}
    assert CSS_STANDS_IN_AS == "regent"
    assert CSS_ROLE in ALL_ROLES
    assert (CSS_ROLE, "Chapter Support Specialist") in ALL_ROLES_CHOICES
    for role_set in (NAT_OFFICERS, COUNCIL, CHAPTER_OFFICER, CHAPTER_ROLES, ADVISOR_ROLES, ALL_OFFICERS):
        assert CSS_ROLE not in role_set
    # Chapter officers pick roles from CHAPTER_ROLES_CHOICES, so they cannot hand it out.
    assert CSS_ROLE not in dict(CHAPTER_ROLES_CHOICES)


@pytest.mark.django_db
def test_the_css_role_never_puts_the_person_in_the_officer_or_natoff_group():
    css = make_css()

    assert CSS_ROLE in css.current_roles
    assert not css.groups.filter(name__in=["officer", "natoff"]).exists()
    assert css.officer is False
    assert not css.is_officer
    assert not css.is_national_officer()
    assert user_is_national_officer(css) is False


@pytest.mark.django_db
def test_ending_the_css_role_removes_it_from_current_roles():
    css = make_css()
    role = css.roles.get(role=CSS_ROLE)
    role.end = timezone.localdate() - datetime.timedelta(days=1)
    role.save()

    css.refresh_from_db()
    assert CSS_ROLE not in (css.current_roles or [])


@pytest.mark.django_db
def test_a_member_keeps_their_status_and_chapter_when_given_the_role():
    from thetatauCMT.users.tests.factories import UserFactory

    member = UserFactory(status="alumni")
    chapter_id = member.chapter_id
    give_css_role(member)

    member.refresh_from_db()
    assert member.current_status == "alumni"
    assert member.chapter_id == chapter_id
    assert CSS_ROLE in member.current_roles


def test_css_status_is_labelled_and_only_admin_forms_offer_it():
    assert UserStatusChange.STATUS.get_value("css") == "Chapter Support Specialist"
    assert ("css", "Chapter Support Specialist") in status_options()
    # The chapter officers' status change form offers reasons, not statuses.
    assert "css" not in [reason.value[0] for reason in StatusChange.REASONS]


@pytest.mark.django_db
def test_random_factories_never_make_someone_a_css():
    from thetatauCMT.users.tests.factories import UserRoleChangeFactory, UserStatusChangeFactory

    roles = {UserRoleChangeFactory().role for _ in range(60)}
    statuses = {UserStatusChangeFactory().status for _ in range(60)}

    assert CSS_ROLE not in roles
    assert "css" not in statuses
