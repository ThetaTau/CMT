"""The Feature Catalog page and the help hub (TWI-9, TWI-10).

The catalog is the one page that renders *everything* a viewer is allowed to
see, which makes it both the best place to catch an audience leak and the
easiest place to write an accidental O(n) query. Both are tested here.
"""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from thetatauCMT.configs.models import Config
from thetatauCMT.guides import services
from thetatauCMT.guides.models import Audience, Feature, UserAcknowledgement
from thetatauCMT.guides.tests.factories import FeatureAreaFactory, FeatureFactory, RoleGuideFactory
from thetatauCMT.users.tests.factories import UserAlterFactory, UserFactory

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


def _keys(catalog):
    return [entry["feature"].key for block in catalog for entry in block["features"]]


def _area_keys(catalog):
    return [block["area"].key for block in catalog]


def _mine(catalog, prefix):
    """Only the keys this test created.

    A reused test database may already hold the real registry (``dbseed`` or an
    earlier ``load_feature_registry``), so an assertion over the whole catalog
    would pass locally and fail on a fresh database, or the reverse.
    """
    return [key for key in _keys(catalog) if key.startswith(prefix)]


# ---------------------------------------------------------------------------
# get_catalog -- grouping and ordering
# ---------------------------------------------------------------------------
def test_catalog_groups_features_under_their_area_in_order():
    second = FeatureAreaFactory(key="second", order=2)
    first = FeatureAreaFactory(key="first", order=1)
    FeatureFactory(area=first, key="mine-a-one", order=1)
    FeatureFactory(area=first, key="mine-a-two", order=2)
    FeatureFactory(area=second, key="mine-b-one", order=1)

    catalog = services.get_catalog(_member())

    assert [key for key in _area_keys(catalog) if key in {"first", "second"}] == ["first", "second"]
    assert _mine(catalog, "mine-") == ["mine-a-one", "mine-a-two", "mine-b-one"]


def test_catalog_drops_an_area_with_nothing_visible_in_it():
    """An empty heading is worse than no heading."""
    FeatureFactory(
        area=FeatureAreaFactory(key="empty-for-members", audience=Audience.MEMBER),
        key="officers-only",
        audience=Audience.OFFICER,
    )

    assert "empty-for-members" not in _area_keys(services.get_catalog(_member()))
    assert "empty-for-members" in _area_keys(services.get_catalog(_officer()))


# ---------------------------------------------------------------------------
# Audience filtering -- the whole ladder
# ---------------------------------------------------------------------------
@pytest.fixture
def ladder():
    """One area per audience, in ascending order.

    ``order`` must be explicit: ``FeatureArea.Meta.ordering`` is
    ``["order", "name"]`` and the factory leaves every area at the default
    ``order=0``, so an unset order falls back to sorting by the
    factory-sequenced ``name`` (e.g. "Area 9" vs. "Area 10") -- alphabetical,
    not numeric, so it silently reorders once the process-wide sequence
    counter crosses a digit boundary. That made this fixture's assertions
    order-dependent on how many other ``FeatureAreaFactory`` rows earlier
    tests in the same worker had already created (worse with fewer xdist
    workers, since more tests share one worker's counter).
    """
    for order, audience in enumerate([Audience.PUBLIC, Audience.MEMBER, Audience.OFFICER, Audience.NATOFF]):
        area = FeatureAreaFactory(key=f"ladder-{audience}", audience=audience, order=order)
        FeatureFactory(area=area, key=f"ladder-{audience}-feature")


def test_anonymous_sees_only_public_entries(ladder):
    assert _mine(services.get_catalog(AnonymousUser()), "ladder-") == ["ladder-public-feature"]


def test_member_sees_public_and_member(ladder):
    assert _mine(services.get_catalog(_member()), "ladder-") == [
        "ladder-public-feature",
        "ladder-member-feature",
    ]


def test_officer_sees_everything_below_natoff(ladder):
    assert _mine(services.get_catalog(_officer()), "ladder-") == [
        "ladder-public-feature",
        "ladder-member-feature",
        "ladder-officer-feature",
    ]


def test_natoff_sees_everything(ladder):
    assert len(_mine(services.get_catalog(_natoff()), "ladder-")) == 4


def test_natoff_hidden_sees_the_member_view(ladder):
    """The "view as member" toggle has to change the catalog, or it is a lie."""
    user = _natoff()
    UserAlterFactory(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    assert _mine(services.get_catalog(user), "ladder-") == [
        "ladder-public-feature",
        "ladder-member-feature",
    ]


def test_flag_disabled_area_is_absent():
    area = FeatureAreaFactory(key="flagged", feature_flag="FEATURE_TEST_CATALOG")
    FeatureFactory(area=area, key="mine-behind-a-flag")
    flag = Config.objects.create(key="FEATURE_TEST_CATALOG", value="off", description="test")

    assert _mine(services.get_catalog(_member()), "mine-") == []

    flag.value = "on"
    flag.save()
    assert _mine(services.get_catalog(_member()), "mine-") == ["mine-behind-a-flag"]


# ---------------------------------------------------------------------------
# Card contents
# ---------------------------------------------------------------------------
def test_an_unresolvable_link_renders_the_card_without_a_url():
    """A missing URL must not take the whole page down with a NoReverseMatch."""
    FeatureFactory(key="broken", url_name="not:a:real:url")
    FeatureFactory(key="fine", url_name="home")

    urls = {
        entry["feature"].key: entry["url"] for block in services.get_catalog(_member()) for entry in block["features"]
    }

    assert urls["broken"] is None
    assert urls["fine"] == reverse("home")


def test_new_badge_follows_the_whats_new_rule(settings):
    from django.utils import timezone

    settings.NEW_FEATURE_MAX_AGE_DAYS = 30
    fresh = FeatureFactory(key="fresh", released_at=timezone.now().date())
    FeatureFactory(key="stale", released_at=timezone.now().date() - timezone.timedelta(days=90))
    user = _member()

    badges = {
        entry["feature"].key: entry["is_new"] for block in services.get_catalog(user) for entry in block["features"]
    }
    assert badges == {"fresh": True, "stale": False}

    # "Got it" anywhere clears it everywhere -- one lifecycle, not two.
    from django.contrib.contenttypes.models import ContentType

    UserAcknowledgement.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(Feature),
        object_id=fresh.pk,
        source=UserAcknowledgement.Source.MODAL,
    )
    badges = {
        entry["feature"].key: entry["is_new"] for block in services.get_catalog(user) for entry in block["features"]
    }
    assert badges["fresh"] is False


