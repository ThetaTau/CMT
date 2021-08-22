import os
from django.db.models import Q
from django.core.management import BaseCommand
from csv import DictReader
from users.models import User


# python manage.py badge_fixes secrets\ld_badgefix.csv -test
class Command(BaseCommand):
    # Show this when the user types help
    help = (
        "Command to fix badge numbers for members. \n"
        "First row should be: "
        "    email, correct\n"
        "Will attempt to find by email then current badge number"
    )

    def add_arguments(self, parser):
        parser.add_argument("file_path", nargs=1, type=str)
        parser.add_argument("-test", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        file_path = options["file_path"][0]
        if not os.path.exists(file_path):
            print(f"{file_path} does not exist")
            return
        test = options.get("test", False)
        print(f"Test mode {test}")
        with open(file_path, "r") as csv_file:
            reader = DictReader(csv_file)
            updated_users = []
            offset_users = []
            start = 80_000
            for count, row in enumerate(reader):
                print(row)
                email = row["email"].strip()
                # try:
                user = User.objects.get(
                    Q(email__iexact=email) | Q(email_school__iexact=email)
                )
                offset = start + count
                badge_number = row["correct"]
                chapter = user.chapter
                user_id = f"{chapter.greek}{badge_number}"
                user_id_offset = f"{chapter.greek}{offset}"
                updated_users.append(
                    {"id": user.id, "badge_number": badge_number, "user_id": user_id}
                )
                offset_users.append(
                    {"id": user.id, "badge_number": offset, "user_id": user_id_offset}
                )
        if not test:
            User.objects.bulk_update(
                [User(**kv) for kv in offset_users],
                [
                    "badge_number",
                    "user_id",
                ],
            )
            # After the bulk update, all remaining user_ids should not conflict
            new_ids = [new["user_id"] for new in updated_users]
            conflict_users = User.objects.filter(user_id__in=new_ids)
            nl = "\n"  # can't have backslashes in f-strings
            print(
                f"Conflicting users:\n {nl.join(conflict_users.values_list('name', 'email'))}"
            )
            start = 90_000
            conflict_users_update = [
                {
                    "id": user.id,
                    "badge_number": start + count,
                    "user_id": f"{user.chapter.greek}{start + count}",
                }
                for count, user in enumerate(conflict_users)
            ]

            User.objects.bulk_update(
                [User(**kv) for kv in conflict_users_update],
                [
                    "badge_number",
                    "user_id",
                ],
            )
            User.objects.bulk_update(
                [User(**kv) for kv in updated_users],
                [
                    "badge_number",
                    "user_id",
                ],
            )
