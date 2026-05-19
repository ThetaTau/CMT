"""Tests for users/resources.py."""

from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from thetatauCMT.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_user_status_change_resource_before_import_row():
    """before_import_row looks up user by email and sets 'user' in row."""
    from thetatauCMT.users.resources import UserStatusChangeResource

    user = UserFactory.create()
    resource = UserStatusChangeResource()
    row = {"user__email": user.email, "status": "active", "start": "", "end": ""}
    resource.before_import_row(row)
    assert row["user"] == user.id


@pytest.mark.django_db
def test_user_resource_before_import_row_strips_email():
    """before_import_row strips whitespace from email field."""
    from thetatauCMT.users.resources import UserResource

    resource = UserResource()
    row = {"email": "  test@example.com  ", "name": "Test User"}
    resource.before_import_row(row)
    assert row["email"] == "test@example.com"


@pytest.mark.django_db
def test_user_resource_before_import_row_no_email():
    """before_import_row does not crash when email is absent from row."""
    from thetatauCMT.users.resources import UserResource

    resource = UserResource()
    row = {"name": "Test User"}
    resource.before_import_row(row)
    assert "email" not in row


@pytest.mark.django_db
def test_user_resource_get_instance_by_email():
    """get_instance returns user when found by email."""
    from thetatauCMT.users.resources import UserResource

    user = UserFactory.create()
    resource = UserResource()

    # Build a fake instance_loader
    mock_loader = MagicMock()
    mock_loader.get_queryset.return_value = type(user).objects.all()

    row = {"email": user.email}
    result = resource.get_instance(mock_loader, row)
    assert result is not None
    assert result.pk == user.pk


@pytest.mark.django_db
def test_user_resource_get_instance_not_found():
    """get_instance returns None when user is not found."""
    from thetatauCMT.users.models import User
    from thetatauCMT.users.resources import UserResource

    resource = UserResource()
    mock_loader = MagicMock()
    mock_loader.get_queryset.return_value = User.objects.none()

    row = {"email": "nonexistent@example.com"}
    result = resource.get_instance(mock_loader, row)
    assert result is None


@pytest.mark.django_db
def test_user_resource_get_instance_multiple_found_raises():
    """get_instance raises ValidationError when multiple users match."""
    from thetatauCMT.users.models import User
    from thetatauCMT.users.resources import UserResource

    user1 = UserFactory.create()
    user2 = UserFactory.create()
    resource = UserResource()

    # Use a queryset that will cause MultipleObjectsReturned by patching
    mock_loader = MagicMock()

    class RaisingQS:
        def get(self, *args, **kwargs):
            raise User.MultipleObjectsReturned("multiple")

    mock_loader.get_queryset.return_value = RaisingQS()

    row = {"email": "test@example.com"}
    with pytest.raises(ValidationError):
        resource.get_instance(mock_loader, row)


@pytest.mark.django_db
def test_user_resource_init_instance_raises_with_id_and_email():
    """init_instance raises ValidationError with id and email in message."""
    from thetatauCMT.users.resources import UserResource

    resource = UserResource()
    row = {"id": "123", "email": "missing@example.com"}
    with pytest.raises(ValidationError) as exc_info:
        resource.init_instance(row)
    error_str = str(exc_info.value)
    assert "id=123" in error_str or "missing@example.com" in error_str


@pytest.mark.django_db
def test_user_resource_get_instance_by_id():
    """get_instance returns user when found by id."""
    from thetatauCMT.users.resources import UserResource

    user = UserFactory.create()
    resource = UserResource()

    mock_loader = MagicMock()
    mock_loader.get_queryset.return_value = type(user).objects.all()

    row = {"id": str(user.pk)}
    result = resource.get_instance(mock_loader, row)
    assert result is not None
    assert result.pk == user.pk
