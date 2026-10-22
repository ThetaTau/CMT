import datetime
import json
from unittest import mock

import pytest
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.forms import BooleanField
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import CSS_ROLE
from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.biglittle.services import can_manage, can_view_tree
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.forms.flows import ReassignTaskView
from thetatauCMT.forms.forms import RiskManagementForm, UserSelectForm
from thetatauCMT.forms.models import RiskManagement
from thetatauCMT.forms.views import AuditFormView
from thetatauCMT.submissions.models import Submission
from thetatauCMT.support.services import CSS_MANAGERS_CONFIG_KEY, can_manage_css
from thetatauCMT.tasks.models import TaskChapter
from thetatauCMT.transitions import services as transitions
from thetatauCMT.transitions.models import ReportObligation, ReportTemplate, TransitionReport
from thetatauCMT.users.models import CONTACT_VISIBILITY_NO_ONE, User, UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, make_css

pytestmark = pytest.mark.django_db


def _fresh(user):
    return User.objects.get(pk=user.pk)


def assigned_css(*names):
    css = make_css()
    chapters = [ChapterFactory(name=name) for name in names]
    for chapter in chapters:
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
    return _fresh(css), chapters


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


# --- contact details (S11) ----------------------------------------------------------------


def test_a_css_sees_contact_details_in_assigned_chapters_only():
    css, (alpha,) = assigned_css("alpha")
    in_alpha = UserFactory(chapter=alpha, status="active", phone_visibility=CONTACT_VISIBILITY_NO_ONE)
    elsewhere = UserFactory(chapter=ChapterFactory(name="delta"), status="active")

    assert in_alpha.contact_visible_to(css, CONTACT_VISIBILITY_NO_ONE)
    assert not elsewhere.contact_visible_to(css, CONTACT_VISIBILITY_NO_ONE)


# --- transition reports (Q2 b, Q20) --------------------------------------------------------


def _report(chapter, author, position_key="treasurer"):
    due_date = timezone.localdate() + datetime.timedelta(days=10)
    obligation = ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        officer=author,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=30),
        due_date=due_date,
        is_required=True,
        status="open",
    )
    template, _ = ReportTemplate.objects.get_or_create(
        position_type="CHAPTER_OFFICER", position_key=position_key, defaults={"name": f"{position_key} report"}
    )
    return TransitionReport.objects.create(
        obligation=obligation,
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key=position_key,
        author=author,
        template=template,
        template_version=1,
        status="submitted",
        submitted_at=timezone.now(),
    )


def test_a_css_reads_every_officers_reports_for_assigned_chapters_only():
    css, (alpha,) = assigned_css("alpha")
    delta = ChapterFactory(name="delta")
    in_alpha = _report(alpha, UserFactory(chapter=alpha))
    in_delta = _report(delta, UserFactory(chapter=delta))

    readable = transitions.get_readable_reports(css)
    assert in_alpha in readable and in_delta not in readable
    assert transitions.can_view_chapter_dashboard(css, alpha)
    assert not transitions.can_view_chapter_dashboard(css, delta)


def test_a_css_cannot_close_a_vacant_report():
    css, (alpha,) = assigned_css("alpha")
    vacant = ReportObligation.objects.create(
        chapter=alpha,
        position_type="CHAPTER_OFFICER",
        position_key="scribe",
        officer=None,
        term_start=timezone.localdate(),
        term_end=timezone.localdate() + datetime.timedelta(days=100),
        due_date=timezone.localdate() + datetime.timedelta(days=10),
        is_required=True,
        status="open",
    )

    assert not transitions.can_close_na_vacant(css, vacant)
    assert not transitions.get_vacant_obligations_for_closer(css).exists()


