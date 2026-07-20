import pytest

from thetatauCMT.configs.models import Config


@pytest.fixture
def make_config():
    def _make(key, value, description="Test description"):
        config = Config(key=key, value=value, description=description)
        config.save()
        return config

    return _make


@pytest.mark.django_db
def test_config_get_value_returns_stripped_html(make_config):
    """get_value with clean=True strips HTML tags."""
    make_config("site_name", "<p>Hello <b>World</b></p>")
    result = Config.get_value("site_name", clean=True)
    assert result == "Hello World"


@pytest.mark.django_db
def test_config_get_value_returns_safe_html(make_config):
    """get_value with clean=False returns the raw HTML marked safe."""
    make_config("site_banner", "<p>Hello <b>World</b></p>")
    result = Config.get_value("site_banner", clean=False)
    assert "<b>World</b>" in str(result)


@pytest.mark.django_db
def test_config_get_value_missing_key_returns_empty():
    """get_value returns empty string for a nonexistent key."""
    result = Config.get_value("nonexistent_key_xyz")
    assert result == ""


@pytest.mark.django_db
def test_config_get_value_returns_latest_when_multiple(make_config):
    """When multiple Config entries share the same key, the last created is returned."""
    make_config("msg", "<p>First</p>")
    make_config("msg", "<p>Second</p>")
    result = Config.get_value("msg", clean=True)
    assert result == "Second"


@pytest.mark.django_db
def test_config_ordering(make_config):
    """Config ordering is by -modified (most recently modified first)."""
    make_config("key1", "<p>A</p>")
    c2 = make_config("key2", "<p>B</p>")
    configs = list(Config.objects.all())
    # Most recently modified should be first
    assert configs[0].pk == c2.pk


@pytest.mark.django_db
def test_config_str_creation(make_config):
    """Config can be created and its key is persisted."""
    config = make_config("my_key", "<p>value</p>", "A description")
    assert config.pk is not None
    assert config.key == "my_key"
    assert config.description == "A description"


@pytest.mark.django_db
def test_feature_enabled_defaults_true_when_missing():
    """A feature with no Config row is enabled by default."""
    assert Config.feature_enabled("FEATURE_MISSING") is True


@pytest.mark.django_db
def test_feature_enabled_respects_default_arg():
    """The default is used when no Config row exists."""
    assert Config.feature_enabled("FEATURE_MISSING", default=False) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    ["off", "OFF", "Off", "0", "false", "no", "disabled", "hide", "hidden", "<p>off</p>"],
)
def test_feature_enabled_off_values_disable(make_config, value):
    """Any recognized off token (case/HTML-insensitive) disables the feature."""
    make_config("FEATURE_X", value)
    assert Config.feature_enabled("FEATURE_X") is False


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["on", "ON", "yes", "enabled", "<p>on</p>", "1", "true"])
def test_feature_enabled_on_values_enable(make_config, value):
    """Non-off values keep the feature enabled."""
    make_config("FEATURE_X", value)
    assert Config.feature_enabled("FEATURE_X") is True


@pytest.mark.django_db
def test_feature_enabled_uses_latest_created(make_config):
    """The most recently created row for a key wins (toggle mechanism)."""
    make_config("FEATURE_X", "on")
    make_config("FEATURE_X", "off")
    assert Config.feature_enabled("FEATURE_X") is False


@pytest.mark.django_db
def test_feature_flags_fixture_loads_all_enabled():
    """The feature_flags fixture creates the three flags (auto pk), all enabled."""
    from django.core.management import call_command

    call_command("loaddata", "feature_flags", verbosity=0)
    for key in ("FEATURE_AWARDS", "FEATURE_JOBS", "FEATURE_EVENTS_CALENDAR"):
        row = Config.objects.filter(key=key).order_by("created").last()
        assert row is not None
        assert row.pk is not None
        assert Config.feature_enabled(key) is True
