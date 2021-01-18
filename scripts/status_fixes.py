from datetime import datetime, timedelta
from django.db.models import Q, F
from users.models import User
from users.models import UserStatusChange


def run():
    """
    python manage.py runscript status_fixes
    For every user should have at least 3 status, pledge, active, alumn
        More status possible eg. pledge->active-->away-->active-->alumn-->active-->alumn
    No status should overlap
    Ideally not have same status next to each other. eg. active --> active
        These would be combined
    """
    # First issue, many dates start/end were flipped, need to fix
    flipped_dates = UserStatusChange.objects.filter(Q(start__gt=F("end")))
    print("Fix flipped dates start ", flipped_dates.count())
    for flipped_date in flipped_dates:
        start, end = flipped_date.start, flipped_date.end
        flipped_date.start = end
        flipped_date.end = start
    UserStatusChange.objects.bulk_update(flipped_dates, ["start", "end"])
    print("Fix flipped dates end")
    users = User.objects.all()
    total = users.count()
    for count, user in enumerate(users):
        print(f"{count+1}/{total}")
        user_statuses = user.status.all().order_by("start")
        print("    User statuses: ", user, user_statuses)
        pledge = user_statuses.filter(status="pnm").first()
        active = user_statuses.filter(status="active").first()
        alumni = user_statuses.filter(status="alumni").first()
        if not active:
            # No active status,
            #   if alumni should have active
            #   if pledge check init
            if not alumni and not pledge:
                # nothing, could be expelled, nonmember, friend, advisor
                other_status = user_statuses.filter(
                    status__in=["expelled", "nonmember", "friend", "advisor"]
                )
                if not other_status:
                    print("        no status, need active ", user.graduation_year)
                    start = datetime(user.graduation_year, 6, 1)
                    user.set_current_status(
                        "active", start=start - timedelta(365 * 3.5), end=start
                    )
                    user.set_current_status("alumni", start=start)
            if alumni and not pledge:
                print("        need active from alumni", alumni.start)
                other_status = user_statuses.filter(status__in=["expelled"])
                if not other_status:
                    start = alumni.start
                    user.set_current_status(
                        "active", start=start - timedelta(365 * 3.5), end=start
                    )
            if pledge:
                # there is no alumni so the current status should be active
                if hasattr(user, "initiation"):
                    start = user.initiation.date
                    print("        need active from init", start)
                    user.set_current_status(
                        "active", start=start,
                    )
                else:
                    print("        not initiated yet or depledged")
            active = user.status.filter(status="active").order_by("start").first()
        if not pledge and active:
            start = active.start
            print("        need pledge ", start)
            user.set_current_status(
                "pnm", start=start - timedelta(365 * 0.5), end=start,
            )
        if not alumni and active:
            graduate = user.status_changes.filter(reason="graduate").first()
            if graduate:
                start = graduate.date_start
                print("        need alumni ", start)
                user.set_current_status(
                    "alumni", start=start,
                )
            else:
                print("        not graduated")
        # Need to handle duplicates/overlaps
        #   Dates overlap not just within a status, but across statuses
        # each status the end <= start of next status
        user_statuses = list(user.status.all().order_by("start"))
        for ind, user_status in enumerate(user_statuses[:-1]):
            next_status = user_statuses[ind + 1]
            if user_status.status == "alumni" and next_status.status == "pnm":
                # odd issue where alumni status was added before pnm
                user_status.delete()
                continue
            if user_status.status == next_status.status:
                # if two status in row the same, other status should absorb
                print("            Absorb status, new start: ", user_status.start)
                next_status.start = user_status.start
                next_status.save()
                user_status.delete()
                continue
            if user_status.end > next_status.start:
                print("            Update status: ", user_status, next_status)
                user_status.end = next_status.start
                user_status.save()
