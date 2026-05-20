"""Tests for users/templatetags/custom_tags.py"""

from unittest.mock import MagicMock

import pytest


def test_lookup_filter_with_dict():
    """lookup filter returns value from dict by key."""
    from thetatauCMT.users.templatetags.custom_tags import lookup

    d = {"foo": "bar", "baz": 42}
    assert lookup(d, "foo") == "bar"
    assert lookup(d, "baz") == 42


def test_lookup_filter_with_object():
    """lookup filter returns attribute from object."""
    from thetatauCMT.users.templatetags.custom_tags import lookup

    obj = MagicMock()
    obj.name = "test_name"
    result = lookup(obj, "name")
    assert result == "test_name"


def test_split_filter():
    """split filter splits string on given key."""
    from thetatauCMT.users.templatetags.custom_tags import split

    result = split("hello world foo", " ")
    assert result == ["hello", "world", "foo"]


def test_split_filter_comma():
    """split filter works with comma separator."""
    from thetatauCMT.users.templatetags.custom_tags import split

    result = split("a,b,c", ",")
    assert result == ["a", "b", "c"]


@pytest.mark.django_db
def test_get_fields_returns_list_of_tuples(auto_login_user):
    """get_fields returns list of (verbose_name, value) tuples for model instance."""
    from thetatauCMT.users.templatetags.custom_tags import get_fields

    _, user = auto_login_user()
    fields = get_fields(user)
    assert isinstance(fields, list)
    # Should have multiple fields
    assert len(fields) > 0
    for item in fields:
        assert len(item) == 2


@pytest.mark.django_db
def test_user_alter_form_no_request():
    """user_alter_form returns None when no request in context."""
    from thetatauCMT.users.templatetags.custom_tags import user_alter_form

    result = user_alter_form({})
    assert result is None


@pytest.mark.django_db
def test_user_alter_form_anonymous_user(rf):
    """user_alter_form returns None for anonymous user."""
    from django.contrib.auth.models import AnonymousUser

    from thetatauCMT.users.templatetags.custom_tags import user_alter_form

    request = rf.get("/")
    request.user = AnonymousUser()
    result = user_alter_form({"request": request})
    assert result is None


@pytest.mark.django_db
def test_user_alter_form_non_national_officer(auto_login_user):
    """user_alter_form returns None for non-national-officer user."""
    from thetatauCMT.users.templatetags.custom_tags import user_alter_form

    client, user = auto_login_user()
    # Build a mock request with a regular user
    request = MagicMock()
    request.user = user
    result = user_alter_form({"request": request})
    assert result is None
