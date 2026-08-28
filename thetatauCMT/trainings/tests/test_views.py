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
from thetatauCMT.users.models import User
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
