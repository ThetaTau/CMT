import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from thetatauCMT.awards.models import AwardType
from thetatauCMT.awards.tests.factories import AwardTypeFactory

pytestmark = pytest.mark.django_db


def test_str_returns_name():
    award = AwardTypeFactory.create(name="Distinguished Service")
    assert str(award) == "Distinguished Service"


def test_sensible_defaults():
    award = AwardTypeFactory.create()
    assert award.is_active is True
    assert award.grant_method == AwardType.GrantMethod.DIRECT
    assert award.recurrence == AwardType.Recurrence.ONE_TIME
    assert award.single_winner is False
    assert award.allow_multiple_winners is False
    assert award.allow_multiple_nominations is False
    assert award.points is None
    assert award.created is not None
    assert award.modified is not None


# ---------------------------------------------------------------------------
# Acceptance: create award types across all levels
# ---------------------------------------------------------------------------
def test_create_award_types_across_all_levels():
    for level in AwardType.Level.values:
        award = AwardTypeFactory.create(level=level)
        reloaded = AwardType.objects.get(pk=award.pk)
        assert reloaded.level == level
    assert AwardType.objects.count() == len(AwardType.Level.values)


# ---------------------------------------------------------------------------
# Acceptance: grant_method + nominator_scope persist
# ---------------------------------------------------------------------------
def test_grant_method_and_nominator_scope_persist():
    award = AwardTypeFactory.create(
        grant_method=AwardType.GrantMethod.NOMINATION_WORKFLOW,
        nominator_scope=[
            AwardType.NominatorScope.MEMBER,
            AwardType.NominatorScope.OFFICER,
        ],
    )
    reloaded = AwardType.objects.get(pk=award.pk)
    assert reloaded.grant_method == AwardType.GrantMethod.NOMINATION_WORKFLOW
    assert set(reloaded.nominator_scope) == {"member", "officer"}


def test_nominator_scope_supports_all_three_roles():
    award = AwardTypeFactory.create(nominator_scope=["member", "officer", "national"])
    reloaded = AwardType.objects.get(pk=award.pk)
    assert set(reloaded.nominator_scope) == {"member", "officer", "national"}


# ---------------------------------------------------------------------------
# Acceptance: retired awards excluded from active lists
# ---------------------------------------------------------------------------
def test_retired_awards_excluded_from_active_lists():
    active = AwardTypeFactory.create(is_active=True)
    retired = AwardTypeFactory.create(is_active=False)
    active_qs = AwardType.objects.active()
    assert active in active_qs
    assert retired not in active_qs
    assert list(active_qs) == [active]


# ---------------------------------------------------------------------------
# Acceptance: badge / icon stored
# ---------------------------------------------------------------------------
def test_badge_image_stored():
    award = AwardTypeFactory.create()
    award.badge_image = SimpleUploadedFile("badge.png", b"fake-badge-bytes", content_type="image/png")
    award.save()
    reloaded = AwardType.objects.get(pk=award.pk)
    assert reloaded.badge_image.name.startswith("awards/badges/")
    assert reloaded.badge_image.name.endswith(".png")
    # Remove the file written to MEDIA_ROOT so the test leaves no artifacts.
    reloaded.badge_image.delete(save=False)
