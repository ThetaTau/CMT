# Generated by Django 2.2.12 on 2021-09-07 23:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="raised",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
    ]
