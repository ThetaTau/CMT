"""
Grant, revoke or list a member's roles from the command line.

Superusers are seeded with ``current_roles = ["grand regent"]`` by
``CustomUserManager._give_superuser_natoff_roles`` and have no backing
``UserRoleChange`` row, so the denormalized array has to be edited directly as
well as the role rows.

    python manage.py user_role test@gmail.com
    python manage.py user_role test@gmail.com --add "grand scribe" --months 12
    python manage.py user_role test@gmail.com --remove "grand regent"
"""

import datetime

from django.core.management import BaseCommand, CommandError
from django.db.models import Q

from core.models import ALL_ROLES, TODAY_END
from thetatauCMT.users.models import User, UserRoleChange


class Command(BaseCommand):
    help = "Grant, revoke or list the roles held by a member."

    def add_arguments(self, parser):
        parser.add_argument("user", type=str, help="Username or email address.")
        parser.add_argument("--add", type=str, help="Role to grant, e.g. 'grand regent'.")
        parser.add_argument("--remove", type=str, help="Role to revoke.")
        parser.add_argument("--months", type=int, default=12, help="Term length for --add. Default 12.")

    def handle(self, *args, **options):
        identifier = options["user"]
        user = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
        if user is None:
            raise CommandError(f"No user matches {identifier}")

        add_role = options.get("add")
        remove_role = options.get("remove")
        for role in (add_role, remove_role):
            if role and role not in ALL_ROLES:
                raise CommandError(f"Unknown role '{role}'. Valid roles: {', '.join(ALL_ROLES)}")

        if add_role:
            self.grant(user, add_role, options["months"])
        if remove_role:
            self.revoke(user, remove_role)

        user.refresh_from_db()
        self.stdout.write(f"{user} ({user.username}) roles: {user.current_roles or []}")
        self.stdout.write(f"  groups: {list(user.groups.values_list('name', flat=True))}")
        for role_change in user.roles.order_by("-end"):
            self.stdout.write(f"  {role_change.role}: {role_change.start} to {role_change.end}")

    def grant(self, user, role, months):
        today = datetime.date.today()
        existing = user.roles.filter(role=role, start__lte=TODAY_END, end__gte=TODAY_END).first()
        if existing:
            self.stdout.write(f"{user} already holds '{role}' until {existing.end}")
            return
        # UserRoleChange.save() maintains current_roles and the officer/natoff groups.
        UserRoleChange(user=user, role=role, start=today, end=today + datetime.timedelta(days=30 * months)).save()
        self.stdout.write(f"Granted '{role}' to {user} for {months} month(s)")

    def revoke(self, user, role):
        ended = 0
        for role_change in user.roles.filter(role=role, end__gte=TODAY_END):
            role_change.end = datetime.date.today() - datetime.timedelta(days=1)
            role_change.save()
            ended += 1
        user.refresh_from_db()
        current_roles = list(user.current_roles or [])
        if role in current_roles:
            # Seeded superuser roles have no UserRoleChange row to end.
            current_roles.remove(role)
            user.current_roles = current_roles
            user.save(update_fields=["current_roles"])
        self.stdout.write(f"Revoked '{role}' from {user} ({ended} term(s) ended)")
