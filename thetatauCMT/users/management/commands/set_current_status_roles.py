import datetime
from django.core.management import BaseCommand
from users.models import User
from core.models import TODAY_END


# python manage.py set_current_status_roles
class Command(BaseCommand):
    # Show this when the user types help
    help = "Set the current user status and roles"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        """
        We denormalized the status and roles field and now need to make sure they do not get out of sync
        primarily because roles end and away status can end as well
        I chose not to check UserRoleChange and UserStatusChange specifically
        because the end date can change greater than a week or so
        and the modified on those tables could be off as well. So we just check all users.
        """
        today = datetime.date.today().strftime("%A")
        override = options.get("override", False)
        if today != "Tuesday" and not override:
            print(f"Not today {today}")
            return
        users = User.objects.all().prefetch_related("status", "roles")
        total = users.count()
        print("Number of users", total)
        update_users = []
        for count, user in enumerate(users):
            if not ((count + 1) % 5000):
                print(f"Working on user {count+1}/{total}")
            status_update = False
            roles_update = False
            current_status = user.status.filter(
                start__lte=TODAY_END, end__gte=TODAY_END
            ).order_by("-start")
            if not current_status:
                # We will just take the last status user ever had
                current_status = user.status.order_by("-start")
            status = current_status.first()
            if not status:
                status = "alumni"
            else:
                status = status.status
            if user.current_status != status:
                print(
                    f"User {user} {count+1}/{total} updated previous status {user.current_status} new status {status}"
                )
                user.current_status = status
                status_update = True
            current_roles = (
                user.roles.filter(start__lte=TODAY_END, end__gte=TODAY_END)
                .order_by("-start")
                .values_list("role", flat=True)
            )
            already_set_roles = user.current_roles
            set_roles = set()
            if already_set_roles:
                set_roles = set(already_set_roles)
            roles = set()
            if current_roles:
                roles = set(current_roles)
            if roles != set_roles:
                print(
                    f"User {user} {count+1}/{total} updated previous roles {set_roles} new roles {roles}"
                )
                user.current_roles = list(roles)
                roles_update = True
            if roles_update or status_update:
                update_users.append(user)
        print(f"Updating {len(update_users)}: {update_users}")
        if update_users:
            User.objects.bulk_update(update_users, ["current_status", "current_roles"])
        current_officer = self.user.is_officer
        if current_officer:
            if self.user not in off_group.user_set.all():
                try:
                    off_group.user_set.add(self.user)
                except IntegrityError as e:
                    if "unique constraint" in str(e):
                        pass
            if self.user.is_national_officer():
                try:
                    nat_group.user_set.add(self.user)
                except IntegrityError as e:
                    if "unique constraint" in str(e):
                        pass
        else:
            self.user.groups.remove(off_group)
            self.user.groups.remove(nat_group)
            off_group.user_set.remove(self.user)
            nat_group.user_set.remove(self.user)
            self.user.save()
