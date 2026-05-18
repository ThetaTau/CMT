import pytest
from thetatauCMT.regions.models import Region


def _make_region(name, **kwargs):
    defaults = dict(
        email=f"{name.lower().replace(' ', '')}@thetatau.org",
        website="https://thetatau.org",
        facebook="https://facebook.com/thetatau",
    )
    defaults.update(kwargs)
    region = Region(name=name, **defaults)
    region.save()
    return region


@pytest.mark.django_db
def test_region_str():
    region = _make_region("Western")
    assert str(region) == "Western"


@pytest.mark.django_db
def test_region_save_sets_slug():
    region = _make_region("Great Lakes")
    assert region.slug == "great-lakes"


@pytest.mark.django_db
def test_region_save_updates_slug_on_rename():
    region = _make_region("Old Name Region")
    assert region.slug == "old-name-region"
    region.name = "New Name Region"
    region.save()
    assert region.slug == "new-name-region"


@pytest.mark.django_db
def test_region_choices_includes_national():
    choices = Region.region_choices()
    slugs = [c[0] for c in choices]
    assert "national" in slugs


@pytest.mark.django_db
def test_region_choices_national_is_first():
    choices = Region.region_choices()
    assert choices[0][0] == "national"


@pytest.mark.django_db
def test_region_choices_includes_candidate_chapter():
    choices = Region.region_choices()
    slugs = [c[0] for c in choices]
    assert "candidate_chapter" in slugs


@pytest.mark.django_db
def test_region_choices_includes_saved_region():
    region = _make_region("Pacific Northwest Test")
    choices = Region.region_choices()
    slugs = [c[0] for c in choices]
    assert region.slug in slugs


@pytest.mark.django_db
def test_region_choices_returns_list():
    choices = Region.region_choices()
    assert isinstance(choices, list)
    # Each choice is a (value, label) tuple
    for choice in choices:
        assert len(choice) == 2
