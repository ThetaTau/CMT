import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from thetatauCMT.guides.models import Audience, Feature, FeatureArea
from thetatauCMT.guides.tests.factories import FeatureAreaFactory, FeatureFactory
from thetatauCMT.tasks.models import Task

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Acceptance: create areas and features
# ---------------------------------------------------------------------------
def test_str_returns_name():
    area = FeatureAreaFactory.create(name="Finances")
    feature = FeatureFactory.create(area=area, name="Submit an invoice")
    assert str(area) == "Finances"
    assert str(feature) == "Submit an invoice"


def test_sensible_defaults():
    area = FeatureAreaFactory.create()
    feature = FeatureFactory.create(area=area)
    assert area.is_active is True
    assert area.order == 0
    assert area.audience == Audience.MEMBER
    assert area.feature_flag == ""
    assert feature.is_active is True
    assert feature.is_highlighted is False
    assert feature.order == 0
    assert feature.audience == ""
    assert feature.roles == []
    assert feature.url_kwargs == {}
    assert feature.released_at is None
    assert feature.created is not None
    assert feature.modified is not None


def test_features_are_reachable_from_their_area():
    area = FeatureAreaFactory.create()
    FeatureFactory.create_batch(3, area=area)
    assert area.features.count() == 3


def test_area_supports_every_audience():
    for audience in Audience.values:
        area = FeatureAreaFactory.create(audience=audience)
        assert FeatureArea.objects.get(pk=area.pk).audience == audience


# ---------------------------------------------------------------------------
# Acceptance: keys are unique -- they are the fixture's stable identity
# ---------------------------------------------------------------------------
def test_area_key_is_unique():
    FeatureAreaFactory.create(key="a-made-up-area")
    with pytest.raises(IntegrityError):
        FeatureAreaFactory.create(key="a-made-up-area")


def test_feature_key_is_unique_across_areas():
    first = FeatureAreaFactory.create()
    second = FeatureAreaFactory.create()
    FeatureFactory.create(area=first, key="submit-invoice")
    with pytest.raises(IntegrityError):
        FeatureFactory.create(area=second, key="submit-invoice")


# ---------------------------------------------------------------------------
# Acceptance: ordering is respected
# ---------------------------------------------------------------------------
def test_areas_order_by_order_then_name():
    # Scoped to these three rows: the real registry is seeded into the test
    # database (see thetatauCMT/conftest.py), so the table is never empty.
    made = [
        FeatureAreaFactory.create(name="Zulu", order=1),
        FeatureAreaFactory.create(name="Bravo", order=2),
        FeatureAreaFactory.create(name="Alpha", order=2),
    ]
    ours = FeatureArea.objects.filter(pk__in=[area.pk for area in made])
    assert [area.name for area in ours] == ["Zulu", "Alpha", "Bravo"]


def test_features_order_by_area_order_then_own_order():
    first_area = FeatureAreaFactory.create(order=1)
    second_area = FeatureAreaFactory.create(order=2)
    made = [
        FeatureFactory.create(area=second_area, name="Third", order=1),
        FeatureFactory.create(area=first_area, name="Second", order=2),
        FeatureFactory.create(area=first_area, name="First", order=1),
    ]
    ours = Feature.objects.filter(pk__in=[feature.pk for feature in made])
    assert [feature.name for feature in ours] == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# Acceptance: inactive rows are excluded from the active querysets
# ---------------------------------------------------------------------------
def test_active_areas_exclude_inactive():
    live = FeatureAreaFactory.create()
    dead = FeatureAreaFactory.create(is_active=False)
    ours = FeatureArea.objects.active().filter(pk__in=[live.pk, dead.pk])
    assert list(ours) == [live]


def test_active_features_exclude_inactive():
    area = FeatureAreaFactory.create()
    live = FeatureFactory.create(area=area)
    FeatureFactory.create(area=area, is_active=False)
    assert list(Feature.objects.active().filter(area=area)) == [live]


def test_deactivating_an_area_hides_its_active_features():
    """An inactive area takes its features with it, so callers check one flag."""
    area = FeatureAreaFactory.create(is_active=False)
    FeatureFactory.create(area=area, is_active=True)
    assert Feature.objects.active().filter(area=area).count() == 0


# ---------------------------------------------------------------------------
# Acceptance: validation rejects unknown roles and audiences
# ---------------------------------------------------------------------------
def test_roles_accept_known_duty_roles():
    feature = FeatureFactory.create(roles=["treasurer", "regent"])
    feature.full_clean()
    assert Feature.objects.get(pk=feature.pk).roles == ["treasurer", "regent"]


def test_roles_reject_unknown_values():
    feature = FeatureFactory.build(area=FeatureAreaFactory.create(), roles=["treasurer", "grand-poobah"])
    with pytest.raises(ValidationError) as excinfo:
        feature.full_clean()
    assert "roles" in excinfo.value.error_dict
    assert "grand-poobah" in str(excinfo.value)


