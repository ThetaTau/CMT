import pytest
from django.contrib import admin as dj_admin
from django.urls import reverse

from thetatauCMT.trainings.admin import AssignTrainingMixin
from thetatauCMT.trainings.models import Training
from thetatauCMT.users.models import User


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
