# Generated by Django 2.2.12 on 2021-08-21 23:23

import core.models
from django.db import migrations, models
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_auto_20210809_1008"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deceased_changed",
            field=model_utils.fields.MonitorField(
                default=core.models.forever, monitor="deceased"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="deceased_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]