# Generated by Django 2.2.12 on 2022-02-17 03:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0019_auto_20220101_1355"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="charter",
            field=models.BooleanField(default=False, help_text="Charter member"),
        ),
        migrations.AlterField(
            model_name="userstatuschange",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "active"),
                    ("activepend", "active pending"),
                    ("advisor", "advisor"),
                    ("alumni", "alumni"),
                    ("alumnipend", "alumni pending"),
                    ("away", "away"),
                    ("deceased", "deceased"),
                    ("depledge", "depledge"),
                    ("expelled", "expelled"),
                    ("friend", "friend"),
                    ("nonmember", "nonmember"),
                    ("probation", "probation"),
                    ("pnm", "prospective"),
                    ("resigned", "resigned"),
                    ("resignedCC", "resignedCC"),
                    ("suspended", "suspended"),
                ],
                max_length=10,
            ),
        ),
    ]