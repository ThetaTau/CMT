import datetime

import pytest
from django.contrib import admin
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.admin import ChapterSupportAssignmentAdmin, SupportDigestEntryAdmin
from thetatauCMT.support.models import ChapterSupportAssignment, SupportDigestEntry
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, SupportDigestEntryFactory, make_css


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


class _Form:
    def __init__(self, changed_data):
        self.changed_data = changed_data


def test_models_are_registered_with_their_admins():
    assert isinstance(admin.site._registry[ChapterSupportAssignment], ChapterSupportAssignmentAdmin)
    assert isinstance(admin.site._registry[SupportDigestEntry], SupportDigestEntryAdmin)


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_changelist_filters_current_upcoming_and_ended(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    css = make_css()
    current = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="alpha"), start=_days(-5))
    upcoming = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="beta"), start=_days(5))
    ended = ChapterSupportAssignmentFactory(
        user=css, chapter=ChapterFactory(name="delta"), start=_days(-30), end=_days(-1)
    )
    url = reverse("admin:support_chaptersupportassignment_changelist")

    for state, expected in (("current", current), ("upcoming", upcoming), ("ended", ended)):
        response = client.get(url, {"state": state})
        assert response.status_code == 200
        assert list(response.context["cl"].queryset) == [expected]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_add_and_change_pages_load(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    assignment = ChapterSupportAssignmentFactory()

    assert client.get(reverse("admin:support_chaptersupportassignment_add")).status_code == 200
    change = reverse("admin:support_chaptersupportassignment_change", args=[assignment.pk])
    assert client.get(change).status_code == 200


@pytest.mark.django_db
def test_saving_records_who_assigned_and_who_ended(admin_user):
    model_admin = ChapterSupportAssignmentAdmin(ChapterSupportAssignment, admin.site)
    request = RequestFactory().post("/")
    request.user = admin_user
    assignment = ChapterSupportAssignment(user=make_css(), chapter=ChapterFactory())

    model_admin.save_model(request, assignment, form=_Form(["user", "chapter"]), change=False)
    assignment.refresh_from_db()
    assert assignment.created_by == admin_user
    assert assignment.ended_by is None

    assignment.end = timezone.localdate()
    model_admin.save_model(request, assignment, form=_Form(["end"]), change=True)
    assignment.refresh_from_db()
    assert assignment.ended_by == admin_user

    assignment.end = None
    model_admin.save_model(request, assignment, form=_Form(["end"]), change=True)
    assignment.refresh_from_db()
    assert assignment.ended_by is None
    assert assignment.created_by == admin_user


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_page_lists_assignments_only_for_a_css(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    assignment = ChapterSupportAssignmentFactory()
    member = UserFactory(status="active")

    css_page = client.get(reverse("admin:users_user_change", args=[assignment.user.pk]))
    member_page = client.get(reverse("admin:users_user_change", args=[member.pk]))

    # The inline group's id; the model's name also appears in the admin sidebar on every page.
    inline_group = 'id="support_assignments-group"'
    assert css_page.status_code == 200
    assert inline_group in css_page.content.decode()
    assert member_page.status_code == 200
    assert inline_group not in member_page.content.decode()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_digest_entries_are_view_only(auto_login_user, admin_user):
    client, _ = auto_login_user(user=admin_user)
    entry = SupportDigestEntryFactory()
    model_admin = SupportDigestEntryAdmin(SupportDigestEntry, admin.site)
    request = RequestFactory().get("/")
    request.user = admin_user

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, entry)
    assert client.get(reverse("admin:support_supportdigestentry_changelist")).status_code == 200
    assert client.get(reverse("admin:support_supportdigestentry_change", args=[entry.pk])).status_code == 200
