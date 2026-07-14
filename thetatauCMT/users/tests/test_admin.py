import pytest
from test_plus.test import TestCase

from thetatauCMT.users.admin import MyUserCreationForm


class TestMyUserCreationForm(TestCase):
    def setUp(self):
        self.user = self.make_user("notalamode", "notalamodespassword")

    def test_clean_username_success(self):
        # Form is valid when required fields (chapter, badge_number) are provided
        form = MyUserCreationForm(
            {
                "chapter": self.user.chapter_id,
                "badge_number": 12345,
            }
        )
        valid = form.is_valid()
        self.assertTrue(valid)

    def test_clean_username_false(self):
        # Form is invalid when required chapter field is missing
        form = MyUserCreationForm({})
        valid = form.is_valid()
        self.assertFalse(valid)
        self.assertIn("chapter", form.errors)


# ---------------------------------------------------------------------------
# MyUserAdmin "Send selected users to MailerLite" action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_send_to_mailerlite_action_delegates_when_configured():
    from unittest import mock

    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory

    from thetatauCMT.users.admin import MyUserAdmin
    from thetatauCMT.users.models import User

    admin_instance = MyUserAdmin(User, AdminSite())
    admin_instance.message_user = mock.MagicMock()
    request = RequestFactory().post("/admin/users/user/")
    summary = {"added": 2, "exists": 1, "skipped": 0, "errors": 0}
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailerlite_api.is_configured",
            return_value=True,
        ),
        mock.patch(
            "thetatauCMT.email_tracking.mailerlite_sync.send_users",
            return_value=summary,
        ) as send,
    ):
        admin_instance.send_to_mailerlite(request, User.objects.none())
    send.assert_called_once()
    admin_instance.message_user.assert_called_once()
    assert "added 2" in admin_instance.message_user.call_args.args[1]


@pytest.mark.django_db
def test_send_to_mailerlite_action_guards_when_unconfigured():
    from unittest import mock

    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory

    from thetatauCMT.users.admin import MyUserAdmin
    from thetatauCMT.users.models import User

    admin_instance = MyUserAdmin(User, AdminSite())
    admin_instance.message_user = mock.MagicMock()
    request = RequestFactory().post("/admin/users/user/")
    with (
        mock.patch(
            "thetatauCMT.email_tracking.mailerlite_api.is_configured",
            return_value=False,
        ),
        mock.patch("thetatauCMT.email_tracking.mailerlite_sync.send_users") as send,
    ):
        admin_instance.send_to_mailerlite(request, User.objects.none())
    send.assert_not_called()
    admin_instance.message_user.assert_called_once()
