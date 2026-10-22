"""CSSWI-10: a CSS syncs their chapters' officers; region syncs list the region's CSSs."""

import datetime
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.contact_sync.officers import (
    SUPPORT_ROLE,
    SUPPORT_SCOPE,
    collect_contacts_for_scope,
    collect_region_officer_contacts,
)
from thetatauCMT.contact_sync.providers.base import SyncResult
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import User, UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, make_css, make_regent

pytestmark = pytest.mark.django_db

GOOGLE = {"CONTACT_SYNC_GOOGLE_CLIENT_ID": "id", "CONTACT_SYNC_GOOGLE_CLIENT_SECRET": "s"}
PUSH = "thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts"


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    return User.objects.get(pk=user.pk)


def _officer(chapter, role):
    user = UserFactory(chapter=chapter, status="active")
    UserRoleChange.objects.create(user=user, role=role, start=_days(-30), end=_days(300))
    return _fresh(user)


@pytest.fixture
def setting():
    region = RegionFactory()
    alpha = ChapterFactory(name="alpha", region=region)
    beta = ChapterFactory(name="beta", region=region)
    delta = ChapterFactory(name="delta", region=region)
    officers = {
        "alpha regent": make_regent(chapter=alpha),
        "alpha treasurer": _officer(alpha, "treasurer"),
        "beta scribe": _officer(beta, "scribe"),
        "delta regent": make_regent(chapter=delta),
    }
    css = make_css(email="css@example.com")
    ChapterSupportAssignmentFactory(user=css, chapter=alpha)
    beta_assignment = ChapterSupportAssignmentFactory(user=css, chapter=beta)
    other_css = make_css(email="other.css@example.com")
    ChapterSupportAssignmentFactory(user=other_css, chapter=alpha)
    return SimpleSetting(region, alpha, beta, delta, officers, _fresh(css), _fresh(other_css), beta_assignment)


class SimpleSetting:
    def __init__(self, region, alpha, beta, delta, officers, css, other_css, beta_assignment):
        self.region, self.alpha, self.beta, self.delta = region, alpha, beta, delta
        self.officers, self.css, self.other_css, self.beta_assignment = officers, css, other_css, beta_assignment


def _people(contacts):
    return sorted(contact.user_pk for contact in contacts)


def _token(user, scopes=()):
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.expires_at = timezone.now() + datetime.timedelta(hours=1)
    token.auto_sync_scopes = list(scopes)
    token.save()
    return token


# --- a CSS's own chapters -----------------------------------------------------------------------


def test_a_css_gets_their_chapters_officers_and_no_other_css(setting):
    contacts, display = collect_contacts_for_scope(SUPPORT_SCOPE, user=setting.css)

    expected = [setting.officers[key].pk for key in ("alpha regent", "alpha treasurer", "beta scribe")]
    assert _people(contacts) == sorted(expected)
    assert display == "My chapters"
    assert collect_contacts_for_scope(SUPPORT_SCOPE, user=None) == ([], "My chapters")


def test_a_css_downloads_the_vcard(auto_login_user, setting):
    client, _ = auto_login_user(user=setting.css)

    response = client.get(reverse("contact_sync:support_vcard"))

    assert response.status_code == 200
    assert response["X-CMT-Officer-Count"] == "3"
    body = response.content.decode()
    assert setting.officers["alpha regent"].last_name in body
    assert setting.officers["delta regent"].email not in body


@override_settings(**GOOGLE)
def test_a_css_syncs_to_google_and_turns_on_the_weekly_sync(auto_login_user, setting):
    client, _ = auto_login_user(user=setting.css)
    token = _token(setting.css)

    with mock.patch(PUSH, return_value=SyncResult(created=3, updated=0, failed=0, total=3)) as push:
        response = client.post(reverse("contact_sync:google_sync"), {"scope": SUPPORT_SCOPE})
    assert response.status_code == 200, response.content
    assert len(push.call_args[0][1]) == 3

    response = client.post(reverse("contact_sync:google_auto_sync"), {"scope": SUPPORT_SCOPE, "enabled": "1"})
    assert response.status_code == 200
    token.refresh_from_db()
    assert token.auto_sync_scopes == [SUPPORT_SCOPE]


