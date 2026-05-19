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
    c1 = make_config("key1", "<p>A</p>")
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
