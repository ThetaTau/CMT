from django.core.management import BaseCommand
file_path = r"secrets/natoff.csv"
from csv import DictReader
from django.contrib.auth.models import Group, Permission
# from django.contrib.contenttypes.models import ContentType
from users.models import User
# ct = ContentType.objects.get_for_model(User)
# permission = Permission.objects.create(
#     codename='can_add_project', name='Can add project',
#     content_type=ct)
# new_group.permissions.add(permission)


# The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Add users to natoff and officer groups"

    # A command must define handle()
    def handle(self, *args, **options):
        nat_group, created = Group.objects.get_or_create(name='natoff')
        off_group, created = Group.objects.get_or_create(name='officer')
        with open(file_path, 'r') as csv_file:
            reader = DictReader(csv_file)
            for row in reader:
                # print(row)
                try:
                    user = User.objects.get(email=row["Email"])
                except User.DoesNotExist:
                    user = None
                if user is not None:
                    off_group.user_set.add(user)
                    nat_group.user_set.add(user)
                    continue
                try:
                    user = User.objects.get(
                        first_name=row["First Name"],
                        last_name=row["Last Name"])
                except User.DoesNotExist:
                    user = None
                if user is not None:
                    off_group.user_set.add(user)
                    nat_group.user_set.add(user)
                    continue
                try:
                    user = User.objects.get(
                        last_name=row["Last Name"])
                except User.DoesNotExist:
                    user = None
                except User.MultipleObjectsReturned:
                    user = None
                    users = User.objects.filter(last_name=row["Last Name"])
                    print(users)
                if user is not None:
                    off_group.user_set.add(user)
                    nat_group.user_set.add(user)
                    continue
                print("User not found", row)
        all_users = User.objects.all()
        for user in all_users:
            if user.is_chapter_officer():
                off_group.user_set.add(user)
