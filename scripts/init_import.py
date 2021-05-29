import csv
import datetime
from django.db.models import Q
from users.models import User, UserStatusChange, forever
from forms.models import Initiation


def run(*args):
    """
    Constituent ID
    Name
    Email address
    Constituent codes
    ChapRoll
    Chapter
    Chapter Name
    Initiation Date

    python manage.py runscript init_import --script-args "database_backups/Initiation Dates 20210512.csv"
    """
    path = args[0]
    with open(path, encoding="ISO-8859-1") as f:
        reader = csv.DictReader(f)
        # Some users can't be found, need to update manually
        manual = []
        for count, member in enumerate(reader):
            user_id = member["Constituent ID"]
            email = member["Email address"]
            print(f"Processing {count + 1}/39339 {email} {member['Name']}")
            init_date = member["Initiation Date"]
            if init_date not in ["", "No date"]:
                try:
                    if len(email) > 2:
                        # email should match first as the id can be off
                        try:
                            user = User.objects.get(
                                Q(email__iexact=email) | Q(email_school__iexact=email)
                            )
                        except User.DoesNotExist:
                            user = User.objects.get(Q(user_id__iexact=user_id))
                    else:
                        user = User.objects.get(Q(user_id__iexact=user_id))
                except User.DoesNotExist:
                    print("     !!!! User does not exist", (user_id, email, init_date))
                    manual.append((user_id, email, init_date))
                    continue
            else:
                print(f"     No date: {user_id}")
                continue
            init_date = datetime.datetime.strptime(init_date, "%m/%d/%Y").date()
            if hasattr(user, "initiation"):
                initiation = user.initiation
                if initiation.date != init_date:
                    initiation.date = init_date
                    initiation.save(status_update=False)
            else:
                initiation = Initiation(
                    user=user,
                    chapter=user.chapter,
                    date_graduation=datetime.date(user.graduation_year, 1, 1),
                    date=init_date,
                    gpa=0,
                    test_a=0,
                    test_b=0,
                    roll=user.badge_number,
                )
                initiation.save(status_update=False)
            pledge = user.status.filter(status="pnm").first()
            pledge_start = init_date - datetime.timedelta(days=30 * 4)
            if pledge:
                pledge.start = pledge_start
                pledge.end = init_date
                pledge.save()
            else:
                UserStatusChange(
                    user=user, status="pnm", start=pledge_start, end=init_date,
                ).save()
            active = user.status.filter(status="active").first()
            alumni = user.status.filter(status="alumni").last()
            if not alumni:
                # if no alumni status, then member is still active?
                status_end = forever()
            else:
                status_end = alumni.start
            if active:
                active.start = init_date
                active.end = status_end
                active.save()
            else:
                UserStatusChange(
                    user=user, status="active", start=init_date, end=status_end,
                ).save()
    print("Manually update", *manual, sep="\n")
    fields = ["User ID", "Email", "Init Date"]
    with open(r"database_backups/init_date_manual.csv", "w", newline="") as f:
        write = csv.writer(f)
        write.writerow(fields)
        write.writerows(manual)