def test_the_transitions_page_shows_the_viewed_chapter(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    response = client.get(reverse("transitions:list"))

    assert response.status_code == 200
    assert response.context["chapter"] == alpha


# --- other checks that read the viewer's own chapter ---------------------------------------


def test_after_the_audit_page_a_css_returns_to_the_viewed_chapter():
    css, (alpha,) = assigned_css("alpha")
    request = RequestFactory().get("/")
    request.user = css
    view = AuditFormView()
    view.request = request

    assert view.get_success_url() == reverse("chapters:audit", kwargs={"slug": alpha.slug})


def test_a_css_sees_assigned_family_trees_but_never_manages_them():
    css, (alpha,) = assigned_css("alpha")
    delta = ChapterFactory(name="delta")

    assert can_view_tree(css, alpha)
    assert not can_view_tree(css, delta)
    assert not can_manage(css, alpha)


# --- ballots (Q3) -----------------------------------------------------------------------------


def _chapter_ballot(**kwargs):
    kwargs.setdefault("due_date", timezone.localdate() + datetime.timedelta(days=5))
    return Ballot.objects.create(
        name=kwargs.pop("name", "Amendment vote"),
        sender="Grand Scribe",
        type="other",
        description="A test ballot.",
        voters="all_chapters",
        **kwargs,
    )


def test_my_ballots_lists_the_chapters_ballots_and_whether_it_voted(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    voted = _chapter_ballot(name="Ballot the chapter voted on")
    _chapter_ballot(name="Ballot still waiting")
    regent = UserFactory(chapter=alpha, status="active")
    BallotComplete.objects.create(ballot=voted, user=regent, role="regent", motion="nay")
    client, _ = auto_login_user(user=css)

    response = client.get(reverse("ballots:votelist"))
    rows = {row.record["name"]: row.get_cell("motion") for row in response.context["table"].rows}

    assert rows == {"Ballot the chapter voted on": "Voted", "Ballot still waiting": "Not yet"}
    assert "Nay" not in response.content.decode()


def test_the_vote_page_tells_a_css_whether_the_chapter_voted_but_not_how(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    ballot = _chapter_ballot()
    regent = UserFactory(chapter=alpha, status="active")
    BallotComplete.objects.create(ballot=ballot, user=regent, role="regent", motion="aye")
    client, _ = auto_login_user(user=css)

    content = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug})).content.decode()

    assert "Chapter Support Specialists cannot vote." in content
    assert f"{alpha.name} has voted." in content
    assert "Aye" not in content
    assert 'name="motion"' not in content


# --- RMP and the NME banner (Q5, S13) --------------------------------------------------------


def test_a_css_must_sign_the_rmp_each_semester(client):
    css, _ = assigned_css("alpha")
    client.force_login(css)

    response = client.get(reverse("home"))

    assert response.status_code == 302 and response["Location"] == reverse("rmp")


def test_a_css_signs_the_rmp_for_their_own_chapter_not_the_viewed_one(client):
    css, (alpha,) = assigned_css("alpha")
    client.force_login(css)
    data = {name: "on" for name, field in RiskManagementForm().fields.items() if isinstance(field, BooleanField)}
    data["typed_name"] = str(css)

    with mock.patch("thetatauCMT.forms.views.retry_google_api"):
        response = client.post(reverse("forms:rmp"), data=data)

    assert response.status_code == 302 and response["Location"] == reverse("home")
    signed = RiskManagement.objects.get(user=css)
    assert signed.submission.chapter == css.chapter
    assert not Submission.objects.filter(chapter=alpha).exists()
    assert not TaskChapter.objects.filter(chapter=alpha).exists()


