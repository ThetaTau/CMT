# Generated by Django 2.2.12 on 2022-01-21 01:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DepledgeSurvey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("volunteer", "Voluntarily decided not to continue"),
                            ("time", "Unable/unwilling to meet time commitment"),
                            ("grades", "Unable/unwilling to meet academic requirement"),
                            (
                                "financial",
                                "Unable/unwilling to meet financial commitment",
                            ),
                            ("violation", "Policy/Procedure Violation"),
                            ("vote", "Poor fit with the chapter/candidate chapter"),
                            ("withdrew", "Withdrew from Engineering/University"),
                            ("transfer", "Transferring to another school"),
                            ("other", "Other"),
                        ],
                        max_length=10,
                        verbose_name="What was the reason for your depledging?",
                    ),
                ),
                (
                    "reason_other",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Other reason for depledging",
                    ),
                ),
                (
                    "decided",
                    models.CharField(
                        choices=[
                            ("me", "Decided by me"),
                            ("chapter", "Decided by the chapter"),
                            ("other", "Other"),
                        ],
                        max_length=10,
                        verbose_name="How was your depledging decided?",
                    ),
                ),
                (
                    "decided_other",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Decided in another way",
                    ),
                ),
                (
                    "enjoyed",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Was there a part of the education program that you particularly enjoyed or found helpful?",
                    ),
                ),
                (
                    "improve",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Do you have any suggestions to improve the education program?",
                    ),
                ),
                (
                    "extra_notes",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Is there anything else you'd like to share?",
                    ),
                ),
                (
                    "contact",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Would you like someone to contact you?",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="depledge_survey",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]