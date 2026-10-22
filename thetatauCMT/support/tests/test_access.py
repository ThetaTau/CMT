import ast
import datetime
import pathlib
import re

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import get_resolver, resolve, reverse
from django.urls.resolvers import URLPattern, URLResolver
from django.utils import timezone

from core.models import CSS_STANDS_IN_AS, user_is_national_officer
from core.views import NationalOfficerRequiredMixin, NatOfficerRequiredMixin, OfficerRequiredMixin, group_required
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.middleware import LOCKED_FORM_ATTRIBUTE, ViewOnlyCSSMiddleware, mark_locked_forms
from thetatauCMT.support.services import NOT_CSS, PERSONAL_ACTIONS, VIEW_ONLY_MESSAGE, css_state, is_personal_action
from thetatauCMT.users.models import User, UserAlter
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, central_office, give_css_role, make_css, make_regent

pytestmark = pytest.mark.django_db


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    """A new instance, so the per-request CSS cache starts empty."""
    return User.objects.get(pk=user.pk)


def assigned_css(*names):
    css = make_css()
    chapters = [ChapterFactory(name=name) for name in names]
    for chapter in chapters:
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
    return _fresh(css), chapters


# --- who a CSS is and what they view ---------------------------------------------------


def test_someone_without_the_role_costs_no_queries(django_assert_num_queries):
    member = UserFactory(status="active")
    with django_assert_num_queries(0):
        assert css_state(member) is NOT_CSS


def test_a_css_views_their_first_assigned_chapter_and_stands_in_as_regent():
    css, (beta, alpha) = assigned_css("beta", "alpha")

    state = css_state(css)
    assert state.is_css and state.standing_in
    assert state.chapter_ids == {alpha.pk, beta.pk}
    assert css.current_chapter == alpha
    assert css.chapter_officer() == {CSS_STANDS_IN_AS}
    assert css.is_chapter_officer_group and css.is_officer_group
    # Never a real officer: group membership and the raw property stay untouched.
    assert not css.is_officer
    assert not css.groups.filter(name__in=["officer", "natoff"]).exists()
    assert not user_is_national_officer(css)


def test_the_switcher_choice_is_used_while_it_is_assigned():
    css, (alpha, beta) = assigned_css("alpha", "beta")
    UserAlter.objects.create(user=css, chapter=beta)

    assert _fresh(css).current_chapter == beta


def test_a_stale_switcher_choice_falls_back_to_an_assigned_chapter():
    css, (alpha,) = assigned_css("alpha")
    UserAlter.objects.create(user=css, chapter=ChapterFactory(name="delta"))

    css = _fresh(css)
    assert css.current_chapter == alpha
    assert css_state(css).standing_in


def test_without_assignments_a_css_sees_their_home_chapter_with_no_officer_access():
    css = _fresh(make_css())

    assert css.current_chapter == central_office()
    assert not css_state(css).standing_in
    assert css.chapter_officer() == set()
    assert not css.is_chapter_officer_group


def test_ending_the_assignment_or_the_role_removes_access():
    css, (alpha,) = assigned_css("alpha")
    css.support_assignments.update(start=_days(-10), end=_days(-1))
    assert not css_state(_fresh(css)).standing_in

    css, (beta,) = assigned_css("beta")
    css.roles.update(end=_days(-1))
    assert css_state(_fresh(css)) is NOT_CSS


def test_a_member_css_keeps_their_own_chapter_until_they_switch():
    own = ChapterFactory(name="alpha")
    member = UserFactory(status="alumni", chapter=own)
    give_css_role(member)
    beta = ChapterFactory(name="beta")
    ChapterSupportAssignmentFactory(user=member, chapter=beta)

    member = _fresh(member)
    assert member.current_chapter == own
    assert not css_state(member).standing_in

    UserAlter.objects.create(user=member, chapter=beta)
    member = _fresh(member)
    assert member.current_chapter == beta
    assert css_state(member).standing_in
    assert member.chapter_officer() == {CSS_STANDS_IN_AS}


def test_a_national_officer_who_is_also_a_css_keeps_the_national_switcher():
    css, (alpha,) = assigned_css("alpha")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(css)

    css = _fresh(css)
    state = css_state(css)
    assert state.is_css and alpha.pk in state.chapter_ids
    assert not state.standing_in
    assert css.current_chapter == css.chapter


def test_the_state_is_worked_out_once_per_user_object(django_assert_num_queries):
    css, _ = assigned_css("alpha")
    first = css_state(css)
    with django_assert_num_queries(0):
        assert css_state(css) is first


