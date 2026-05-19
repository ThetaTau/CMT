import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django

django.setup()

from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

user = UserFactory.create()
print("initial is_officer:", user.is_officer)
print("initial current_roles:", user.current_roles)
rc = UserRoleChangeFactory.create(user=user, current=True, officer="chapter")
user.refresh_from_db()
print("role change officer field:", rc.officer)
print("after current_roles:", user.current_roles)
print("after is_officer:", user.is_officer)
from thetatauCMT.users.models import User

CHAPTER_OFFICER = User.CHAPTER_OFFICER if hasattr(User, "CHAPTER_OFFICER") else None
print("CHAPTER_OFFICER:", CHAPTER_OFFICER)
print("chapter_officer():", user.chapter_officer())
