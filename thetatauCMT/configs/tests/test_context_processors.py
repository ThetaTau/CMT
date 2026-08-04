import pytest

from thetatauCMT.configs.models import Config
from thetatauCMT.utils.context_processors import feature_flags, incident_report


@pytest.fixture
def make_config():
    def _make(key, value, description="Test description"):
        config = Config(key=key, value=value, description=description)
        config.save()
        return config

    return _make


@pytest.mark.django_db
def test_feature_flags_exposes_expected_keys():
    """The context processor returns exactly the three flag variables."""
    result = feature_flags(None)
    assert set(result) == {
        "feature_awards_enabled",
        "feature_jobs_enabled",
        "feature_events_calendar_enabled",
    }


@pytest.mark.django_db
def test_feature_flags_enabled_by_default():
    """All flags are enabled when no disabling Config row exists."""
    result = feature_flags(None)
    assert result["feature_awards_enabled"] is True
    assert result["feature_jobs_enabled"] is True
    assert result["feature_events_calendar_enabled"] is True


@pytest.mark.django_db
def test_feature_flags_reflect_disabled_config(make_config):
    """Disabling a Config flag flips only that context variable to False."""
    make_config("FEATURE_AWARDS", "off")
    result = feature_flags(None)
    assert result["feature_awards_enabled"] is False
    assert result["feature_jobs_enabled"] is True
    assert result["feature_events_calendar_enabled"] is True


@pytest.mark.django_db
def test_incident_report_url_blank_without_config():
    assert incident_report(None) == {"incident_report_url": ""}


@pytest.mark.django_db
def test_incident_report_url_strips_markup_and_entities(make_config):
    make_config("INCIDENT_REPORT_URL", "<p>https://forms.gle/abc?a=1&amp;b=2</p>")
    result = incident_report(None)
    assert result["incident_report_url"] == "https://forms.gle/abc?a=1&b=2"


@pytest.mark.django_db
def test_incident_report_url_rejects_non_http_scheme(make_config):
    make_config("INCIDENT_REPORT_URL", "javascript:alert(1)")
    assert incident_report(None)["incident_report_url"] == ""
