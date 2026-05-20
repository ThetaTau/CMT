"""Tests for forms/templatetags/forms_custom_tags.py"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.django_db
def test_safe_url_file_with_valid_file():
    """safeURLfile returns an anchor tag for a file with a valid URL."""
    from thetatauCMT.forms.templatetags.forms_custom_tags import safeURLfile

    mock_file = MagicMock()
    mock_file.url = "/media/test.pdf"
    mock_file.name = "test.pdf"

    result = safeURLfile(mock_file)
    assert 'href="/media/test.pdf"' in result
    assert "test.pdf" in result
    assert "<a " in result


@pytest.mark.django_db
def test_safe_url_file_with_no_url_raises_value_error():
    """safeURLfile returns raw value when url raises ValueError."""
    from thetatauCMT.forms.templatetags.forms_custom_tags import safeURLfile

    mock_file = MagicMock()
    type(mock_file).url = property(lambda self: (_ for _ in ()).throw(ValueError("no file")))
    mock_file.name = "empty.pdf"

    result = safeURLfile(mock_file)
    assert result == mock_file


def test_safe_url_file_with_attribute_error():
    """safeURLfile returns raw value when url raises AttributeError."""
    from thetatauCMT.forms.templatetags.forms_custom_tags import safeURLfile

    result = safeURLfile("just a string")
    # A plain string has no .url attribute, AttributeError is caught
    assert result == "just a string"


def test_underscore_tag_pads_correctly():
    """underscore tag wraps value in <u> and pads with underscores."""
    from thetatauCMT.forms.templatetags.forms_custom_tags import underscore

    result = underscore("ABC", 10)
    assert "<u>ABC</u>" in result
    assert "_" in result


def test_underscore_tag_exact_length():
    """underscore tag with count == len(value) has no padding."""
    from thetatauCMT.forms.templatetags.forms_custom_tags import underscore

    result = underscore("ABC", 3)
    assert "<u>ABC</u>" in result
    # extra = 0, half_char = "" so no underscores in padding
    assert result == "<u>ABC</u>"