def test_a_css_sees_the_nme_reminder_as_information_once_per_page(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    client, _ = auto_login_user(user=css)
    reminder = "This chapter has not submitted its New Member Education program this semester."
    callback = {
        "output": "members-by-chapter.figure",
        "outputs": {"id": "members-by-chapter", "property": "figure"},
        "inputs": [
            {"id": "region-slug-store", "property": "data", "value": "support"},
            {"id": "theme-store", "property": "data", "value": "light"},
        ],
        "changedPropIds": ["region-slug-store.data"],
        "state": [],
    }

    with (
        mock.patch("core.middleware.current_term", return_value="fa"),
        mock.patch("core.middleware.current_month", return_value=10),
    ):
        page = client.get(reverse("support:my_chapters"))
        dashboard = client.post(
            "/django_plotly_dash/app/RegionDashboard/_dash-update-component",
            data=json.dumps(callback),
            content_type="application/json",
        )

    assert reminder in _messages(page)
    # The page's copy is still waiting to be shown; the callback adds no second one.
    assert dashboard.status_code == 200 and _messages(dashboard).count(reminder) == 1


# --- Edit My Info (Q5) ------------------------------------------------------------------------


def test_a_css_staff_account_gets_the_short_my_info_page(auto_login_user):
    css, _ = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    response = client.get(reverse("users:detail"))
    assert [template.name for template in response.templates][0] == "support/css_my_info.html"
    assert set(response.context["forms"]) == {"user", "prefs"}

    response = client.post(
        reverse("users:detail"),
        {
            "action": "user",
            "first_name": css.first_name,
            "preferred_name": "",
            "last_name": css.last_name,
            "preferred_pronouns": "they/them",
            "email": css.email,
            "email_visibility": CONTACT_VISIBILITY_NO_ONE,
            "phone_number": "5125551234",
            "phone_visibility": CONTACT_VISIBILITY_NO_ONE,
        },
    )

    assert response.status_code == 302
    assert "Your information was updated." in _messages(response)
    assert _fresh(css).phone_number == "5125551234"


def test_a_member_still_gets_the_full_my_info_page(auto_login_user):
    client, _ = auto_login_user(user=UserFactory(status="active"))

    response = client.get(reverse("users:detail"))

    assert [template.name for template in response.templates][0] == "users/user_detail.html"


# --- workflow tasks (Q21) ---------------------------------------------------------------------


def test_workflow_tasks_cannot_be_reassigned_to_a_css():
    css, _ = assigned_css("alpha")
    member = UserFactory(status="active")
    assert not UserSelectForm(data={"user": css.pk}).is_valid()
    assert UserSelectForm(data={"user": member.pk}).is_valid()

    request = RequestFactory().post("/workflow/task/assign/", {"user": css.pk})
    request.user = UserFactory(status="active")
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    view = ReassignTaskView()
    view.request = request
    view.kwargs = {}
    view.activation = mock.MagicMock()

    response = view.post(request)

    assert response.status_code == 302
    view.activation.assign.assert_not_called()


# --- the CSS role itself (S12, Q6) --------------------------------------------------------------


def test_only_css_managers_can_edit_a_css_role(admin_user):
    css, (alpha,) = assigned_css("alpha")
    role = css.roles.get(role=CSS_ROLE)
    officer = UserFactory(chapter=alpha, status="active")
    UserRoleChange.objects.create(
        user=officer, role="regent", start=timezone.localdate(), end=timezone.localdate() + datetime.timedelta(400)
    )
    manager = UserFactory(status="active", email="manager@example.com")

    assert not role.can_be_edited_by(css)
    assert not role.can_be_edited_by(_fresh(officer))
    assert role.can_be_edited_by(admin_user)
    assert not role.can_be_edited_by(manager)
    Config.objects.create(key=CSS_MANAGERS_CONFIG_KEY, value="<p>manager@example.com</p>", description="test")
    assert role.can_be_edited_by(manager)


@override_settings(EXECUTIVE_DIRECTOR="executive.director@example.com")
def test_css_managers_default_to_the_executive_director_and_accept_roles():
    director = UserFactory(status="alumni", email="executive.director@example.com")
    operations = UserFactory(status="alumni")
    UserRoleChange.objects.create(
        user=operations,
        role="national operations manager",
        start=timezone.localdate(),
        end=timezone.localdate() + datetime.timedelta(400),
    )

    assert can_manage_css(director)
    assert not can_manage_css(_fresh(operations))
    Config.objects.create(
        key=CSS_MANAGERS_CONFIG_KEY, value="<p>National Operations Manager,\nsomeone@example.com</p>", description="t"
    )
    assert can_manage_css(_fresh(operations))
    assert not can_manage_css(director)
