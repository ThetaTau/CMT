# Generated by Django 2.2.12 on 2021-09-11 23:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0003_auto_20210907_1944"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="raised",
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text="How many philanthropy funds were raised at this event?",
                max_digits=10,
            ),
        ),
    ]