def test_a_css_home_page_costs_no_more_queries_than_a_national_officers(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    natoff = UserFactory(status="active", chapter=alpha)
    Group.objects.get_or_create(name="natoff")[0].user_set.add(natoff)

    def home_page_queries(user):
        # A CSS's Home redirects to their landing page, so both requests are counted.
        client, _ = auto_login_user(user=user)
        client.get(reverse("home"), follow=True)  # warm the per-process caches first
        with CaptureQueriesContext(connection) as queries:
            assert client.get(reverse("home"), follow=True).status_code == 200
        return len(queries)

    css_queries, natoff_queries = home_page_queries(css), home_page_queries(natoff)
    assert css_queries <= natoff_queries, (css_queries, natoff_queries)


# --- access checks --------------------------------------------------------------------


def _view_classes():
    found = []

    def walk(patterns):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns)
            elif isinstance(pattern, URLPattern):
                view_class = getattr(pattern.callback, "view_class", None)
                if view_class is not None:
                    found.append(view_class)

    walk(get_resolver().url_patterns)
    return set(found)


def _check(view_class, user):
    request = RequestFactory().get("/")
    request.user = user
    view = view_class()
    view.request = request
    return view.check_membership(view.get_group_required())


def test_every_officer_view_lets_a_css_in_and_every_national_view_keeps_them_out():
    css, _ = assigned_css("alpha")
    classes = _view_classes()
    officer_views = {cls for cls in classes if issubclass(cls, OfficerRequiredMixin)}
    natoff_views = {cls for cls in classes if issubclass(cls, NatOfficerRequiredMixin)}
    national_views = {cls for cls in classes if issubclass(cls, NationalOfficerRequiredMixin)}

    assert len(officer_views) >= 15 and len(natoff_views) >= 25 and national_views
    for view_class in officer_views:
        assert _check(view_class, css), view_class.__name__
    for view_class in natoff_views:
        assert not _check(view_class, css), view_class.__name__
    # NationalOfficerRequiredMixin decides with user_is_national_officer.
    assert not user_is_national_officer(css)


def test_a_css_without_assignments_is_not_let_into_officer_views():
    css = _fresh(make_css())
    officer_view = next(cls for cls in _view_classes() if issubclass(cls, OfficerRequiredMixin))
    assert not _check(officer_view, css)


def test_group_required_officer_matches_the_regent():
    def page(request):
        return HttpResponse("ok")

    officer_only = group_required("officer")(page)
    listed = group_required(["officer", "natoff"])(page)
    css, _ = assigned_css("alpha")
    member = UserFactory(status="active")
    factory = RequestFactory()

    request = factory.get("/")
    request.user = css
    assert officer_only(request).status_code == 200
    # The list form matches no group today, so a Regent is turned away too; so is a CSS.
    assert listed(request).status_code == 302
    request = factory.get("/")
    request.user = member
    assert officer_only(request).status_code == 302


# --- view only --------------------------------------------------------------------------


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def test_request_flags_for_a_css(auto_login_user):
    css, _ = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    request = client.get(reverse("home")).wsgi_request
    assert request.is_css and request.is_officer and request.css_view_only
    assert not getattr(request, "is_nat_officer", False)

    no_chapters = _fresh(make_css(email="idle-css@example.com"))
    client.force_login(no_chapters)
    request = client.get(reverse("home")).wsgi_request
    assert request.is_css
    assert not getattr(request, "is_officer", False) and not getattr(request, "css_view_only", False)


