# Generated by Django 2.2.12 on 2022-08-14 23:24

import ballots.models
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
            name="Ballot",
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
                    "sender",
                    models.CharField(
                        default="Grand Scribe", max_length=50, verbose_name="From"
                    ),
                ),
                ("slug", models.SlugField()),
                ("name", models.CharField(max_length=50)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("candidate_chapter", "Candidate Chapter Petition"),
                            ("chapter", "Chapter Petition"),
                            ("suspension", "Suspension"),
                            ("other", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "attachment",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=ballots.models.get_ballot_attachment_upload_path,
                    ),
                ),
                ("description", models.TextField()),
                ("due_date", models.DateField(default=ballots.models.return_date_time)),
                (
                    "voters",
                    ballots.models.MultiSelectField(
                        choices=[
                            ("all_chapters", "All Chapters"),
                            ("alumni programs director", "Alumni Programs Director"),
                            (
                                "candidate chapter director",
                                "Candidate Chapter Director",
                            ),
                            ("council delegate", "Council Delegate"),
                            ("expansion director", "Expansion Director"),
                            ("grand inner guard", "Grand Inner Guard"),
                            ("grand marshal", "Grand Marshal"),
                            ("grand outer guard", "Grand Outer Guard"),
                            ("grand regent", "Grand Regent"),
                            ("grand scribe", "Grand Scribe"),
                            ("grand treasurer", "Grand Treasurer"),
                            ("grand vice regent", "Grand Vice Regent"),
                            ("national director", "National Director"),
                            ("national officer", "National Officer"),
                            (
                                "national operations manager",
                                "National Operations Manager",
                            ),
                            (
                                "professional development director",
                                "Professional Development Director",
                            ),
                            ("regional director", "Regional Director"),
                            ("service director", "Service Director"),
                        ],
                        max_length=500,
                        verbose_name="Who is allowed to vote on this ballot?",
                    ),
                ),
            ],
            options={
                "unique_together": {("name", "due_date")},
            },
        ),
        migrations.CreateModel(
            name="BallotComplete",
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
                    "motion",
                    models.CharField(
                        choices=[
                            ("aye", "Aye"),
                            ("nay", "Nay"),
                            ("abstain", "Abstain"),
                            ("incomplete", "Incomplete"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("alumni programs director", "Alumni Programs Director"),
                            (
                                "candidate chapter director",
                                "Candidate Chapter Director",
                            ),
                            ("corresponding secretary", "Corresponding Secretary"),
                            ("council delegate", "Council Delegate"),
                            ("expansion director", "Expansion Director"),
                            ("grand inner guard", "Grand Inner Guard"),
                            ("grand marshal", "Grand Marshal"),
                            ("grand outer guard", "Grand Outer Guard"),
                            ("grand regent", "Grand Regent"),
                            ("grand scribe", "Grand Scribe"),
                            ("grand treasurer", "Grand Treasurer"),
                            ("grand vice regent", "Grand Vice Regent"),
                            ("national director", "National Director"),
                            ("national officer", "National Officer"),
                            (
                                "national operations manager",
                                "National Operations Manager",
                            ),
                            (
                                "professional development director",
                                "Professional Development Director",
                            ),
                            ("regent", "Regent"),
                            ("regional director", "Regional Director"),
                            ("scribe", "Scribe"),
                            ("service director", "Service Director"),
                            ("treasurer", "Treasurer"),
                            ("vice regent", "Vice Regent"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "ballot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="completed",
                        to="ballots.Ballot",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ballots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "ballot")},
            },
        ),
    ]
