import pytest


@pytest.mark.django_db
def test_get_absolute_url(tp):
    user = tp.make_user()
    assert user.get_absolute_url() == "/users/myinfo/"


@pytest.mark.django_db
def test__str__(tp):
    user = tp.make_user()
    user.name = "Test User"
    user.save(update_fields=["name"])
    assert str(user) == "Test User"