def test_a_css_cannot_submit_officer_forms(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    client, _ = auto_login_user(user=css)
    website = alpha.website
    url = reverse("chapters:detail", kwargs={"slug": alpha.slug})

    response = client.post(url, {"action": "chapter", "website": "https://example.org"}, HTTP_REFERER=url)

    assert response.status_code == 302 and response["Location"] == url
    assert VIEW_ONLY_MESSAGE in _messages(response)
    alpha.refresh_from_db()
    assert alpha.website == website


def test_a_script_gets_a_json_refusal(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    response = client.post(
        reverse("chapters:detail", kwargs={"slug": alpha.slug}), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )

    assert response.status_code == 403
    assert response.json() == {"error": VIEW_ONLY_MESSAGE}


def test_the_middleware_only_acts_on_a_css_changing_something():
    middleware = ViewOnlyCSSMiddleware(lambda request: HttpResponse("ok"))
    factory = RequestFactory()

    officer_post = factory.post("/chapters/")
    officer_post.resolver_match = resolve(reverse("chapters:list"))
    assert middleware.process_view(officer_post, None, (), {}) is None

    css_get = factory.get("/chapters/")
    css_get.css_view_only = True
    assert middleware.process_view(css_get, None, (), {}) is None

    css_personal = factory.post(reverse("support:switch"))
    css_personal.css_view_only = True
    css_personal.resolver_match = resolve(reverse("support:switch"))
    assert middleware.process_view(css_personal, None, (), {}) is None


def test_dashboard_callbacks_count_as_reading():
    match = resolve("/django_plotly_dash/app/RegionDashboard/_dash-update-component")
    assert is_personal_action(match)


def _form_tags(content):
    return re.findall(r"<form\b[^>]*>", content, re.IGNORECASE)


def test_forms_a_css_cannot_submit_are_marked_and_their_own_are_not(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    content = client.get(reverse("chapters:detail", kwargs={"slug": alpha.slug})).content.decode()

    tags = _form_tags(content)
    officer_forms = [tag for tag in tags if 'class="chapter"' in tag or 'class="faculty"' in tag]
    own_forms = [
        tag for tag in tags if reverse("support:switch") in tag or reverse("events:feed_subscribe_chapter") in tag
    ]
    assert len(officer_forms) == 2 and all(LOCKED_FORM_ATTRIBUTE in tag for tag in officer_forms)
    assert len(own_forms) == 2 and not any(LOCKED_FORM_ATTRIBUTE in tag for tag in own_forms)
    assert f"form[{LOCKED_FORM_ATTRIBUTE}]" in content  # the script that disables their buttons


def test_the_regents_page_is_not_marked(auto_login_user):
    client, regent = auto_login_user(user=make_regent())

    content = client.get(reverse("chapters:detail", kwargs={"slug": regent.chapter.slug})).content.decode()

    assert LOCKED_FORM_ATTRIBUTE not in content


@pytest.mark.parametrize(
    "tag, locked",
    [
        ('<form method="post">', True),
        ('<form method="POST" action="?step=2">', True),
        ("<form action='/chapters/' method=post>", True),
        ('<form method="get" action="/chapters/">', False),
        ('<form method="post" action="/support/switch/">', False),
        ('<form method="post" action="https://www.paypal.com/cgi-bin/webscr">', False),
        ('<form method="post" action="/no/such/page/">', False),
        ('<form data-action="/chapters/" method="post" action="/support/switch/">', False),
    ],
)
def test_which_forms_are_marked(tag, locked):
    request = RequestFactory().get(reverse("chapters:list"))
    response = HttpResponse(f"<p>{tag}</p>", content_type="text/html; charset=utf-8")

    mark_locked_forms(request, response)

    assert (LOCKED_FORM_ATTRIBUTE in response.content.decode()) is locked


def test_email_all_sends_nothing_for_a_css(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    UserFactory(chapter=alpha, status="active")
    UserFactory(chapter=alpha, status="active")
    client, _ = auto_login_user(user=css)
    mail.outbox = []

    response = client.get(reverse("users:list"), {"email": "Email ALL"})

    assert response.status_code == 200
    assert mail.outbox == []
    assert VIEW_ONLY_MESSAGE in _messages(response)
    assert "Email RMP &amp; Info Update to ALL" not in response.content.decode()


def test_the_member_picker_returns_the_viewed_chapters_members(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    member = UserFactory(chapter=alpha, status="active", name="Pat Picker")
    client, _ = auto_login_user(user=css)

    response = client.get(reverse("users:autocomplete"), {"q": "Pat Picker"})

    assert [result["id"] for result in response.json()["results"]] == [str(member.pk)]


def _url_names():
    names = set()

    def walk(patterns, namespace=None):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                nested = ":".join(filter(None, [namespace, pattern.namespace])) if pattern.namespace else namespace
                walk(pattern.url_patterns, nested)
            elif isinstance(pattern, URLPattern) and pattern.name:
                names.add(f"{namespace}:{pattern.name}" if namespace else pattern.name)

    walk(get_resolver().url_patterns)
    return names


def test_every_personal_action_is_a_real_url_name():
    assert PERSONAL_ACTIONS - _url_names() == set()


# Views that change data during a plain page load. ViewOnlyCSSMiddleware only sees
# submissions, so each of these must check ``request.css_view_only`` itself, or only touch
# the signed-in user's own account. Add to this list only after making that true.
KNOWN_GET_WRITERS = {
    "users/views.py::UserListView.get",  # "Email ALL": blocked for a CSS in the view
    "contact_sync/views.py::oauth_callback",  # saves the user's own contact-sync token
}
WRITE_CALLS = {
    "send",
    "save",
    "delete",
    "bulk_create",
    "bulk_update",
    "mark_complete",
    "get_or_create",
    "update_or_create",
    "set_current_status",
}
GET_METHODS = {"get", "head", "get_context_data", "get_queryset", "get_object", "dispatch"}


def _write_calls(node):
    return {
        call.func.attr
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in WRITE_CALLS
    }


def test_no_new_view_writes_on_a_plain_page_load():
    root = pathlib.Path(settings.APPS_DIR)
    found = set()
    for path in root.rglob("views.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        relative = path.relative_to(root).as_posix()
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name in GET_METHODS and _write_calls(method):
                        found.add(f"{relative}::{node.name}.{method.name}")
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and _write_calls(node):
                segment = ast.get_source_segment(source, node) or ""
                decorators = " ".join(ast.unparse(decorator) for decorator in node.decorator_list)
                if "POST" not in segment and "require_POST" not in decorators:
                    found.add(f"{relative}::{node.name}")

    assert found == KNOWN_GET_WRITERS
