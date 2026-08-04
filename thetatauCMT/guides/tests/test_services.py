import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from thetatauCMT.configs.models import Config
from thetatauCMT.guides import services
from thetatauCMT.guides.models import Audience
from thetatauCMT.guides.tests.factories import FeatureAreaFactory, FeatureFactory
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


# ---------------------------------------------------------------------------
# user_audience
# ---------------------------------------------------------------------------
def test_anonymous_is_public():
    assert services.user_audience(AnonymousUser()) == Audience.PUBLIC
    assert services.user_audience(None) == Audience.PUBLIC


def test_plain_user_is_member():
    assert services.user_audience(_member()) == Audience.MEMBER


def test_officer_group_is_officer():
    assert services.user_audience(_officer()) == Audience.OFFICER


def test_natoff_group_is_natoff():
    assert services.user_audience(_natoff()) == Audience.NATOFF


def test_national_officer_role_without_the_group_is_natoff():
    """``NationalOfficerRequiredMixin`` admits a role holder who is not in the group."""
    user = _member()
    user.current_roles = ["grand regent"]
    user.save(update_fields=["current_roles"])
    assert services.user_audience(user) == Audience.NATOFF


def test_superuser_is_natoff():
    """There is no superuser audience -- admin tooling is out of the catalog."""
    user = _member()
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    assert services.user_audience(user) == Audience.NATOFF


def test_natoff_hidden_drops_to_member():
    """The "view as member" toggle must actually change what the catalog offers."""
    user = _natoff()
    UserAlterFactory(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    assert services.user_audience(user) == Audience.MEMBER


def test_natoff_hidden_who_is_also_an_officer_drops_to_officer():
    user = _in_group(_natoff(), "officer")
    UserAlterFactory(user=user, chapter=user.chapter, role=None, hide_natoff=True)
    assert services.user_audience(user) == Audience.OFFICER


# ---------------------------------------------------------------------------
# get_visible_areas
# ---------------------------------------------------------------------------
@pytest.fixture
def area_ladder():
    """One active area per audience, keyed by audience value."""
    return {audience: FeatureAreaFactory(key=f"area-{audience}", audience=audience) for audience in Audience.values}


def _keys(entries):
    return {entry.key for entry in entries}


def test_anonymous_sees_only_public_areas(area_ladder):
    assert _keys(services.get_visible_areas(AnonymousUser())) == {"area-public"}


def test_member_sees_public_and_member_areas(area_ladder):
    assert _keys(services.get_visible_areas(_member())) == {"area-public", "area-member"}


def test_officer_sees_one_more_than_a_member(area_ladder):
    assert _keys(services.get_visible_areas(_officer())) == {"area-public", "area-member", "area-officer"}


def test_natoff_sees_everything(area_ladder):
    assert _keys(services.get_visible_areas(_natoff())) == {f"area-{audience}" for audience in Audience.values}


def test_inactive_areas_are_never_visible():
    FeatureAreaFactory(key="live", audience=Audience.MEMBER)
    FeatureAreaFactory(key="retired", audience=Audience.MEMBER, is_active=False)
    assert _keys(services.get_visible_areas(_member())) == {"live"}


def test_area_with_a_disabled_flag_is_hidden():
    FeatureAreaFactory(key="awards", audience=Audience.MEMBER, feature_flag="FEATURE_AWARDS")
    member = _member()
    assert _keys(services.get_visible_areas(member)) == {"awards"}
    Config.objects.create(key="FEATURE_AWARDS", value="off", description="test")
    assert services.get_visible_areas(member) == []


# ---------------------------------------------------------------------------
# get_visible_features
# ---------------------------------------------------------------------------
def test_feature_inherits_its_area_audience_when_blank():
    area = FeatureAreaFactory(audience=Audience.NATOFF)
    FeatureFactory(area=area, key="inherits", audience="")
    assert services.get_visible_features(_member()) == []
    assert _keys(services.get_visible_features(_natoff())) == {"inherits"}


def test_feature_audience_can_be_stricter_than_its_area():
    area = FeatureAreaFactory(audience=Audience.MEMBER)
    FeatureFactory(area=area, key="open", audience="")
    FeatureFactory(area=area, key="restricted", audience=Audience.NATOFF)
    assert _keys(services.get_visible_features(_member())) == {"open"}
    assert _keys(services.get_visible_features(_natoff())) == {"open", "restricted"}


def test_features_can_be_limited_to_one_area():
    wanted = FeatureAreaFactory(audience=Audience.MEMBER)
    other = FeatureAreaFactory(audience=Audience.MEMBER)
    FeatureFactory(area=wanted, key="wanted")
    FeatureFactory(area=other, key="other")
    assert _keys(services.get_visible_features(_member(), area=wanted)) == {"wanted"}


def test_inactive_features_and_features_of_inactive_areas_are_hidden():
    area = FeatureAreaFactory(audience=Audience.MEMBER)
    dead_area = FeatureAreaFactory(audience=Audience.MEMBER, is_active=False)
    FeatureFactory(area=area, key="live")
    FeatureFactory(area=area, key="retired", is_active=False)
    FeatureFactory(area=dead_area, key="orphan")
    assert _keys(services.get_visible_features(_member())) == {"live"}


def test_feature_inherits_a_disabled_area_flag():
    area = FeatureAreaFactory(audience=Audience.MEMBER, feature_flag="FEATURE_JOBS")
    FeatureFactory(area=area, key="post-a-job", feature_flag="")
    Config.objects.create(key="FEATURE_JOBS", value="off", description="test")
    assert services.get_visible_features(_member()) == []


def test_feature_flag_overrides_the_area_flag():
    area = FeatureAreaFactory(audience=Audience.MEMBER, feature_flag="FEATURE_JOBS")
    FeatureFactory(area=area, key="own-flag", feature_flag="FEATURE_AWARDS")
    Config.objects.create(key="FEATURE_JOBS", value="off", description="test")
    assert _keys(services.get_visible_features(_member())) == {"own-flag"}


def test_flag_lookups_are_shared_across_features():
    """One Config lookup per distinct flag, not one per feature."""
    area = FeatureAreaFactory(audience=Audience.MEMBER)
    member = _member()
    FeatureFactory(area=area, key="flagged-0", feature_flag="FEATURE_AWARDS")

    def count_queries():
        with CaptureQueriesContext(connection) as captured:
            services.get_visible_features(member)
        return len(captured.captured_queries)

    with_one = count_queries()
    for index in range(1, 6):
        FeatureFactory(area=area, key=f"flagged-{index}", feature_flag="FEATURE_AWARDS")
    assert count_queries() == with_one


# ---------------------------------------------------------------------------
# resolve_feature_url
# ---------------------------------------------------------------------------
def test_static_kwargs_resolve():
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={"slug": "alpha-beta"})
    assert services.resolve_feature_url(feature, _member()) == reverse("chapters:detail", kwargs={"slug": "alpha-beta"})


