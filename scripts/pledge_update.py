import csv
import datetime
from django.forms.models import model_to_dict
from django.db.models import Q
from address.models import Address
from forms.models import Pledge, PledgeProcess
from chapters.models import Chapter, ChapterCurricula
from users.models import User


def run(*args):
    """
    python manage.py runscript pledge_update
    python manage.py runscript pledge_update --script-args import
    """
    if "import" not in args:
        with open("exports/pledge_update.csv", "w", newline="") as csvfile:
            header = False
            for pledge in Pledge.objects.all():
                pledge_dict = model_to_dict(pledge)
                pledge_dict.update({"process": pledge.process.get().id})
                if not header:
                    writer = csv.DictWriter(
                        csvfile, fieldnames=list(pledge_dict.keys())
                    )
                    writer.writeheader()
                    header = True
                print(pledge_dict)
                writer.writerow(pledge_dict)
        Pledge.objects.all().delete()
    else:
        with open("exports/pledge_update.csv", "r") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                print(f"Processing row: {row}")
                chapter = Chapter.objects.get(school=row["school_name"])
                major = ChapterCurricula.objects.get(id=row["major"])
                try:
                    address = Address.objects.get(id=row["address"])
                except Address.DoesNotExist:
                    address = None
                birth_date = datetime.datetime.strptime(row["birth_date"], "%Y-%m-%d")
                user, created = User.objects.filter(
                    Q(email=row["email_personal"]) | Q(email_school=row["email_school"])
                ).update_or_create(
                    defaults=dict(
                        chapter=chapter,
                        badge_number=User.next_pledge_number(),
                        major=major,
                        address=address,
                        first_name=row["first_name"],
                        middle_name=row["middle_name"],
                        last_name=row["last_name"],
                        title=row["title"],
                        suffix=row["suffix"],
                        nickname=row["nickname"],
                        email_school=row["email_school"],
                        email=row["email_personal"],
                        phone_number=row["phone_mobile"],
                        birth_date=birth_date,
                        graduation_year=row["grad_date_year"],
                    ),
                )
                created = datetime.datetime.strptime(
                    row["created"].split(".")[0].split("+")[0], "%Y-%m-%d %H:%M:%S"
                )  # 2020-04-26 20:49:47.210573+00:00
                Pledge(
                    id=row["id"],
                    user=user,
                    created=created,
                    signature=row["signature"],
                    parent_name=row["parent_name"],
                    birth_place=row["birth_place"],
                    other_degrees=row["other_degrees"],
                    relative_members=row["relative_members"],
                    other_greeks=row["other_greeks"],
                    other_tech=row["other_tech"],
                    other_frat=row["other_frat"],
                    other_college=row["other_college"],
                    explain_expelled_org=row["explain_expelled_org"],
                    explain_expelled_college=row["explain_expelled_college"],
                    explain_crime=row["explain_crime"],
                    loyalty=row["loyalty"],
                    not_honor=row["not_honor"],
                    accountable=row["accountable"],
                    life=row["life"],
                    unlawful=row["unlawful"],
                    unlawful_org=row["unlawful_org"],
                    brotherhood=row["brotherhood"],
                    engineering=row["engineering"],
                    engineering_grad=row["engineering_grad"],
                    payment=row["payment"],
                    attendance=row["attendance"],
                    harmless=row["harmless"],
                    alumni=row["alumni"],
                    honest=row["honest"],
                ).save()
                pledge = Pledge.objects.get(id=row["id"])
                pledge_process = PledgeProcess.objects.get(id=row["process"])
                pledge_process.pledges.add(pledge)
