import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.services import chapter_support_specialists
from thetatauCMT.users.models import User, UserStatusChange
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, make_css, make_regent

pytestmark = pytest.mark.django_db


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    return User.objects.get(pk=user.pk)


@pytest.fixture
def setting():
    alpha, beta = ChapterFactory(name="alpha"), ChapterFactory(name="beta")
    alpha.support_specialist = "<p>Old support text</p>"
    alpha.save(update_fields=["support_specialist"])
    css = make_css(name="Casey Support", email="casey.support@example.com")
    ChapterSupportAssignmentFactory(user=css, chapter=alpha)
    ChapterSupportAssignmentFactory(user=css, chapter=beta)
    ended = ChapterFactory(name="delta")
    ChapterSupportAssignmentFactory(user=css, chapter=ended, start=_days(-40), end=_days(-1))
    return alpha, beta, ended, _fresh(css)


def _viewers(alpha, css):
    return {
        "member of the chapter": UserFactory(status="active", chapter=alpha),
        "member of another chapter": UserFactory(status="active", chapter=ChapterFactory(name="epsilon")),
        "the CSS": css,
    }


# --- the chapter page (Q11, Q18) ----------------------------------------------------------------


def test_the_chapter_page_lists_its_css_for_every_member(auto_login_user, setting):
    alpha, _, _, css = setting
    url = reverse("chapters:detail", kwargs={"slug": alpha.slug})

    for who, viewer in _viewers(alpha, css).items():
        client, _ = auto_login_user(user=_fresh(viewer))
        content = client.get(url, follow=True).content.decode()
        block = content.split('id="chapter-support-specialists"')[1].split("</p>")[0]
        assert "Casey Support" in block and "casey.support@example.com" in block, who
        assert reverse("users:profile", kwargs={"username": css.username}) in block, who
        assert "Old support text" not in content, who


def test_the_old_text_shows_only_while_no_css_is_assigned(auto_login_user, setting):
    alpha, _, ended, _ = setting
    ended.support_specialist = "<p>Old delta text</p>"
    ended.save(update_fields=["support_specialist"])
    client, _ = auto_login_user(user=UserFactory(status="active", chapter=ended))

    content = client.get(reverse("chapters:detail", kwargs={"slug": ended.slug}), follow=True).content.decode()

    assert "Old delta text" in content
    assert 'id="chapter-support-specialists"' not in content


def test_only_current_specialists_with_the_role_count(setting):
    alpha, beta, ended, css = setting
    assert list(chapter_support_specialists(alpha)) == [css]
    assert list(chapter_support_specialists(ended)) == []

    css.roles.update(end=_days(-1))
    assert list(chapter_support_specialists(alpha)) == []


# --- the profile (Q18) --------------------------------------------------------------------------


def test_the_profile_says_which_chapters_they_support(auto_login_user, setting):
    alpha, beta, ended, css = setting
    url = reverse("users:profile", kwargs={"username": css.username})

    for who, viewer in _viewers(alpha, css).items():
        client, _ = auto_login_user(user=_fresh(viewer))
        content = client.get(url).content.decode()
        line = content.split('id="css-chapters"')[1].split("</div>")[0]
        assert "Chapter Support Specialist for:" in line, who
        assert alpha.name in line and beta.name in line and ended.name not in line, who
        assert "Badge #" not in content, who


def test_members_profiles_do_not_get_the_line(auto_login_user):
    member = UserFactory(status="active")
    client, _ = auto_login_user(user=member)

    content = client.get(reverse("users:profile", kwargs={"username": member.username})).content.decode()

    assert 'id="css-chapters"' not in content


# --- kept out of the chapter's own lists ----------------------------------------------------------


def test_a_css_never_shows_in_an_assigned_chapters_roster_or_lists(auto_login_user, setting):
    alpha, _, _, css = setting
    regent = make_regent(chapter=alpha)
    UserFactory(status="advisor", chapter=alpha)
    every_status = [status.value[0] for status in UserStatusChange.STATUS]
    client, _ = auto_login_user(user=regent)

    roster = client.get(reverse("users:list"), {"current_status": every_status}).content.decode()

    assert regent.name in roster and "Casey Support" not in roster
    assert css not in alpha.members.all()
    assert css not in alpha.get_current_officers()
    assert css not in alpha.advisors
    assert css not in alpha.actives() and css not in alpha.current_members()
