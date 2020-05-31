from test_plus.test import TestCase


def test_get_absolute_url(tp):
    expected_url = "/users/testuser/"
    user = tp.make_user()
    reversed_url = user.get_absolute_url()
    assert expected_url == reversed_url


def test__str__(tp):
    user = tp.make_user()
    assert "testuser" == user.__str__()
