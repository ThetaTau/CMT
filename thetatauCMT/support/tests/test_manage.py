import datetime
import re

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import CSS_ROLE
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.models import ChapterSupportAssignment
from thetatauCMT.support.notifications import EmailSupportWelcome
from thetatauCMT.support.services import NOT_CSS, css_state, holds_css_role
from thetatauCMT.users.models import User
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, central_office, give_css_role, make_css

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("director_is_manager")]

DIRECTOR = "director@example.com"


@pytest.fixture
def director_is_manager():
    # CSS_MANAGERS is unset, so the Executive Director manages CSSs (Q6).
    with override_settings(EXECUTIVE_DIRECTOR=DIRECTOR):
        yield


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    return User.objects.get(pk=user.pk)


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _manager(auto_login_user):
    client, manager = auto_login_user(user=UserFactory(status="alumni", email=DIRECTOR))
    return client, manager


def _natoff(auto_login_user):
    natoff = UserFactory(status="alumni")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(natoff)
    return auto_login_user(user=natoff)


# --- who can see and do what (Q6) -----------------------------------------------------------


def test_the_directory_lists_current_css_and_their_chapters(auto_login_user):
    alpha, beta = ChapterFactory(name="alpha"), ChapterFactory(name="beta")
    css = make_css(name="Casey Support")
    ChapterSupportAssignmentFactory(user=css, chapter=alpha)
    ChapterSupportAssignmentFactory(user=css, chapter=beta, start=_days(5))
    former = make_css(name="Former Support", email="former@example.com")
    former.roles.update(start=_days(-60), end=_days(-1))
    client, _ = _manager(auto_login_user)

    content = client.get(reverse("support:list")).content.decode()

    assert "Casey Support" in content and "Former Support" not in content
    assert alpha.name in content and "1 upcoming" in content
    assert reverse("support:create") in content


def test_national_officers_read_the_directory_without_the_buttons(auto_login_user):
    css = make_css(name="Casey Support")
    ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="alpha"), notes="Private note")
    client, _ = _natoff(auto_login_user)

    directory = client.get(reverse("support:list")).content.decode()
    detail = client.get(reverse("support:detail", kwargs={"pk": css.pk})).content.decode()

    assert "Casey Support" in directory and reverse("support:create") not in directory
    assert reverse("support:assign", kwargs={"pk": css.pk}) not in detail
    assert reverse("support:remove", kwargs={"pk": css.pk}) not in detail
    assert "Private note" not in detail

    response = client.post(reverse("support:create"), {"first_name": "A", "last_name": "B", "email": "a@b.org"})
    assert response["Location"] == reverse("support:list")
    assert not User.objects.filter(email="a@b.org").exists()


@pytest.mark.parametrize("who", ["member", "css"])
def test_everyone_else_is_sent_home(auto_login_user, who):
    if who == "member":
        user = UserFactory(status="active")
    else:
        user = make_css()
        ChapterSupportAssignmentFactory(user=user, chapter=ChapterFactory(name="alpha"))
    client, _ = auto_login_user(user=_fresh(user))

    for url in (reverse("support:list"), reverse("support:create"), reverse("support:detail", kwargs={"pk": 1})):
        response = client.get(url)
        assert response.status_code == 302 and response["Location"] == reverse("home"), url


# --- creating CSSs (Q7, Q9, Q23) ---------------------------------------------------------------


def test_a_manager_creates_a_staff_account_and_it_can_set_its_password(auto_login_user):
    home = central_office()
    client, _ = _manager(auto_login_user)
    mail.outbox = []

    response = client.post(
        reverse("support:create"), {"first_name": "Pat", "last_name": "Helper", "email": "pat.helper@thetatau.org"}
    )

    person = User.objects.get(email="pat.helper@thetatau.org")
    assert response["Location"] == reverse("support:detail", kwargs={"pk": person.pk})
    assert person.current_status == "css" and person.chapter == home and person.name == "Pat Helper"
    assert holds_css_role(person) and CSS_ROLE in person.current_roles
    assert EmailAddress.objects.filter(user=person, email=person.email, verified=True, primary=True).exists()
    assert any("emailed pat.helper@thetatau.org a link" in message for message in _messages(response))

    (welcome,) = mail.outbox
    assert welcome.to == ["pat.helper@thetatau.org"]
    assert "Chapter Support Specialist account" in welcome.body
    link = re.search(r"http://testserver(/reset/\S+/)", welcome.body).group(1)
    set_password = Client().get(link, follow=True)
    assert "new_password1" in set_password.content.decode()


def test_an_existing_member_keeps_their_membership(auto_login_user):
    chapter = ChapterFactory(name="alpha")
    member = UserFactory(status="alumni", chapter=chapter, email="alum@example.com")
    client, _ = _manager(auto_login_user)
    mail.outbox = []

    response = client.post(
        reverse("support:create"), {"first_name": "X", "last_name": "Y", "email": "ALUM@example.com"}
    )

    member = _fresh(member)
    assert response["Location"] == reverse("support:detail", kwargs={"pk": member.pk})
    assert member.current_status == "alumni" and member.chapter == chapter
    assert holds_css_role(member)
    assert mail.outbox == []
    assert User.objects.filter(email__iexact="alum@example.com").count() == 1