def test_roles_reject_a_non_list():
    feature = FeatureFactory.build(area=FeatureAreaFactory.create(), roles={"role": "treasurer"})
    with pytest.raises(ValidationError) as excinfo:
        feature.full_clean()
    assert "roles" in excinfo.value.error_dict


def test_feature_audience_rejects_unknown_value():
    feature = FeatureFactory.build(area=FeatureAreaFactory.create(), audience="wizard")
    with pytest.raises(ValidationError) as excinfo:
        feature.full_clean()
    assert "audience" in excinfo.value.error_dict


def test_area_audience_rejects_unknown_value():
    area = FeatureAreaFactory.build(audience="wizard")
    with pytest.raises(ValidationError) as excinfo:
        area.full_clean()
    assert "audience" in excinfo.value.error_dict


def test_blank_feature_audience_is_valid():
    """Blank means "inherit the area", so it must survive validation."""
    feature = FeatureFactory.build(area=FeatureAreaFactory.create(), audience="")
    feature.full_clean()


# ---------------------------------------------------------------------------
# Acceptance: feature_flag persists
# ---------------------------------------------------------------------------
def test_feature_flag_persists_on_both_models():
    area = FeatureAreaFactory.create(feature_flag="FEATURE_AWARDS")
    feature = FeatureFactory.create(area=area, feature_flag="FEATURE_JOBS")
    assert FeatureArea.objects.get(pk=area.pk).feature_flag == "FEATURE_AWARDS"
    assert Feature.objects.get(pk=feature.pk).feature_flag == "FEATURE_JOBS"


# ---------------------------------------------------------------------------
# Inheritance of audience and feature flag from the area
# ---------------------------------------------------------------------------
def test_blank_feature_audience_and_flag_inherit_the_area():
    area = FeatureAreaFactory.create(audience=Audience.NATOFF, feature_flag="FEATURE_AWARDS")
    feature = FeatureFactory.create(area=area, audience="", feature_flag="")
    assert feature.effective_audience == Audience.NATOFF
    assert feature.effective_feature_flag == "FEATURE_AWARDS"


def test_feature_audience_and_flag_override_the_area():
    area = FeatureAreaFactory.create(audience=Audience.MEMBER, feature_flag="FEATURE_AWARDS")
    feature = FeatureFactory.create(area=area, audience=Audience.NATOFF, feature_flag="FEATURE_JOBS")
    assert feature.effective_audience == Audience.NATOFF
    assert feature.effective_feature_flag == "FEATURE_JOBS"


# ---------------------------------------------------------------------------
# Link targets: url_name / external_url are mutually exclusive
# ---------------------------------------------------------------------------
def test_url_name_and_kwargs_persist():
    feature = FeatureFactory.create(url_name="chapters:detail", url_kwargs={"slug": "@chapter_slug"})
    reloaded = Feature.objects.get(pk=feature.pk)
    assert reloaded.url_name == "chapters:detail"
    assert reloaded.url_kwargs == {"slug": "@chapter_slug"}


def test_namespaced_viewflow_url_name_fits():
    feature = FeatureFactory.create(url_name="viewflow:forms:hseducation:start")
    assert Feature.objects.get(pk=feature.pk).url_name == "viewflow:forms:hseducation:start"


def test_external_url_persists_for_features_outside_django():
    feature = FeatureFactory.create(external_url="https://thetatau-tx.vectorlmsedu.com")
    feature.full_clean()
    assert Feature.objects.get(pk=feature.pk).external_url == "https://thetatau-tx.vectorlmsedu.com"


def test_url_name_and_external_url_cannot_both_be_set():
    feature = FeatureFactory.build(
        area=FeatureAreaFactory.create(),
        url_name="forms:pledgeform",
        external_url="https://example.org",
    )
    with pytest.raises(ValidationError) as excinfo:
        feature.full_clean()
    assert "url_name" in excinfo.value.error_dict
    assert "external_url" in excinfo.value.error_dict


def test_a_feature_may_have_no_link_at_all():
    """Explanation-only entries are still worth cataloguing."""
    feature = FeatureFactory.build(area=FeatureAreaFactory.create())
    feature.full_clean()


# ---------------------------------------------------------------------------
# Optional links out to existing models / release metadata
# ---------------------------------------------------------------------------
def test_feature_can_link_to_a_task_and_survives_its_deletion():
    task = Task.objects.create(
        name="Submit the budget",
        owner="treasurer",
        type="task",
        description="Annual chapter budget.",
    )
    feature = FeatureFactory.create(task=task)
    assert task.features.get() == feature
    task.delete()
    feature.refresh_from_db()
    assert feature.task is None


def test_release_metadata_persists():
    feature = FeatureFactory.create(
        released_at=datetime.date(2026, 3, 1),
        release_version="2026.03",
        is_highlighted=True,
    )
    reloaded = Feature.objects.get(pk=feature.pk)
    assert reloaded.released_at == datetime.date(2026, 3, 1)
    assert reloaded.release_version == "2026.03"
    assert reloaded.is_highlighted is True
