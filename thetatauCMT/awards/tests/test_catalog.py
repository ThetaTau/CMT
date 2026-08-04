import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.awards.eligibility import describe_eligibility
from thetatauCMT.awards.services import revoke_grant
from thetatauCMT.awards.tests._helpers import sign_rmp
from thetatauCMT.awards.tests.factories import AwardGrantFactory, AwardTypeFactory, EligibilityRuleFactory
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _catalog_url():
    # Resolved lazily: the root urlconf pulls in viewflow, which touches the DB.
    return reverse("awards:catalog")


def _member():
    user = UserFactory(status="active")
    sign_rmp(user)
    return user


def _natoff():
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    sign_rmp(user)
    return user


@pytest.fixture(autouse=True)
def _signed_in(client):
    client.force_login(_member())


def _catalog_awards(response):
    return {award.name: award for group, awards in response.context["award_groups"] for award in awards}


# ---------------------------------------------------------------------------
# Acceptance: signed-in members can browse every available award
# ---------------------------------------------------------------------------
def test_catalog_requires_login(client):
    client.logout()
    response = client.get(_catalog_url())
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_catalog_lists_awards_with_description_and_eligibility(client):
    AwardTypeFactory(
        name="Distinguished Whatsit",
        description="Recognizes a truly distinguished whatsit.",
        eligibility="Any member in good standing.",
        category="Individual Member Award",
    )
    response = client.get(_catalog_url())
    assert response.status_code == 200
    content = response.content.decode()
    assert "Distinguished Whatsit" in content
    assert "Recognizes a truly distinguished whatsit." in content
    assert "Any member in good standing." in content


def test_catalog_groups_by_category(client):
    AwardTypeFactory(name="Member One", category="Individual Member Award")
    AwardTypeFactory(name="Chapter One", category="Chapter Award", level="chapter")
    response = client.get(_catalog_url())
    groups = dict(response.context["award_groups"])
    assert {award.name for award in groups["Individual Member Award"]} == {"Member One"}
    assert {award.name for award in groups["Chapter Award"]} == {"Chapter One"}


def test_catalog_links_each_award_to_its_winners(client):
    award = AwardTypeFactory(name="Linkable Award")
    response = client.get(_catalog_url())
    assert reverse("awards:type_winners", args=[award.pk]) in response.content.decode()


def test_catalog_counts_active_winners_only(client):
    award = AwardTypeFactory(name="Counted Award")
    AwardGrantFactory(award_type=award)
    revoked = AwardGrantFactory(award_type=award)
    revoke_grant(revoked, UserFactory(), reason="mistake")
    response = client.get(_catalog_url())
    assert _catalog_awards(response)["Counted Award"].winner_count == 1


def test_catalog_hides_retired_awards_from_members(client):
    AwardTypeFactory(name="Retired Award", is_active=False)
    AwardTypeFactory(name="Live Award")
    names = set(_catalog_awards(client.get(_catalog_url())))
    assert "Live Award" in names
    assert "Retired Award" not in names


def test_catalog_shows_retired_awards_to_national_officer(client):
    AwardTypeFactory(name="Retired Award", is_active=False)
    client.force_login(_natoff())
    names = set(_catalog_awards(client.get(f"{_catalog_url()}?show_retired=1")))
    assert "Retired Award" in names


def test_catalog_search_and_level_filter(client):
    AwardTypeFactory(name="Brotherhood Program", level="chapter")
    AwardTypeFactory(name="Service Commendation", level="member")
    names = set(_catalog_awards(client.get(_catalog_url(), {"q": "brotherhood"})))
    assert names == {"Brotherhood Program"}
    names = set(_catalog_awards(client.get(_catalog_url(), {"level": "member"})))
    assert names == {"Service Commendation"}


def test_catalog_nominate_button_only_for_nominatable_awards(client):
    AwardTypeFactory(
        name="Open Nomination",
        grant_method="nomination_workflow",
        nominator_scope=["member"],
    )
    AwardTypeFactory(
        name="National Only",
        grant_method="nomination_workflow",
        nominator_scope=["national"],
    )
    awards = _catalog_awards(client.get(_catalog_url()))
    assert awards["Open Nomination"].can_nominate is True
    assert awards["National Only"].can_nominate is False


# ---------------------------------------------------------------------------
# Eligibility summary rendered from the configured rules
# ---------------------------------------------------------------------------
def test_describe_eligibility_defaults_to_recipient_kind():
    assert describe_eligibility(AwardTypeFactory(level="member")) == ["Individual members"]
    assert describe_eligibility(AwardTypeFactory(level="chapter")) == ["Chapters"]
    assert describe_eligibility(AwardTypeFactory(level="region")) == ["Regions"]


def test_describe_eligibility_combines_member_statuses():
    award = AwardTypeFactory(level="member")
    EligibilityRuleFactory(award_type=award, member_status="active")
    EligibilityRuleFactory(award_type=award, member_status="alumni")
    assert describe_eligibility(award) == ["Active student members or Alumni members"]


def test_describe_eligibility_lists_scope_restrictions():
    award = AwardTypeFactory(level="chapter")
    chapter = ChapterFactory()
    region = RegionFactory()
    chapter_rule = EligibilityRuleFactory(award_type=award, rule_type="chapter_scope", member_status="")
    chapter_rule.chapters.add(chapter)
    region_rule = EligibilityRuleFactory(award_type=award, rule_type="region_scope", member_status="")
    region_rule.regions.add(region)
    bullets = describe_eligibility(award)
    assert f"Limited to chapters: {chapter}" in bullets
    assert f"Limited to regions: {region}" in bullets


def test_award_type_winners_page_shows_eligibility(client):
    award = AwardTypeFactory(name="Eligible Award", eligibility="Only the finest members.")
    EligibilityRuleFactory(award_type=award, member_status="active")
    response = client.get(reverse("awards:type_winners", args=[award.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Only the finest members." in content
    assert "Active student members" in content
    assert response.context["eligibility_bullets"] == ["Active student members"]
