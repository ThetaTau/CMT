import datetime

import pytest
from django.contrib import admin as dj_admin
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.tests.factories import InitiationFactory
from thetatauCMT.trainings.admin import AssignTrainingMixin
from thetatauCMT.trainings.models import COMMUNITY_EDU_COURSE_ID, COMMUNITY_EDU_COURSE_TITLE, Training
from thetatauCMT.users.models import User, UserStatusChange
from thetatauCMT.users.tests.factories import UserFactory


def _make_natoff(user, client):
    """Ensure user is in the 'natoff' Django group and refresh the session."""
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_admin(user, client, hide_admin=False):
    """Make ``user`` a (optionally hidden) Admin and refresh the session."""
    from thetatauCMT.users.models import UserAlter

    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    if hide_admin:
        UserAlter.objects.create(user=user, chapter=user.chapter, role=None, hide_admin=True)
    client.force_login(user)


@pytest.mark.django_db
def test_training_list_view_authenticated(auto_login_user):
    """Authenticated user can see their training list."""
    client, user = auto_login_user()
    url = reverse("trainings:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_training_list_view_unauthenticated(client):
    url = reverse("trainings:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def _member_with_training(chapter, current_status="active", pnm_starts=()):
    member = UserFactory.create(chapter=chapter, current_status=current_status)
    for start in pnm_starts:
        UserStatusChange.objects.create(user=member, status="pnm", start=start, end=start + datetime.timedelta(days=30))
    Training.objects.create(
        user=member,
        progress_id="p",
        course_id=COMMUNITY_EDU_COURSE_ID,
        course_title=COMMUNITY_EDU_COURSE_TITLE,
        completed=False,
        max_quiz_score=0,
    )
    return member


def _row_for(response, member):
    return next(row for row in response.context["table"].rows if row.record.user_id == member.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pnm_start, semester",
    [
        (datetime.date(2024, 9, 15), "Fall 2024"),
        (datetime.date(2025, 6, 30), "Spring 2025"),
        (datetime.date(2025, 7, 1), "Fall 2025"),
    ],
)
def test_training_list_shows_current_status_and_semester_pledged(auto_login_user, pnm_start, semester):
    client, viewer = auto_login_user()
    member = _member_with_training(viewer.chapter, current_status="activepend", pnm_starts=[pnm_start])

    row = _row_for(client.get(reverse("trainings:list")), member)

    assert (row.get_cell("current_status"), row.get_cell("pledge_semester")) == ("Active Pending", semester)


@pytest.mark.django_db
def test_training_list_semester_pledged_uses_the_most_recent_pnm_status(auto_login_user):
    client, viewer = auto_login_user()
    member = _member_with_training(viewer.chapter, pnm_starts=[datetime.date(2024, 10, 1), datetime.date(2025, 2, 10)])

    row = _row_for(client.get(reverse("trainings:list")), member)

    assert row.get_cell("pledge_semester") == "Spring 2025"


@pytest.mark.django_db
def test_training_list_semester_pledged_is_none_without_a_pnm_status(auto_login_user):
    client, viewer = auto_login_user()
    member = _member_with_training(viewer.chapter)

    row = _row_for(client.get(reverse("trainings:list")), member)

    assert row.get_cell("pledge_semester") == "None"


@pytest.mark.django_db
def test_training_list_sorts_by_current_status_and_semester_pledged(auto_login_user):
    client, viewer = auto_login_user()
    active = _member_with_training(viewer.chapter, current_status="active", pnm_starts=[datetime.date(2021, 9, 1)])
    pnm = _member_with_training(viewer.chapter, current_status="pnm", pnm_starts=[datetime.date(2024, 9, 1)])

    def members_sorted_by(sort):
        response = client.get(reverse("trainings:list"), {"sort": sort})
        assert response.status_code == 200
        return [row.record.user for row in response.context["table"].rows]

    assert members_sorted_by("pledge_semester") == [active, pnm]
    assert members_sorted_by("-current_status") == [pnm, active]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params, shows_everyone",
    [
        ({}, False),
        ({"sort": "pledge_semester"}, False),
        ({"current_status": "roster"}, False),
        ({"current_status": ""}, True),
        ({"cancel": "Clear"}, True),
    ],
)
def test_training_list_defaults_to_active_active_pending_and_prospective(auto_login_user, params, shows_everyone):
    client, viewer = auto_login_user()
    roster_statuses = ("active", "activeCC", "activepend", "pnm")
    roster = {_member_with_training(viewer.chapter, current_status=status) for status in roster_statuses}
    others = {_member_with_training(viewer.chapter, current_status=status) for status in ("depledge", "alumni", "")}

    response = client.get(reverse("trainings:list"), params)

    expected = roster | others if shows_everyone else roster
    assert {row.record.user for row in response.context["table"].rows} == expected


@pytest.mark.django_db
def test_training_list_filters_by_current_status_including_candidate_chapter_variant(auto_login_user):
    client, viewer = auto_login_user()
    active = _member_with_training(viewer.chapter, current_status="active")
    candidate_chapter_active = _member_with_training(viewer.chapter, current_status="activeCC")
    _member_with_training(viewer.chapter, current_status="alumni")

    response = client.get(reverse("trainings:list"), {"current_status": "active"})

    assert {row.record.user for row in response.context["table"].rows} == {active, candidate_chapter_active}


@pytest.mark.django_db
def test_training_list_filters_by_semester_pledged(auto_login_user):
    client, viewer = auto_login_user()
    first_day = _member_with_training(viewer.chapter, pnm_starts=[datetime.date(2024, 7, 1)])
    last_day = _member_with_training(viewer.chapter, pnm_starts=[datetime.date(2024, 12, 31)])
    for start in (datetime.date(2024, 6, 30), datetime.date(2025, 1, 1)):
        _member_with_training(viewer.chapter, pnm_starts=[start])
    _member_with_training(viewer.chapter)

    response = client.get(reverse("trainings:list"), {"pledge_semester": "fa-2024"})

    assert {row.record.user for row in response.context["table"].rows} == {first_day, last_day}


@pytest.mark.django_db
def test_training_list_semester_pledged_choices_are_the_chapters_semesters_newest_first(auto_login_user):
    client, viewer = auto_login_user(user=UserFactory.create(chapter=ChapterFactory.create(name="alpha")))
    for start in (
        datetime.date(2024, 9, 1),
        datetime.date(2025, 8, 1),
        datetime.date(2025, 2, 1),
        datetime.date(2024, 10, 1),
    ):
        _member_with_training(viewer.chapter, pnm_starts=[start])
    _member_with_training(ChapterFactory.create(name="beta"), pnm_starts=[datetime.date(2019, 9, 1)])

    response = client.get(reverse("trainings:list"))

    assert list(response.context["filter"].form.fields["pledge_semester"].choices) == [
        ("", "Any semester pledged"),
        ("fa-2025", "Fall 2025"),
        ("sp-2025", "Spring 2025"),
        ("fa-2024", "Fall 2024"),
    ]


class _RecordingUserAdmin(AssignTrainingMixin, dj_admin.ModelAdmin):
    """Minimal admin combining the mixin so ``message_user`` is available in tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded_messages = []

    def message_user(self, request, message, level=None, extra_tags="", fail_silently=False):
        self.recorded_messages.append((message, level))


@pytest.mark.django_db
def test_assign_training_admin_action_survives_user_error(user_factory, rf, monkeypatch):
    """A failing user in the bulk 'Assign Member Training' action is logged and
    skipped so the batch keeps going and the admin does not get a 500."""
    user1 = user_factory.create()
    user2 = user_factory.create()

    monkeypatch.setattr(
        Training,
        "get_extra_groups",
        staticmethod(lambda: [("risk management chair", "Risk")]),
    )

    processed = []

    def fake_add_user(user, extra_group=None, request=None):
        if user.pk == user1.pk:
            raise ValueError("boom")
        processed.append(user.pk)

    monkeypatch.setattr(Training, "add_user", staticmethod(fake_add_user))

    admin_instance = _RecordingUserAdmin(User, dj_admin.sites.AdminSite())
    request = rf.post(
        "/admin/users/user/",
        data={
            "apply": "1",
            "_selected_action": [user1.pk, user2.pk],
            "training_system": "Vector",
            "extra_group": "risk management chair",
            "new_group": "",
        },
    )
    queryset = User.objects.filter(pk__in=[user1.pk, user2.pk])

    # Must not raise even though user1's sync blows up.
    response = admin_instance.assign_training(request, queryset)

    assert response.status_code == 302  # redirects back to the changelist
    assert processed == [user2.pk]  # user2 still processed after user1 failed
    assert any("failed" in msg.lower() for msg, _level in admin_instance.recorded_messages)


@pytest.mark.django_db
def test_community_edu_completion_view_requires_admin(auto_login_user):
    client, _user = auto_login_user()  # regular member
    response = client.get(reverse("trainings:community_edu_completion"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_community_edu_completion_view_natoff_alone_is_not_enough(auto_login_user):
    """A National Officer who is not also an Admin cannot reach the tool."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.get(reverse("trainings:community_edu_completion"))
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_community_edu_completion_view_hidden_admin_is_redirected(auto_login_user):
    """Toggling 'Hide admin functionality' blocks access, even for a superuser."""
    client, user = auto_login_user()
    _make_admin(user, client, hide_admin=True)
    response = client.get(reverse("trainings:community_edu_completion"))
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_community_edu_completion_view_shows_stats_for_admin(auto_login_user):
    client, user = auto_login_user()
    _make_admin(user, client)
    chapter = ChapterFactory.create()
    today = timezone.now().date()
    completed_user = UserFactory.create(chapter=chapter)
    InitiationFactory.create(user=completed_user, chapter=chapter, date=today - datetime.timedelta(days=30))
    Training.objects.create(
        user=completed_user,
        progress_id="p",
        course_id=COMMUNITY_EDU_COURSE_ID,
        course_title=COMMUNITY_EDU_COURSE_TITLE,
        completed=True,
        max_quiz_score=100,
    )

    response = client.get(reverse("trainings:community_edu_completion"))
    assert response.status_code == 200
    stats_by_chapter = {stat.chapter.pk: stat for stat in response.context["stats"]}
    assert stats_by_chapter[chapter.pk].total == 1
    assert stats_by_chapter[chapter.pk].completed == 1
    assert stats_by_chapter[chapter.pk].surcharge_bracket == "none"


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_community_edu_completion_view_apply_sets_chapter_surcharge(auto_login_user):
    client, user = auto_login_user()
    _make_admin(user, client)
    chapter = ChapterFactory.create(health_safety_surcharge="none")
    today = timezone.now().date()
    for i in range(4):
        member = UserFactory.create(chapter=chapter)
        InitiationFactory.create(user=member, chapter=chapter, date=today - datetime.timedelta(days=10))
        Training.objects.create(
            user=member,
            progress_id="p",
            course_id=COMMUNITY_EDU_COURSE_ID,
            course_title=COMMUNITY_EDU_COURSE_TITLE,
            completed=(i == 0),  # 1/4 = 25% -> L1c
            max_quiz_score=100,
        )

    response = client.post(
        reverse("trainings:community_edu_completion"),
        data={"apply_chapter": str(chapter.pk)},
    )
    assert response.status_code == 200
    chapter.refresh_from_db()
    assert chapter.health_safety_surcharge == "L1c"
