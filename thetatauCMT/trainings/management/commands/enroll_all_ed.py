from django.core.management import BaseCommand

from thetatauCMT.trainings.models import Training
from thetatauCMT.users.models import User


# python manage.py enroll_all_ed
class Command(BaseCommand):
    help = "Enroll every active member in the configured Open edX (ed.thetatau.org) course run(s)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process the first N users (useful for a test run).",
        )

    def handle(self, *args, **options):
        # One token for the whole run; the app owner must be Open edX global staff.
        header = Training._ed_authenticate_header()
        users = list(User.objects.filter(is_active=True).exclude(email="").order_by("id"))
        limit = options.get("limit")
        if limit:
            users = users[:limit]
        total = len(users)
        enrolled = pending = errored = 0
        for index, user in enumerate(users, start=1):
            results = Training.enroll_user_ed(user, header=header)
            statuses = {status for _course, status, _msg in results}
            if "error" in statuses:
                errored += 1
            elif statuses == {"enrolled"}:
                enrolled += 1
            else:
                pending += 1
            self.stdout.write(f"[{index}/{total}] {user.email}: {', '.join(sorted(statuses))}")
        self.stdout.write(
            self.style.SUCCESS(f"Done. enrolled={enrolled} pending={pending} errored={errored} total={total}")
        )