def test_an_existing_secondary_email_finds_the_member(auto_login_user):
    member = UserFactory(status="alumni", email="main@example.com")
    EmailAddress.objects.create(user=member, email="other@example.com", verified=True)
    client, _ = _manager(auto_login_user)

    client.post(reverse("support:create"), {"first_name": "X", "last_name": "Y", "email": "other@example.com"})

    assert holds_css_role(member)
    assert not User.objects.filter(email="other@example.com").exists()


def test_refusals_show_on_the_form(auto_login_user):
    already = make_css(email="already@example.com")
    UserFactory(status="alumni", email="off@example.com", is_active=False)
    client, _ = _manager(auto_login_user)

    for email, text in (
        ("already@example.com", "is already a Chapter Support Specialist"),
        ("off@example.com", "account is switched off"),
    ):
        response = client.post(reverse("support:create"), {"first_name": "X", "last_name": "Y", "email": email})
        assert response.status_code == 200 and text in response.content.decode(), email
    assert already.roles.filter(role=CSS_ROLE).count() == 1


def test_a_missing_home_chapter_is_explained(auto_login_user):
    client, _ = _manager(auto_login_user)

    response = client.post(reverse("support:create"), {"first_name": "X", "last_name": "Y", "email": "new@example.com"})

    assert response.status_code == 200 and "central-office" in response.content.decode()
    assert not User.objects.filter(email="new@example.com").exists()


# --- assignments (Q10, Q17) ----------------------------------------------------------------------


def test_a_manager_assigns_and_ends_chapters_and_nobody_is_emailed(auto_login_user):
    alpha = ChapterFactory(name="alpha")
    css = make_css()
    client, manager = _manager(auto_login_user)
    mail.outbox = []

    response = client.post(
        reverse("support:assign", kwargs={"pk": css.pk}),
        {"chapter": alpha.pk, "start": _days(-10).isoformat(), "notes": "Covering for spring"},
    )
    assignment = ChapterSupportAssignment.objects.get(user=css, chapter=alpha)
    assert assignment.created_by == manager and assignment.notes == "Covering for spring"
    assert any("supports" in message for message in _messages(response))
    assert alpha.pk in css_state(_fresh(css)).chapter_ids

    response = client.post(reverse("support:end", kwargs={"pk": assignment.pk}), {"end": _days(-1).isoformat()})
    assignment.refresh_from_db()
    assert assignment.end == _days(-1) and assignment.ended_by == manager
    assert any("stops supporting" in message for message in _messages(response))
    assert css_state(_fresh(css)).chapter_ids == frozenset()
    assert mail.outbox == []

    detail = client.get(reverse("support:detail", kwargs={"pk": css.pk})).content.decode()
    assert 'id="css-past"' in detail and "Covering for spring" not in detail.split('id="css-past"')[1]


def test_assignment_rules_are_explained(auto_login_user):
    own = ChapterFactory(name="alpha")
    member_css = UserFactory(status="alumni", chapter=own)
    give_css_role(member_css)
    closed = ChapterFactory(name="beta", active=False)
    client, _ = _manager(auto_login_user)
    url = reverse("support:assign", kwargs={"pk": member_css.pk})

    for chapter in (own, closed):
        response = client.post(url, {"chapter": chapter.pk, "start": _days(0).isoformat()})
        assert any("Select a valid choice" in message for message in _messages(response)), chapter
    assert not ChapterSupportAssignment.objects.exists()

    not_css = UserFactory(status="active")
    response = client.post(
        reverse("support:assign", kwargs={"pk": not_css.pk}),
        {"chapter": ChapterFactory(name="delta").pk, "start": _days(0).isoformat()},
    )
    assert any("does not hold the Chapter Support Specialist role" in message for message in _messages(response))


def test_upcoming_assignments_are_cancelled_and_past_ones_cannot_be_ended_again(auto_login_user):
    css = make_css()
    upcoming = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="alpha"), start=_days(3))
    past = ChapterSupportAssignmentFactory(
        user=css, chapter=ChapterFactory(name="beta"), start=_days(-30), end=_days(-2)
    )
    client, _ = _manager(auto_login_user)

    client.post(reverse("support:end", kwargs={"pk": upcoming.pk}))
    response = client.post(reverse("support:end", kwargs={"pk": past.pk}), {"end": _days(5).isoformat()})

    assert not ChapterSupportAssignment.objects.filter(pk=upcoming.pk).exists()
    past.refresh_from_db()
    assert past.end == _days(-2)
    assert any("has already ended" in message for message in _messages(response))


