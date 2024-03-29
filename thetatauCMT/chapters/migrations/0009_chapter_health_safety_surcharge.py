# Generated by Django 2.2.12 on 2021-09-26 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chapters", "0008_auto_20210911_1625"),
    ]

    operations = [
        migrations.AddField(
            model_name="chapter",
            name="health_safety_surcharge",
            field=models.CharField(
                choices=[
                    (
                        "L1a",
                        "Between 51% and 75% of prior-year new members completed the online health and safety programming",
                    ),
                    (
                        "L1b",
                        "Between 26% and 50% of prior-year new members completed the online health and safety programming",
                    ),
                    (
                        "L1c",
                        "Between 0% and 25% of prior-year new members completed the online health and safety programming",
                    ),
                    (
                        "none",
                        ">75% of prior-year new members completed the online health and safety programming",
                    ),
                ],
                default="none",
                help_text="Surcharge for chapters not completing X% online health and safety programming",
                max_length=10,
            ),
        ),
    ]
