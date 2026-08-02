"""The What's New feed, its acknowledgements and the modal's manners (TWI-6).

The point of this work item is to make announcements *stop* -- so most of these
tests are about what does **not** appear: items the viewer cannot reach, items
already dismissed, and the modal on any page that is already interrupting the
user. The backwards-compatibility test at the bottom is the guard that says an
untouched announcement row still behaves the way it did before any of this.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import constants as message_constants
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.announcements.models import Announcement
from thetatauCMT.announcements.tests.factories import AnnouncementFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.guides import services
from thetatauCMT.guides.context_processors import whats_new as whats_new_context
from thetatauCMT.guides.models import Audience, UserAcknowledgement
from thetatauCMT.guides.tests.factories import FeatureAreaFactory, FeatureFactory
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

pytestmark = pytest.mark.django_db


def _in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _member():
    return UserFactory(status="active")


def _officer():
    return _in_group(_member(), "officer")


def _natoff():
    return _in_group(_member(), "natoff")


def _new_feature(**kwargs):
    kwargs.setdefault("released_at", timezone.now().date())
    return FeatureFactory(**kwargs)


def _titles(items):
    return [item["title"] for item in items]


def _ack(user, target, source="badge"):
    return UserAcknowledgement.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id,
        source=source,
    )


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def test_acknowledgement_is_unique_per_user_and_target():
    user = _member()
    announcement = AnnouncementFactory()
    _ack(user, announcement)
    assert services.acknowledge(user, [{"kind": "announcement", "id": announcement.id}]) == 0
    assert UserAcknowledgement.objects.count() == 1


def test_announcement_rejects_an_unknown_audience_or_role():
    with pytest.raises(ValidationError) as unknown_audience:
        Announcement(title="t", content="c", audience="wizard").full_clean()
    assert "audience" in unknown_audience.value.message_dict
    with pytest.raises(ValidationError) as unknown_role:
        Announcement(title="t", content="c", roles=["dark lord"]).full_clean()
    assert "roles" in unknown_role.value.message_dict


# ---------------------------------------------------------------------------
# get_whats_new -- what appears
# ---------------------------------------------------------------------------
def test_a_newly_released_visible_feature_is_in_the_feed():
    user = _member()
    _new_feature(name="Roster export")
    assert _titles(services.get_whats_new(user)) == ["Roster export"]


def test_a_feature_with_no_release_date_is_never_new():
    user = _member()
    FeatureFactory(name="Quietly added", released_at=None)
    assert services.get_whats_new(user) == []


def test_a_feature_older_than_the_max_age_drops_out(settings):
    user = _member()
    settings.NEW_FEATURE_MAX_AGE_DAYS = 30
    _new_feature(name="Ancient", released_at=timezone.now().date() - timedelta(days=31))
    _new_feature(name="Fresh", released_at=timezone.now().date() - timedelta(days=29))
    assert _titles(services.get_whats_new(user)) == ["Fresh"]


def test_a_feature_the_viewer_cannot_see_is_not_announced():
    member = _member()
    _new_feature(name="Officer only", area=FeatureAreaFactory(audience=Audience.OFFICER))
    assert services.get_whats_new(member) == []
    assert _titles(services.get_whats_new(_officer())) == ["Officer only"]


def test_a_flag_disabled_feature_is_not_announced():
    user = _member()
    Config.objects.create(key="FEATURE_AWARDS", value="off", description="test")
    _new_feature(name="Awards", feature_flag="FEATURE_AWARDS")
    assert services.get_whats_new(user) == []


def test_a_natoff_announcement_is_invisible_to_a_member():
    AnnouncementFactory(title="Nationals only", audience=Audience.NATOFF)
    assert services.get_whats_new(_member()) == []
    assert _titles(services.get_whats_new(_natoff())) == ["Nationals only"]


def test_a_role_targeted_announcement_only_reaches_that_role():
    treasurer = _officer()
    UserRoleChangeFactory(user=treasurer, current=True, role="treasurer")
    AnnouncementFactory(title="Dues are due", roles=["treasurer"])
    assert _titles(services.get_whats_new(treasurer)) == ["Dues are due"]
    assert services.get_whats_new(_officer()) == []


def test_an_unpublished_announcement_is_not_in_the_feed():
    user = _member()
    now = timezone.now()
    AnnouncementFactory(title="Later", publish_start=now + timedelta(days=1))
    AnnouncementFactory(title="Over", publish_end=now - timedelta(days=1))
    assert services.get_whats_new(user) == []


def test_an_announcement_about_an_invisible_feature_is_withheld():
    """Never advertise a page the reader would be bounced off of."""
    hidden = FeatureFactory(area=FeatureAreaFactory(audience=Audience.NATOFF))
    AnnouncementFactory(title="Try the new thing", feature=hidden)
    assert services.get_whats_new(_member()) == []
    assert _titles(services.get_whats_new(_natoff())) == ["Try the new thing"]


def test_announcements_sort_above_features_and_by_priority():
    user = _member()
    AnnouncementFactory(title="Second", priority=5)
    AnnouncementFactory(title="First", priority=1)
    _new_feature(name="A feature")
    assert _titles(services.get_whats_new(user)) == ["First", "Second", "A feature"]


def test_features_sort_newest_first():
    user = _member()
    _new_feature(name="Older", released_at=timezone.now().date() - timedelta(days=5))
    _new_feature(name="Newer", released_at=timezone.now().date())
    assert _titles(services.get_whats_new(user)) == ["Newer", "Older"]


def test_an_anonymous_visitor_gets_an_empty_feed():
    AnnouncementFactory(title="Hello")
    assert services.get_whats_new(AnonymousUser()) == []


# ---------------------------------------------------------------------------
# acknowledge
# ---------------------------------------------------------------------------
def test_got_it_acknowledges_and_the_item_does_not_come_back():
    user = _member()
    announcement = AnnouncementFactory(title="Read me")
    assert services.acknowledge(user, [{"kind": "announcement", "id": announcement.id}], "badge") == 1
    assert services.get_whats_new(user) == []


def test_acknowledging_one_item_leaves_the_others_alone():
    user = _member()
    first = AnnouncementFactory(title="One")
    AnnouncementFactory(title="Two")
    services.acknowledge(user, [{"kind": "announcement", "id": first.id}], "badge")
    assert _titles(services.get_whats_new(user)) == ["Two"]


def test_acknowledged_items_still_appear_when_asked_for():
    user = _member()
    announcement = AnnouncementFactory(title="Read me")
    services.acknowledge(user, [{"kind": "announcement", "id": announcement.id}])
    items = services.get_whats_new(user, include_acknowledged=True)
    assert [(item["title"], item["is_acknowledged"]) for item in items] == [("Read me", True)]


def test_a_pinned_announcement_cannot_be_acknowledged():
    user = _member()
    pinned = AnnouncementFactory(title="Compliance", dismissible=False)
    assert services.acknowledge(user, [{"kind": "announcement", "id": pinned.id}]) == 0
    assert _titles(services.get_whats_new(user)) == ["Compliance"]


def test_acknowledge_skips_ids_the_user_cannot_see():
    member = _member()
    hidden = AnnouncementFactory(audience=Audience.NATOFF)
    invisible = _new_feature(area=FeatureAreaFactory(audience=Audience.NATOFF))
    written = services.acknowledge(
        member,
        [{"kind": "announcement", "id": hidden.id}, {"kind": "feature", "id": invisible.id}],
    )
    assert written == 0
    assert not UserAcknowledgement.objects.exists()


def test_acknowledge_ignores_malformed_entries():
    user = _member()
    announcement = AnnouncementFactory()
    written = services.acknowledge(
        user,
        [
            "nonsense",
            {"kind": "planet", "id": 1},
            {"kind": "feature", "id": "abc"},
            {"kind": "announcement", "id": announcement.id},
        ],
    )
    assert written == 1


def test_acknowledge_records_the_affordance_and_drops_unknown_ones():
    user = _member()
    first = AnnouncementFactory()
    second = AnnouncementFactory()
    services.acknowledge(user, [{"kind": "announcement", "id": first.id}], "modal")
    services.acknowledge(user, [{"kind": "announcement", "id": second.id}], "telepathy")
    sources = set(UserAcknowledgement.objects.values_list("source", flat=True))
    assert sources == {"modal", ""}


def test_acknowledge_is_a_no_op_for_anonymous_users():
    announcement = AnnouncementFactory()
    assert services.acknowledge(AnonymousUser(), [{"kind": "announcement", "id": announcement.id}]) == 0


def test_acknowledgements_do_not_leak_between_users():
    reader, other = _member(), _member()
    announcement = AnnouncementFactory(title="Read me")
    services.acknowledge(reader, [{"kind": "announcement", "id": announcement.id}])
    assert services.get_whats_new(reader) == []
    assert _titles(services.get_whats_new(other)) == ["Read me"]


def test_the_feed_costs_the_same_whatever_its_length():
    """Two subtraction queries, one per kind -- never one per item through the GFK."""
    user = _member()
    AnnouncementFactory()
    _new_feature()
    services.get_whats_new(user)  # warm the ContentType cache
    with CaptureQueriesContext(connection) as small:
        services.get_whats_new(user)
    for _ in range(5):
        AnnouncementFactory()
        _new_feature()
    with CaptureQueriesContext(connection) as large:
        services.get_whats_new(user)
    assert len(large) == len(small)


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------
def test_ack_endpoint_accepts_a_json_batch(auto_login_user):
    client, user = auto_login_user()
    announcement = AnnouncementFactory()
    feature = _new_feature()
    response = client.post(
        reverse("guides:acknowledge"),
        data={
            "items": [
                {"kind": "announcement", "id": announcement.id},
                {"kind": "feature", "id": feature.id},
            ],
            "source": "modal",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "acknowledged": 2}
    assert UserAcknowledgement.objects.filter(user=user).count() == 2


def test_ack_endpoint_accepts_a_plain_form_post_and_redirects(auto_login_user):
    """The "Got it" button has to work with JavaScript off."""
    client, user = auto_login_user()
    announcement = AnnouncementFactory()
    response = client.post(
        reverse("guides:acknowledge"),
        {"kind": "announcement", "id": announcement.id, "source": "badge", "next": "/"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert UserAcknowledgement.objects.filter(user=user).count() == 1


def test_ack_endpoint_refuses_an_off_site_redirect(auto_login_user):
    client, _ = auto_login_user()
    announcement = AnnouncementFactory()
    response = client.post(
        reverse("guides:acknowledge"),
        {"kind": "announcement", "id": announcement.id, "next": "https://evil.example.com/"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


def test_ack_endpoint_rejects_a_malformed_json_body(auto_login_user):
    client, _ = auto_login_user()
    response = client.post(reverse("guides:acknowledge"), data="not json", content_type="application/json")
    assert response.status_code == 400


def test_ack_endpoint_silently_skips_invisible_ids(auto_login_user):
    """A tab left open across a deploy must not start throwing errors."""
    client, user = auto_login_user()
    response = client.post(
        reverse("guides:acknowledge"),
        data={"items": [{"kind": "feature", "id": 99999}], "source": "badge"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["acknowledged"] == 0


def test_ack_endpoint_requires_a_login():
    response = Client().post(reverse("guides:acknowledge"))
    assert response.status_code == 302
    assert "login" in response["Location"]


def test_ack_endpoint_requires_csrf(auto_login_user):
    _, user = auto_login_user()
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(user)
    response = strict.post(reverse("guides:acknowledge"), {"kind": "announcement", "id": 1})
    assert response.status_code == 403


def test_whats_new_seen_endpoint_marks_the_session(auto_login_user):
    client, _ = auto_login_user()
    assert client.post(reverse("guides:whats-new-seen")).status_code == 200
    assert client.session[services.WHATS_NEW_SESSION_KEY] is True


# ---------------------------------------------------------------------------
# The archive
# ---------------------------------------------------------------------------
def test_the_archive_lists_acknowledged_items_too(auto_login_user):
    client, user = auto_login_user()
    seen = AnnouncementFactory(title="Already read", priority=1)
    AnnouncementFactory(title="Still new", priority=2)
    services.acknowledge(user, [{"kind": "announcement", "id": seen.id}])
    response = client.get(reverse("guides:whats-new"))
    assert response.status_code == 200
    assert _titles(response.context["items"]) == ["Already read", "Still new"]


def test_the_archive_requires_a_login():
    response = Client().get(reverse("guides:whats-new"))
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Modal suppression -- the anti-annoyance rules
# ---------------------------------------------------------------------------
class _Request:
    """Just enough request for the suppression rules."""

    def __init__(self, user, path="/", method="GET", session=None):
        self.user = user
        self.path = path
        self.method = method
        self.session = {} if session is None else session


def test_the_modal_is_offered_on_an_ordinary_page():
    request = _Request(_member())
    AnnouncementFactory(title="Hello")
    assert services.whats_new_modal_allowed(request) is True
    assert _titles(whats_new_context(request)["whats_new_modal"]["items"]) == ["Hello"]


def test_the_modal_is_suppressed_on_a_post():
    assert services.whats_new_modal_allowed(_Request(_member(), method="POST")) is False


def test_the_modal_is_suppressed_for_anonymous_visitors():
    assert services.whats_new_modal_allowed(_Request(AnonymousUser())) is False


@pytest.mark.parametrize("path", ["/rmp/", "/forms/rmp/", "/terms/required/"])
def test_the_modal_is_suppressed_on_compliance_pages(path):
    assert services.whats_new_modal_allowed(_Request(_member(), path=path)) is False


@pytest.mark.parametrize("path", ["/workflow/forms/", "/accounts/login/", "/admin/"])
def test_the_modal_is_suppressed_on_excluded_prefixes(path):
    assert services.whats_new_modal_allowed(_Request(_member(), path=path)) is False


def test_the_modal_is_suppressed_when_an_error_is_already_on_screen():
    """RMPSignMiddleware pushes an ERROR and redirects; do not stack on top of it."""

    class _Message:
        level = message_constants.ERROR

    request = _Request(_member())
    request._messages = type("Storage", (), {"_queued_messages": [_Message()], "_loaded_messages": []})()
    assert services.whats_new_modal_allowed(request) is False


def test_the_modal_is_offered_alongside_a_merely_informational_message():
    class _Message:
        level = message_constants.INFO

    request = _Request(_member())
    request._messages = type("Storage", (), {"_queued_messages": [_Message()], "_loaded_messages": []})()
    assert services.whats_new_modal_allowed(request) is True


def test_the_modal_shows_at_most_once_per_session():
    request = _Request(_member())
    AnnouncementFactory(title="Hello")
    assert whats_new_context(request) != {}
    request.session[services.WHATS_NEW_SESSION_KEY] = True
    assert whats_new_context(request) == {}


def test_an_empty_feed_marks_the_session_so_later_pages_cost_nothing():
    request = _Request(_member())
    assert whats_new_context(request) == {}
    assert request.session[services.WHATS_NEW_SESSION_KEY] is True


def test_the_modal_caps_the_list_and_points_at_the_archive(settings):
    settings.WHATS_NEW_MAX_ITEMS = 2
    request = _Request(_member())
    for index in range(4):
        AnnouncementFactory(title=f"Item {index}", priority=index + 1)
    modal = whats_new_context(request)["whats_new_modal"]
    assert len(modal["items"]) == 2
    assert modal["total"] == 4
    assert modal["has_more"] is True


def test_the_rendered_page_carries_the_modal_and_marks_it_seen(auto_login_user):
    client, _ = auto_login_user()
    AnnouncementFactory(title="Look at this")
    response = client.get(reverse("home"))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="tt-whats-new-modal"' in body
    assert reverse("guides:whats-new-seen") in body


def test_the_modal_is_absent_once_the_session_is_marked(auto_login_user):
    client, _ = auto_login_user()
    AnnouncementFactory(title="Look at this")
    client.post(reverse("guides:whats-new-seen"))
    response = client.get(reverse("home"))
    assert 'id="tt-whats-new-modal"' not in response.content.decode()


# ---------------------------------------------------------------------------
# The home page
# ---------------------------------------------------------------------------
def test_the_home_page_shows_a_got_it_button_for_a_plain_announcement(auto_login_user):
    """Backwards compatibility: an untouched row renders as before, plus a button."""
    client, _ = auto_login_user()
    announcement = AnnouncementFactory(title="Chapter dues", content="<p>Pay them.</p>")
    response = client.get(reverse("home"))
    body = response.content.decode()
    assert announcement.title in body
    assert "Pay them." in body
    assert f'name="id" value="{announcement.id}"' in body
    assert "Got it" in body


def test_the_home_page_hides_an_acknowledged_announcement_behind_a_disclosure(auto_login_user):
    client, user = auto_login_user()
    announcement = AnnouncementFactory(title="Old news")
    services.acknowledge(user, [{"kind": "announcement", "id": announcement.id}])
    response = client.get(reverse("home"))
    assert response.context["seen_count"] == 1
    assert 'id="tt-whats-new-seen"' in response.content.decode()


def test_the_home_page_renders_a_pinned_announcement_without_a_button(auto_login_user):
    client, _ = auto_login_user()
    pinned = AnnouncementFactory(title="You must sign this", dismissible=False)
    body = client.get(reverse("home")).content.decode()
    assert "You must sign this" in body
    # No acknowledge form for it anywhere -- the modal's own "Got it" footer
    # button is a dismiss for the dialog, not for this item.
    assert f'name="id" value="{pinned.id}"' not in body


def test_an_existing_announcement_reaches_exactly_the_same_audience(auto_login_user):
    """The compatibility guard: default fields mean "everyone signed in", as today."""
    announcement = AnnouncementFactory(title="Everyone sees this")
    assert announcement.audience == Audience.MEMBER
    assert announcement.roles == []
    assert announcement.dismissible is True
    assert announcement.feature is None
    for user in (_member(), _officer(), _natoff()):
        assert _titles(services.get_whats_new(user)) == ["Everyone sees this"]

    # ---------------------------------------------------------------------------
    # Maintenance
    # ---------------------------------------------------------------------------def test_prune_keeps_live_rows_and_drops_long_expired_ones():
    user = _member()
    live = AnnouncementFactory(title="Current")
    stale = AnnouncementFactory(
        title="Ancient",
        publish_start=timezone.now() - timedelta(days=900),
        publish_end=timezone.now() - timedelta(days=800),
    )
    _ack(user, live)
    _ack(user, stale)
    call_command("prune_acknowledgements", days=365)
    remaining = set(UserAcknowledgement.objects.values_list("object_id", flat=True))
    assert remaining == {live.id}


def test_prune_dry_run_deletes_nothing():
    user = _member()
    stale = AnnouncementFactory(
        publish_start=timezone.now() - timedelta(days=900),
        publish_end=timezone.now() - timedelta(days=800),
    )
    _ack(user, stale)
    call_command("prune_acknowledgements", days=365, dry_run=True)
    assert UserAcknowledgement.objects.count() == 1


def test_prune_drops_acknowledgements_of_deactivated_features():
    user = _member()
    feature = _new_feature(is_active=False)
    _ack(user, feature)
    call_command("prune_acknowledgements")
    assert not UserAcknowledgement.objects.exists()


def test_prune_drops_rows_whose_content_type_is_not_a_feed_kind():
    user = _member()
    UserAcknowledgement.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(user),
        object_id=user.id,
    )
    call_command("prune_acknowledgements")
    assert not UserAcknowledgement.objects.exists()


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
def test_every_page_loads_the_whats_new_script(client):
    """Production resolves {% static %} against a manifest; a missing file breaks every page."""
    assert (Path(settings.APPS_DIR) / "static" / "js" / "whats_new.js").is_file()
    assert "js/whats_new.js" in client.get(reverse("help")).content.decode()


def test_the_whats_new_templates_inline_no_script():
    """Behaviour lives in static/js/whats_new.js, wired by data attributes."""
    template_dir = Path(settings.APPS_DIR) / "templates" / "guides"
    for template in template_dir.glob("*whats_new*.html"):
        assert "<script" not in template.read_text(encoding="utf-8")