def test_an_end_date_before_the_start_is_refused(auto_login_user):
    css = make_css()
    assignment = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="alpha"), start=_days(-3))
    client, _ = _manager(auto_login_user)

    response = client.post(reverse("support:end", kwargs={"pk": assignment.pk}), {"end": _days(-5).isoformat()})

    assignment.refresh_from_db()
    assert assignment.end is None
    assert any("cannot be before the start date" in message for message in _messages(response))


# --- removing a CSS (S21) -----------------------------------------------------------------------


def test_removing_a_staff_css_ends_everything_and_switches_the_account_off(auto_login_user):
    css = make_css()
    css.roles.update(start=_days(-60))
    running = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="alpha"), start=_days(-20))
    upcoming = ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="beta"), start=_days(4))
    client, _ = _manager(auto_login_user)
    mail.outbox = []

    response = client.post(reverse("support:remove", kwargs={"pk": css.pk}))

    css = _fresh(css)
    assert response["Location"] == reverse("support:list")
    assert not css.is_active and not holds_css_role(css) and CSS_ROLE not in (css.current_roles or [])
    assert css_state(css) is NOT_CSS
    running.refresh_from_db()
    assert running.end == _days(-1)
    assert not ChapterSupportAssignment.objects.filter(pk=upcoming.pk).exists()
    assert mail.outbox == []


def test_a_css_made_and_removed_the_same_day_leaves_no_role_behind(auto_login_user):
    central_office()
    client, _ = _manager(auto_login_user)
    client.post(reverse("support:create"), {"first_name": "Pat", "last_name": "Brief", "email": "brief@example.com"})
    person = User.objects.get(email="brief@example.com")

    client.post(reverse("support:remove", kwargs={"pk": person.pk}))

    person = _fresh(person)
    assert not person.roles.filter(role=CSS_ROLE).exists()
    assert CSS_ROLE not in (person.current_roles or []) and not person.is_active

    mail.outbox = []
    client.post(reverse("support:create"), {"first_name": "Pat", "last_name": "Brief", "email": "brief@example.com"})
    person = _fresh(person)
    assert person.is_active and holds_css_role(person)
    assert len(mail.outbox) == 1


def test_removing_a_member_css_keeps_their_account(auto_login_user):
    member = UserFactory(status="alumni", chapter=ChapterFactory(name="alpha"))
    give_css_role(member, start=_days(-30))
    client, _ = _manager(auto_login_user)

    client.post(reverse("support:remove", kwargs={"pk": member.pk}))

    member = _fresh(member)
    assert member.is_active and member.current_status == "alumni"
    assert not holds_css_role(member)


def test_the_welcome_email_demo_args():
    make_css()

    (user,) = EmailSupportWelcome.get_demo_args()

    assert isinstance(user, User)
    assert EmailSupportWelcome(user).context["set_password_url"].startswith("http://testserver/reset/")


# --- the new account must be findable at sign-in -----------------------------------------------
# allauth looks emails up lowercased and exact, for password resets and sign-in alike, so an
# account stored as "Angela.Seegel@..." was reported as unknown.

UNKNOWN_ACCOUNT = "no account was found"
NEW_PASSWORD = "Css-Reset-Pass-2026!"


def _reset_links(entered):
    mail.outbox = []
    Client().post(reverse("account_reset_password"), {"email": entered})
    (message,) = mail.outbox
    assert UNKNOWN_ACCOUNT not in message.body, entered
    return re.findall(r"http://testserver(/accounts/password/reset/key/\S+/)", message.body)


@pytest.mark.parametrize("typed", ["Angela.Seegel@ThetaTau.engineering", "angela.seegel@thetatau.engineering"])
def test_a_new_css_can_reset_their_password_whatever_the_case(auto_login_user, typed):
    central_office()
    client, _ = _manager(auto_login_user)

    client.post(reverse("support:create"), {"first_name": "Angela", "last_name": "Seegel", "email": typed})

    person = User.objects.get(email__iexact=typed)
    assert person.email == person.username == typed.lower()
    assert list(EmailAddress.objects.filter(user=person).values_list("email", "verified", "primary")) == [
        (typed.lower(), True, True)
    ]
    for entered in (typed, typed.lower(), typed.upper()):
        assert len(_reset_links(entered)) == 1, entered


@override_settings(DEBUG=True)  # the sign-in form only skips its captcha in DEBUG
def test_a_new_css_sets_a_password_from_the_reset_email_and_signs_in(auto_login_user):
    central_office()
    client, _ = _manager(auto_login_user)
    client.post(
        reverse("support:create"), {"first_name": "Angela", "last_name": "Seegel", "email": "Angela.Seegel@Example.org"}
    )
    (link,) = _reset_links("Angela.Seegel@Example.org")
    visitor = Client()

    form_page = visitor.get(link, follow=True)
    done = visitor.post(form_page.redirect_chain[-1][0], {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD})
    signed_in = visitor.post(reverse("login"), {"login": "ANGELA.Seegel@example.org", "password": NEW_PASSWORD})

    assert done.status_code == 302
    assert signed_in.status_code == 302
    assert visitor.session["_auth_user_id"] == str(User.objects.get(email="angela.seegel@example.org").pk)
