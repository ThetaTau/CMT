# Generated by Django 2.2.12 on 2022-06-18 18:59

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import forms.models


class Migration(migrations.Migration):

    dependencies = [
        ("viewflow", "0008_jsonfield_and_artifact"),
        ("chapters", "0011_chapter_extra_approval"),
        ("forms", "0028_auto_20220216_2021"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChapterEducation",
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
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "report",
                    models.FileField(
                        upload_to=forms.models.get_chapter_education_upload_path
                    ),
                ),
                ("program_date", models.DateField(default=django.utils.timezone.now)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("alcohol_drugs", "Alcohol and Drug Awareness"),
                            ("harassment", "Anti-Harassment"),
                            ("mental", "Mental Health Recognition"),
                        ],
                        max_length=20,
                        verbose_name="Program category",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="facilitator first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="facilitator last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        verbose_name="facilitator email address",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("mr", "Mr."),
                            ("miss", "Miss"),
                            ("ms", "Ms"),
                            ("mrs", "Mrs"),
                            ("mx", "Mx"),
                            ("none", ""),
                        ],
                        max_length=5,
                        verbose_name="facilitator title",
                    ),
                ),
                (
                    "phone_number",
                    models.CharField(
                        blank=True,
                        help_text="Format: 9999999999 no spaces, dashes, etc.",
                        max_length=17,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
                                regex="^\\+?1?\\d{9,15}$",
                            )
                        ],
                        verbose_name="facilitator phone number",
                    ),
                ),
                (
                    "approval",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("revisions", "Revisions needed"),
                            ("denied", "Denied"),
                            ("not_reviewed", "Not Reviewed"),
                        ],
                        default="not_reviewed",
                        max_length=20,
                        verbose_name="Program approval status",
                    ),
                ),
                (
                    "approval_comments",
                    models.TextField(
                        blank=True, verbose_name="If rejecting, please explain why."
                    ),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="education",
                        to="chapters.Chapter",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("viewflow.process", models.Model),
        ),
    ]