def test_chapter_slug_token_resolves_per_viewer():
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={"slug": "@chapter_slug"})
    member = _member()
    expected = reverse("chapters:detail", kwargs={"slug": member.current_chapter.slug})
    assert services.resolve_feature_url(feature, member) == expected


def test_region_slug_token_resolves_per_viewer():
    feature = FeatureFactory(url_name="regions:detail", url_kwargs={"slug": "@region_slug"})
    member = _member()
    expected = reverse("regions:detail", kwargs={"slug": member.current_chapter.region.slug})
    assert services.resolve_feature_url(feature, member) == expected


def test_username_token_resolves_per_viewer():
    feature = FeatureFactory(url_name="users:profile", url_kwargs={"username": "@username"})
    member = _member()
    assert services.resolve_feature_url(feature, member) == reverse(
        "users:profile", kwargs={"username": member.username}
    )


def test_user_alter_chapter_is_honoured_by_the_chapter_token():
    """A natoff impersonating another chapter should be linked to that chapter."""
    natoff = _natoff()
    alter = UserAlterFactory(user=natoff, role=None)
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={"slug": "@chapter_slug"})
    expected = reverse("chapters:detail", kwargs={"slug": alter.chapter.slug})
    assert services.resolve_feature_url(feature, natoff) == expected


def test_anonymous_viewer_cannot_resolve_a_token():
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={"slug": "@chapter_slug"})
    assert services.resolve_feature_url(feature, AnonymousUser()) is None


def test_unknown_token_returns_none():
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={"slug": "@planet"})
    assert services.resolve_feature_url(feature, _member()) is None


def test_unreversible_url_name_returns_none_instead_of_raising():
    feature = FeatureFactory(url_name="nope:does-not-exist")
    assert services.resolve_feature_url(feature, _member()) is None


def test_missing_kwargs_return_none_instead_of_raising():
    feature = FeatureFactory(url_name="chapters:detail", url_kwargs={})
    assert services.resolve_feature_url(feature, _member()) is None


def test_feature_without_a_link_returns_none():
    assert services.resolve_feature_url(FeatureFactory(), _member()) is None


def test_external_url_is_returned_as_is():
    feature = FeatureFactory(external_url="https://thetatau-tx.vectorlmsedu.com")
    assert services.resolve_feature_url(feature, _member()) == "https://thetatau-tx.vectorlmsedu.com"


def test_namespaced_viewflow_url_resolves():
    feature = FeatureFactory(url_name="viewflow:forms:hseducation:start")
    assert services.resolve_feature_url(feature, _member()) is not None


def test_a_fragment_is_appended_so_the_link_lands_on_the_control():
    """Several features are a form on a bigger page, not a page of their own."""
    feature = FeatureFactory(url_name="events:feeds", url_fragment="task-reminders")
    assert services.resolve_feature_url(feature, _member()) == f"{reverse('events:feeds')}#task-reminders"


def test_a_fragment_is_left_off_when_the_url_cannot_be_resolved():
    feature = FeatureFactory(url_name="nope:does-not-exist", url_fragment="somewhere")
    assert services.resolve_feature_url(feature, _member()) is None


# ---------------------------------------------------------------------------
# get_duty_roles
# ---------------------------------------------------------------------------
def test_anonymous_has_no_duty_roles():
    assert services.get_duty_roles(AnonymousUser()) == set()


def test_plain_member_has_no_duty_roles():
    assert services.get_duty_roles(_member()) == set()


def test_current_roles_become_duty_roles():
    user = _member()
    user.current_roles = ["treasurer", "risk management chair"]
    user.save(update_fields=["current_roles"])
    assert services.get_duty_roles(user) == {"treasurer", "risk management chair"}


def test_unknown_role_values_are_dropped():
    user = _member()
    user.current_roles = ["treasurer", "grand-poobah"]
    user.save(update_fields=["current_roles"])
    assert services.get_duty_roles(user) == {"treasurer"}


def test_user_alter_role_is_included():
    """A natoff impersonating a treasurer should get the treasurer's guidance."""
    natoff = _natoff()
    UserAlterFactory(user=natoff, chapter=natoff.chapter, role="treasurer")
    assert "treasurer" in services.get_duty_roles(natoff)
