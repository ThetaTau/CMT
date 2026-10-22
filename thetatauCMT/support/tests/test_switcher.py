import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import User, UserAlter
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, make_css, make_regent

pytestmark = pytest.mark.django_db

SWITCH = "support:switch"


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


def test_switching_to_an_assigned_chapter(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    client, _ = auto_login_user(user=css)

    response = client.post(reverse(SWITCH), {"chapter": beta.slug, "action": "apply", "next": "/tasks/"})

    assert response.status_code == 302 and response["Location"] == "/tasks/"
    assert UserAlter.objects.get(user=css).chapter == beta
    assert _fresh(css).current_chapter == beta
    assert f"Now viewing {beta}." in _messages(response)


def test_an_unassigned_chapter_is_refused(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    other = ChapterFactory(name="delta")
    client, _ = auto_login_user(user=css)

    response = client.post(reverse(SWITCH), {"chapter": other.slug, "action": "apply"})

    assert response.status_code == 302
    assert not UserAlter.objects.filter(user=css).exists()
    assert _fresh(css).current_chapter == alpha
    assert any("not assigned" in message or "valid choice" in message for message in _messages(response))


def test_reset_forgets_the_choice(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    UserAlter.objects.create(user=css, chapter=beta)
    client, _ = auto_login_user(user=css)

    client.post(reverse(SWITCH), {"action": "reset"})

    assert not UserAlter.objects.filter(user=css).exists()
    assert _fresh(css).current_chapter == alpha


def test_leaving_a_chapter_page_lands_on_the_new_chapters_page(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    client, _ = auto_login_user(user=css)
    old_page = reverse("chapters:detail", kwargs={"slug": alpha.slug})

    response = client.post(reverse(SWITCH), {"chapter": beta.slug, "action": "apply", "next": old_page})

    assert response["Location"] == reverse("chapters:detail", kwargs={"slug": beta.slug})


def test_an_unsafe_next_is_ignored(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    client, _ = auto_login_user(user=css)

    response = client.post(
        reverse(SWITCH), {"chapter": beta.slug, "action": "apply", "next": "https://evil.example.com/"}
    )

    assert response["Location"] == reverse("chapters:detail", kwargs={"slug": beta.slug})


def test_only_a_css_can_use_it(auto_login_user):
    member = UserFactory(status="active")
    client, _ = auto_login_user(user=member)

    response = client.post(reverse(SWITCH), {"chapter": member.chapter.slug, "action": "apply"})

    assert response["Location"] == reverse("home")
    assert not UserAlter.objects.filter(user=member).exists()


def test_a_national_officer_who_is_also_a_css_uses_the_national_switcher(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(css)
    client, _ = auto_login_user(user=css)

    response = client.post(reverse(SWITCH), {"chapter": alpha.slug, "action": "apply"})

    assert response["Location"] == reverse("home")


def test_get_is_not_allowed(auto_login_user):
    css, _ = assigned_css("alpha")
    client, _ = auto_login_user(user=css)
    assert client.get(reverse(SWITCH)).status_code == 405


# --- the bar ---------------------------------------------------------------------------


def test_the_bar_lists_only_assigned_chapters_and_says_view_only(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    ChapterFactory(name="delta")
    client, _ = auto_login_user(user=css)

    content = client.get(reverse("home"), follow=True).content.decode()

    assert 'id="css-bar"' in content
    assert f'<option value="{alpha.slug}" selected>' in content
    assert f'<option value="{beta.slug}">' in content
    assert 'value="delta"' not in content
    assert "View only" in content
    assert 'id="region-bar-toggle"' in content
    assert reverse("support:my_chapters") in content


def test_the_bar_explains_when_no_chapter_is_assigned(auto_login_user):
    css = _fresh(make_css())
    client, _ = auto_login_user(user=css)

    content = client.get(reverse("home"), follow=True).content.decode()

    assert 'id="css-bar"' in content
    assert "No chapters assigned. Contact the Central Office." in content


@pytest.mark.parametrize("make_user", [lambda: UserFactory(status="active"), make_regent], ids=["member", "regent"])
def test_members_and_officers_do_not_get_the_bar(auto_login_user, make_user):
    client, _ = auto_login_user(user=make_user())
    content = client.get(reverse("home")).content.decode()
    assert 'id="css-bar"' not in content
    assert 'id="region-bar-toggle"' not in content


def test_a_national_officer_who_is_also_a_css_does_not_get_the_bar(auto_login_user):
    css, _ = assigned_css("alpha")
    Group.objects.get_or_create(name="natoff")[0].user_set.add(css)
    client, _ = auto_login_user(user=css)

    content = client.get(reverse("home")).content.decode()

    assert 'id="css-bar"' not in content