def test_duty_role_chips_show_only_the_roles_the_viewer_holds():
    FeatureFactory(key="dues", roles=["treasurer", "regent"])
    user = _member()
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    catalog = services.get_catalog(user)
    assert catalog[0]["features"][0]["duty_roles"] == ["treasurer"]


# ---------------------------------------------------------------------------
# Query budget
# ---------------------------------------------------------------------------
def test_catalog_query_count_does_not_grow_with_the_number_of_features():
    """The catalog renders every visible feature; a per-card query would be fatal."""
    area = FeatureAreaFactory(key="big")
    for index in range(3):
        FeatureFactory(area=area, key=f"small-{index}")
    user = _member()
    services.get_catalog(user)  # warm the content type / flag caches

    with CaptureQueriesContext(connection) as small:
        services.get_catalog(user)

    for index in range(30):
        FeatureFactory(area=area, key=f"large-{index}")
    with CaptureQueriesContext(connection) as large:
        services.get_catalog(user)

    assert len(large) == len(small)


# ---------------------------------------------------------------------------
# The page itself
# ---------------------------------------------------------------------------
def test_catalog_page_renders_for_an_anonymous_visitor(client):
    """Deliberately not login-required: this is the "what is this thing?" page."""
    area = FeatureAreaFactory(key="public-area", audience=Audience.PUBLIC)
    FeatureFactory(area=area, key="join", name="Join a chapter", audience=Audience.PUBLIC)

    response = client.get(reverse("guides:catalog"))

    assert response.status_code == 200
    assert "Join a chapter" in response.content.decode()


def test_catalog_page_hides_officer_entries_from_a_member(auto_login_user):
    client, _ = auto_login_user()
    FeatureFactory(key="members-thing", name="Members thing", audience=Audience.MEMBER)
    FeatureFactory(key="officers-thing", name="Officers thing", audience=Audience.OFFICER)

    body = client.get(reverse("guides:catalog")).content.decode()

    assert "Members thing" in body
    assert "Officers thing" not in body


def test_catalog_page_links_to_your_own_role_guide(auto_login_user):
    """The catalog answers "what can it do"; the guide answers "what do I owe"."""
    client, user = auto_login_user()
    guide = RoleGuideFactory(role="treasurer", title="Treasurer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])
    FeatureFactory(key="anything", name="Anything")

    body = client.get(reverse("guides:catalog")).content.decode()

    assert guide.get_absolute_url() in body


def test_catalog_page_points_a_member_with_no_office_at_the_index(auto_login_user):
    client, _ = auto_login_user()
    FeatureFactory(key="anything", name="Anything")

    body = client.get(reverse("guides:catalog")).content.decode()

    assert reverse("guides:role-guides") in body


def test_each_catalog_area_is_a_collapsible_panel(auto_login_user):
    """With 120-odd entries the page is only scannable once the areas fold up."""
    client, _ = auto_login_user()
    FeatureFactory(area=FeatureAreaFactory(key="foldable"), key="in-there")

    body = client.get(reverse("guides:catalog")).content.decode()

    assert 'id="panel-foldable"' in body
    assert 'data-bs-target="#panel-foldable"' in body
    assert 'id="tt-catalog-expand"' in body


# ---------------------------------------------------------------------------
# Help hub (TWI-10)
# ---------------------------------------------------------------------------
def test_help_hub_renders_signed_out(client):
    FeatureAreaFactory(key="public-area", audience=Audience.PUBLIC)
    response = client.get(reverse("help"))
    assert response.status_code == 200


def test_help_hub_offers_only_the_catalog_signed_out(client):
    """Role guides and What's New need an account, so they are not advertised."""
    FeatureAreaFactory(key="public-area", audience=Audience.PUBLIC)

    body = client.get(reverse("help")).content.decode()

    assert "What can the CMT do?" in body
    assert "What am I responsible for?" not in body
    assert "What&#x27;s new?" not in body


def test_help_hub_renders_signed_in(auto_login_user):
    client, _ = auto_login_user()
    FeatureFactory(key="something", name="Something useful")

    response = client.get(reverse("help"))

    assert response.status_code == 200
    assert "What can the CMT do?" in response.content.decode()


def test_help_hub_is_reachable_without_javascript(auto_login_user):
    """The help icon is a plain link, so it works with scripting off."""
    client, _ = auto_login_user()
    body = client.get(reverse("home")).content.decode()
    assert f'href="{reverse("help")}"' in body


def test_signed_out_client_is_not_redirected_from_the_catalog():
    assert Client().get(reverse("guides:catalog")).status_code == 200
