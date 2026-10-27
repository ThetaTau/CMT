from collections import defaultdict

from django.core.management import BaseCommand

from thetatauCMT.trainings.models import EdCourse, Training
from thetatauCMT.users.models import User


# python manage.py enroll_all_ed
class Command(BaseCommand):
    help = (
        "Apply the Open edX course rules (Trainings > Open edX courses): enroll every active member in the "
        "every-member courses and current role holders in their role courses."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process the first N users (useful for a test run).",
        )
        parser.add_argument(
            "--course",
            action="append",
            dest="courses",
            help="Only this course run key, e.g. course-v1:ThetaTau+TT101+intro (repeatable).",
        )

    def handle(self, *args, **options):
        members = User.objects.filter(is_active=True).exclude(email="")
        courses = EdCourse.objects.filter(active=True)
        if options.get("courses"):
            courses = courses.filter(course_id__in=options["courses"])
        courses_by_user = defaultdict(list)
        for course in courses:
            if course.assign_to_all_members:
                user_ids = members.values_list("id", flat=True)
            elif course.assign_to_roles:
                user_ids = members.filter(current_roles__overlap=course.assign_to_roles).values_list("id", flat=True)
            else:
                continue
            for user_id in user_ids:
                courses_by_user[user_id].append(course.course_id)

        users = [user for user in members.order_by("id") if user.id in courses_by_user]
        limit = options.get("limit")
        if limit:
            users = users[:limit]
        total = len(users)
        if not total:
            self.stdout.write("Nobody to enroll: no active Open edX course matches any member.")
            return
        # One token for the whole run; the app owner must be Open edX global staff.
        header = Training._ed_authenticate_header()
        enrolled = pending = errored = 0
        for index, user in enumerate(users, start=1):
            results = Training.enroll_user_ed(user, courses=courses_by_user[user.id], header=header)
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