@override_settings(**GOOGLE)
def test_a_css_cannot_ask_for_a_region_or_national_scope(auto_login_user, setting):
    client, _ = auto_login_user(user=setting.css)
    _token(setting.css)

    with mock.patch(PUSH) as push:
        for scope in (f"region:{setting.region.slug}", "national", setting.region.slug):
            response = client.post(reverse("contact_sync:google_sync"), {"scope": scope})
            assert response.status_code == 403, scope
            response = client.post(reverse("contact_sync:google_auto_sync"), {"scope": scope, "enabled": "1"})
            assert response.status_code == 403, scope
    push.assert_not_called()
    response = client.get(reverse("contact_sync:region_vcard", kwargs={"region_slug": setting.region.slug}))
    assert response.status_code == 302 and response["Location"] == reverse("home")


def test_members_cannot_use_the_css_scope(auto_login_user, setting):
    client, _ = auto_login_user(user=UserFactory(status="active"))

    assert client.get(reverse("contact_sync:support_vcard"))["Location"] == reverse("home")
    response = client.post(reverse("contact_sync:google_auto_sync"), {"scope": SUPPORT_SCOPE, "enabled": "1"})
    assert response.status_code == 403


@override_settings(**GOOGLE)
def test_ending_an_assignment_drops_that_chapter_from_the_next_weekly_sync(setting):
    _token(setting.css, scopes=[SUPPORT_SCOPE])
    setting.beta_assignment.start = _days(-30)
    setting.beta_assignment.end = _days(-1)
    setting.beta_assignment.save()

    with mock.patch(PUSH, return_value=SyncResult(created=2, updated=0, failed=0, total=2)) as push:
        call_command("weekly_contact_sync", "--override", stdout=StringIO())

    pushed = push.call_args[0][1]
    assert _people(pushed) == sorted([setting.officers["alpha regent"].pk, setting.officers["alpha treasurer"].pk])


def test_the_landing_page_offers_the_sync(auto_login_user, setting):
    client, _ = auto_login_user(user=setting.css)

    content = client.get(reverse("support:my_chapters")).content.decode()

    assert 'id="officer-contacts"' in content and 'id="contactSyncModal"' in content
    assert reverse("contact_sync:support_vcard") in content


# --- the region sync (Q26 B) --------------------------------------------------------------------


def test_a_region_sync_lists_each_css_once_labelled(setting):
    elsewhere = ChapterFactory(name="epsilon", region=RegionFactory())
    far_css = make_css(email="far.css@example.com")
    ChapterSupportAssignmentFactory(user=far_css, chapter=elsewhere)

    contacts, _ = collect_region_officer_contacts(setting.region.slug)

    support = [contact for contact in contacts if contact.role == SUPPORT_ROLE]
    assert sorted(contact.user_pk for contact in support) == sorted([setting.css.pk, setting.other_css.pk])
    (card,) = [contact for contact in support if contact.user_pk == setting.css.pk]
    assert card.chapter_name == "alpha, beta" and card.display_name.startswith("CSS ")
    assert collect_region_officer_contacts(setting.region.slug, roles=["regent"])[0]
    assert not any(c.role == SUPPORT_ROLE for c in collect_region_officer_contacts(setting.region.slug, ["regent"])[0])


def test_a_css_leaves_the_region_sync_when_their_last_assignment_there_ends(setting):
    setting.css.support_assignments.update(start=_days(-30), end=_days(-1))

    contacts, _ = collect_region_officer_contacts(setting.region.slug)

    assert [c.user_pk for c in contacts if c.role == SUPPORT_ROLE] == [setting.other_css.pk]
