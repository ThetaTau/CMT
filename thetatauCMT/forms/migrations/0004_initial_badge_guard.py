# Generated by Django 2.0.3 on 2018-08-30 00:40
import os
import csv
from django.db import migrations


def add_badge_guard(apps, schema_editor):
    badge = apps.get_model("forms", "Badge")
    guard = apps.get_model("forms", "Guard")
    badge.objects.all().delete()
    guard.objects.all().delete()
    with open(f'{os.path.split(__file__)[0]}/JewelryPriceList.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['type'] == 'Badge':
                badge_obj = badge(
                    name=row['name'],
                    code=row['code'],
                    description=row['description'],
                    cost=row['cost']
                )
                badge_obj.save()
            if row['type'] == 'Guard':
                guard_obj = guard(
                    name=row['name'],
                    code=row['code'],
                    description=row['description'],
                    cost=row['cost'],
                    letters=row['letters']
                )
                guard_obj.save()


def delete(apps, schema_editor):
    badge = apps.get_model("forms", "Badge")
    badge.objects.all().delete()
    guard = apps.get_model("forms", "Guard")
    guard.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0003_riskmanagement'),
    ]

    operations = [
        migrations.RunPython(add_badge_guard, delete),
    ]
