import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template

from thetatauCMT.awards.models import OfficerBadge
from thetatauCMT.awards.services import revoke_grant
from thetatauCMT.awards.templatetags.award_tags import (
    award_badge_types_for,
    award_grants_for,
    officer_badges_for,
)
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardGrantFactory, AwardTypeFactory
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _render_inline(recipient):
    return Template("{% load award_tags %}{% inline_badges recipient %}").render(Context({"recipient": recipient}))


def _render_section(recipient, show_revoked=None):
    if show_revoked is None:
        template = "{% load award_tags %}{% awards_section recipient %}"
    else:
        template = "{% load award_tags %}{% awards_section recipient show_revoked=sr %}"
    return Template(template).render(Context({"recipient": recipient, "sr": show_revoked}))


# ---------------------------------------------------------------------------
# Acceptance: member / chapter / region awards render
# ---------------------------------------------------------------------------
def test_member_awards_render():
    member = UserFactory(status="active")
    grant = AwardGrantFactory(award_type=AwardTypeFactory(name="Distinguished Service"), recipient_member=member)
    assert grant in award_grants_for(member)
    assert "Distinguished Service" in _render_section(member)


def test_chapter_awards_render():
    chapter = ChapterFactory()
    grant = AwardGrantFactory(
        recipient_member=None, recipient_chapter=chapter, award_type=AwardTypeFactory(name="Chapter Excellence")
    )
    assert grant in award_grants_for(chapter)
    assert "Chapter Excellence" in _render_section(chapter)


def test_region_awards_render():
    region = RegionFactory()
    grant = AwardGrantFactory(
        recipient_member=None, recipient_region=region, award_type=AwardTypeFactory(name="Region Award")
    )
    assert grant in award_grants_for(region)
    assert "Region Award" in _render_section(region)


# ---------------------------------------------------------------------------
# Acceptance: badges shown + inline icon tag renders award + officer icons
# ---------------------------------------------------------------------------
def test_inline_badges_renders_award_and_officer_icons():
    member = UserFactory(status="active", current_roles=["grand regent"])
    award = AwardTypeFactory(name="Best Award")
    award.badge_image = SimpleUploadedFile("badge.png", b"fake-image", content_type="image/png")
    award.save()
    AwardGrantFactory(award_type=award, recipient_member=member)
    OfficerBadge.objects.create(role="grand regent", short_label="GR", icon_class="fa fa-star")

    html = _render_inline(member)
    assert award.badge_image.url in html  # award badge image
    assert "fa fa-star" in html  # officer icon
    award.badge_image.delete(save=False)


def test_award_badge_types_only_with_image():
    member = UserFactory(status="active")
    with_badge = AwardTypeFactory(name="Badged")
    with_badge.badge_image = SimpleUploadedFile("b.png", b"x", content_type="image/png")
    with_badge.save()
    no_badge = AwardTypeFactory(name="Plain")
    AwardGrantFactory(award_type=with_badge, recipient_member=member)
    AwardGrantFactory(award_type=no_badge, recipient_member=member)
    badge_types = award_badge_types_for(member)
    assert with_badge in badge_types
    assert no_badge not in badge_types
    with_badge.badge_image.delete(save=False)


# ---------------------------------------------------------------------------
# Acceptance: revoked handled per config
# ---------------------------------------------------------------------------
def test_revoked_hidden_by_default_shown_when_configured():
    member = UserFactory(status="active")
    active = AwardGrantFactory(award_type=AwardTypeFactory(name="Active Award"), recipient_member=member)
    revoked = AwardGrantFactory(award_type=AwardTypeFactory(name="Revoked Award"), recipient_member=member)
    revoke_grant(revoked, UserFactory())

    assert active in award_grants_for(member)
    assert revoked not in award_grants_for(member)
    assert revoked in award_grants_for(member, revoked=True)

    default_html = _render_section(member)  # AWARDS_SHOW_REVOKED defaults False
    assert "Revoked Award" not in default_html
    assert "Active Award" in default_html

    shown_html = _render_section(member, show_revoked=True)
    assert "Revoked Award" in shown_html


# ---------------------------------------------------------------------------
# officer_badges_for helper
# ---------------------------------------------------------------------------
def test_officer_badges_matching_active_roles_only():
    member = UserFactory(current_roles=["grand regent"])
    OfficerBadge.objects.create(role="grand regent", short_label="GR")
    OfficerBadge.objects.create(role="grand scribe", short_label="GS")  # not held
    badges = officer_badges_for(member)
    assert [badge.role for badge in badges] == ["grand regent"]


def test_officer_badges_excludes_inactive():
    member = UserFactory(current_roles=["grand treasurer"])
    OfficerBadge.objects.create(role="grand treasurer", short_label="GT", is_active=False)
    assert officer_badges_for(member) == []


def test_officer_badges_empty_for_non_member():
    assert officer_badges_for(ChapterFactory()) == []
    assert officer_badges_for(UserFactory()) == []  # no current_roles


# ---------------------------------------------------------------------------
# Acceptance: performant (no N+1)
# ---------------------------------------------------------------------------
def test_award_grants_single_query(django_assert_num_queries):
    member = UserFactory(status="active")
    cycle = AwardCycleFactory()
    for _ in range(5):
        AwardGrantFactory(award_type=AwardTypeFactory(), cycle=cycle, recipient_member=member)
    with django_assert_num_queries(1):
        grants = list(award_grants_for(member))
    assert len(grants) == 5


def test_officer_badges_single_query(django_assert_num_queries):
    member = UserFactory(current_roles=["grand regent", "grand scribe"])
    OfficerBadge.objects.create(role="grand regent")
    OfficerBadge.objects.create(role="grand scribe")
    with django_assert_num_queries(1):
        badges = officer_badges_for(member)
    assert len(badges) == 2
