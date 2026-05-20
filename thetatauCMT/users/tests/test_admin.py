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
