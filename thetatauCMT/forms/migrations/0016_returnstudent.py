# Generated by Django 2.2.12 on 2020-11-08 05:54

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("viewflow", "0008_jsonfield_and_artifact"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("forms", "0015_auto_20201022_1954"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReturnStudent",
            fields=[
                (
                    "process_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="viewflow.Process",
                    ),
                ),
                (
                    "reason",
                    models.TextField(
                        verbose_name="Reasons member requests transfer to student member status."
                    ),
                ),
                (
                    "financial",
                    models.BooleanField(
                        default=False,
                        verbose_name="I understand that semiannual dues obligation for the current semester\n        must be met if student member status\n        is resumed on or before the semiannual dues deadline (November 1/March 15).",
                    ),
                ),
                (
                    "debt",
                    models.BooleanField(
                        default=False,
                        verbose_name="This member has paid previous fraternity debt to the chapter.",
                    ),
                ),
                (
                    "approved_exec",
                    models.BooleanField(
                        default=False, verbose_name="Executive Director Approved"
                    ),
                ),
                (
                    "exec_comments",
                    models.TextField(
                        blank=True, verbose_name="If rejecting, please explain why."
                    ),
                ),
                (
                    "vote",
                    models.BooleanField(
                        default=False,
                        verbose_name="The status change for the member was approved by a four-fifths favorable vote of the chapter.",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="return_form",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("viewflow.process",),
        ),
    ]
