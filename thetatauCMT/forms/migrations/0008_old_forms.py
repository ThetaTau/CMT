# Generated by Django 2.0.3 on 2018-09-02 17:15
import os
import csv
import datetime
from django.db import migrations
from django.db import transaction
from django.db.utils import IntegrityError


def load_old_forms(apps, schema_editor):
    status = apps.get_model("forms", "StatusChange")
    depledge = apps.get_model("forms", "Depledge")
    init = apps.get_model("forms", "Initiation")
    badge = apps.get_model("forms", "Badge")
    guard = apps.get_model("forms", "Guard")
    user = apps.get_model("users", "User")
    chapter = apps.get_model("chapters", "Chapter")
    file_path = "secrets/20180902_INIT_COMBINED.csv"
    init_count = 0
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chapter_obj = chapter.objects.get(name=row['chapter'])
            user_id = f"{chapter_obj.greek}{row['roll']}"
            try:
                user_obj = user.objects.get(user_id=user_id)
            except user.DoesNotExist:
                try:
                    user_obj = user.objects.get(
                        chapter=chapter_obj,
                        badge_number=row['roll'])
                except user.DoesNotExist:
                    try:
                        user_obj = user.objects.get(
                            chapter=chapter_obj,
                            first_name=row['first'],
                            last_name=row['last'])
                    except user.DoesNotExist:
                        print(f"INIT User does not exist {row}")
                        continue
            date_graduation = datetime.datetime.strptime(row['date_graduation'], '%m/%d/%Y')
            created = datetime.datetime.strptime(row['created'].split(' ')[0], '%m/%d/%Y')
            date = datetime.datetime.strptime(row['date'], '%m/%d/%Y')
            badge_obj = badge.objects.get(code=row['badge'])
            guard_obj = None
            if row['guard']:
                guard_obj = guard.objects.get(code=row['guard'])
            init_obj = init(
                user=user_obj,
                created=created,
                date=date,
                roll=int(row['roll']),
                date_graduation=date_graduation,
                gpa=float(row['gpa']),
                test_a=int(float(row['test_a'])),
                test_b=int(float(row['test_b'])),
                badge=badge_obj,
                guard=guard_obj,
            )
            try:
                with transaction.atomic():
                    init_obj.save()
                    init_count += 1
            except IntegrityError as e:
                print("Initation ALREADY EXISTS", str(e))
    print(f"Add initiation count {init_count}")
    file_path = "secrets/20180902_DEPL_COMBINED.csv"
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chapter_obj = chapter.objects.get(name=row['chapter'])
            try:
                user_obj = user.objects.get(chapter=chapter_obj,
                                            first_name=row['first'],
                                            last_name=row['last'])
            except user.DoesNotExist:
                continue
            else:
                print(f"Depledge still existed, clearing {row}")
            created = datetime.datetime.strptime(row['created'].split(' ')[0], '%m/%d/%Y')
            date = datetime.datetime.strptime(row['date'], '%m/%d/%Y')
            depledge_obj = depledge(
                user=user_obj,
                created=created,
                date=date,
                reason=row['reason'],
            )
            try:
                with transaction.atomic():
                    depledge_obj.save()
            except IntegrityError as e:
                print("Depledge ALREADY EXISTS", str(e))
    file_path = "secrets/20180902_COOP_COMBINED.csv"
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                user_obj = user.objects.get(user_id=row['user_id'])
            except user.DoesNotExist:
                try:
                    user_obj = user.objects.get(badge_number=row['user_id'])
                except (user.DoesNotExist, ValueError):
                    try:
                        user_obj = user.objects.get(first_name=row['first'],
                                                    last_name=row['last'])
                    except user.DoesNotExist as e:
                        print(f"Depledge User does not exist {row}")
                        raise e
                    except user.MultipleObjectsReturned:
                        print(f"Multiple user found for COOP: {row}")
                        continue
            created = datetime.datetime.strptime(row['created'].split(' ')[0], '%m/%d/%Y')
            date_start = datetime.datetime.strptime(row['date_start'], '%m/%d/%Y')
            date_end = datetime.datetime.strptime(row['date_end'], '%m/%d/%Y')
            status_obj = status(
                created=created,
                user=user_obj,
                reason=row['reason'],
                date_start=date_start,
                date_end=date_end,
                miles=int(float(row['miles'])),
            )
            status_obj.save()
    file_path = "secrets/20180902_MSCR_COMBINED.csv"
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                user_obj = user.objects.get(user_id=row['user_id'])
            except user.DoesNotExist:
                try:
                    user_obj = user.objects.get(username=row['email'])
                except user.DoesNotExist:
                    try:
                        user_obj = user.objects.get(
                            badge_number=row['user_id'],
                            first_name=row['first'],
                            last_name=row['last']
                        )
                    except (user.DoesNotExist, ValueError):
                        try:
                            user_obj = user.objects.get(
                                first_name=row['first'],
                                last_name=row['last'])
                        except user.DoesNotExist:
                            print(f"User does not exist {row}")
                            continue
                    except user.MultipleObjectsReturned:
                        print(f"MSCR User returned multiple {row}")
            created = datetime.datetime.strptime(row['created'].split(' ')[0], '%m/%d/%Y')
            date_start = datetime.datetime.strptime(row['date_start'], '%m/%d/%Y')
            chapter_obj = None
            if row['new_school']:
                try:
                    chapter_obj = chapter.objects.get(school=row['new_school'])
                except chapter.DoesNotExist:
                    chapter_obj = None
            status_obj = status(
                created=created,
                user=user_obj,
                reason=row['reason'],
                date_start=date_start,
                degree=row['degree'],
                employer=row['employer'],
                new_school=chapter_obj,
            )
            status_obj.save()

def delete(apps, schema_editor):
    status = apps.get_model("forms", "StatusChange")
    status.objects.all().delete()
    depledge = apps.get_model("forms", "Depledge")
    depledge.objects.all().delete()
    init = apps.get_model("forms", "Initiation")
    init.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0007_auto_20180903_2130'),
    ]

    operations = [
        migrations.RunPython(load_old_forms, delete),
    ]