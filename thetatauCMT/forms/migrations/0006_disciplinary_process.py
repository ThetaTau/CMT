# Generated by Django 2.2.12 on 2020-07-27 02:52

import core.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import forms.models


class Migration(migrations.Migration):

    dependencies = [
        ("chapters", "0003_auto_20200517_1027"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("viewflow", "0008_jsonfield_and_artifact"),
        ("forms", "0005_init_no_future"),
    ]

    operations = [
        migrations.CreateModel(
            name="DisciplinaryProcess",
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
                    "charges",
                    models.TextField(
                        help_text="Please specify which section of the PPM the member is accused of violating."
                    ),
                ),
                (
                    "resolve",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Did chapter officers try to resolve the problem through private discussion with the brother?",
                    ),
                ),
                (
                    "advisor",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Was the chapter alumni adviser involved in trying to resolve this problem?",
                    ),
                ),
                (
                    "advisor_name",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        null=True,
                        verbose_name="If yes, alumni advisor name",
                    ),
                ),
                (
                    "faculty",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Was a campus/faculty adviser involved in trying to resolve this problem?",
                    ),
                ),
                (
                    "faculty_name",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        null=True,
                        verbose_name="If yes, campus/faculty adviser name",
                    ),
                ),
                (
                    "financial",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Is a simple collections action (for financial delinquency) better suited as a resolution to this issue?",
                    ),
                ),
                (
                    "charges_filed",
                    models.DateField(
                        default=django.utils.timezone.now,
                        validators=[core.models.no_future],
                        verbose_name="Charges filed by majority vote at a chapter meeting on date",
                    ),
                ),
                (
                    "notify_date",
                    models.DateField(
                        default=django.utils.timezone.now,
                        validators=[core.models.no_future],
                        verbose_name="Accused first notified of charges on date",
                    ),
                ),
                (
                    "notify_method",
                    forms.models.MultiSelectField(
                        choices=[
                            ("postal", "Postal Mail"),
                            ("email", "Email"),
                            ("text", "Text Message"),
                            ("social", "Social Media"),
                            ("phone", "Phone Call"),
                            ("person", "In Person"),
                            ("chat", "Chat Message"),
                        ],
                        max_length=42,
                    ),
                ),
                (
                    "trial_date",
                    models.DateField(
                        default=django.utils.timezone.now,
                        verbose_name="Trial scheduled for date",
                    ),
                ),
                (
                    "charging_letter",
                    models.FileField(
                        help_text="Please attach a copy of the charging letter that was sent to the member.",
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "take",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Did the trial take place as planned?",
                    ),
                ),
                (
                    "why_take",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("waived", "Accused Waived Right to Trial"),
                            ("rescheduled", "Rescheduled"),
                        ],
                        max_length=100,
                        null=True,
                        verbose_name="Why did the trial not take place?",
                    ),
                ),
                ("send_ec_date", models.DateField(blank=True, null=True)),
                (
                    "rescheduled_date",
                    models.DateField(
                        default=django.utils.timezone.now,
                        verbose_name="When will the new trial be held?",
                    ),
                ),
                (
                    "attend",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Did the accused attend the trial and defend?",
                    ),
                ),
                (
                    "guilty",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Was the accused found guilty of the charges by a 4/5 majority of the jury?",
                    ),
                ),
                (
                    "notify_results",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="Did the chapter notify the member by mail/email of the results of the trial?",
                    ),
                ),
                (
                    "notify_results_date",
                    models.DateField(
                        default=django.utils.timezone.now,
                        validators=[core.models.no_future],
                        verbose_name="On what date was the member notified of the results of the trial?",
                    ),
                ),
                (
                    "punishment",
                    models.CharField(
                        choices=[("expelled", "Expelled"), ("suspended", "Suspended")],
                        default="suspended",
                        max_length=100,
                        verbose_name="What was the punishment agreed to by the chapter?",
                    ),
                ),
                (
                    "suspension_end",
                    models.DateField(
                        default=django.utils.timezone.now,
                        verbose_name="If suspended, when will this member’s suspension end?",
                    ),
                ),
                (
                    "punishment_other",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="What other punishments, if any, were agreed to by the chapter?",
                    ),
                ),
                (
                    "collect_items",
                    models.BooleanField(
                        choices=[(True, "Yes"), (False, "No")],
                        default=False,
                        verbose_name="If the member was suspended pending expulsion, did the chapter collect and receive the member’s badge, shingle and/or other Theta Tau property?",
                    ),
                ),
                (
                    "minutes",
                    models.FileField(
                        blank=True,
                        help_text="Please attach a copy of the minutes from the meeting where the trial was held.",
                        null=True,
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "results_letter",
                    models.FileField(
                        blank=True,
                        help_text="Please attach a copy of the letter you sent to the member informing them of the outcome of the trial.",
                        null=True,
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "ed_process",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("process", "Accept and Process"),
                            ("accept", "Accept With No Action"),
                            ("reject", "Reject"),
                        ],
                        max_length=10,
                        null=True,
                        verbose_name="Executive Director Review",
                    ),
                ),
                (
                    "ed_notes",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Executive Director Review Notes",
                    ),
                ),
                (
                    "ec_approval",
                    models.BooleanField(
                        blank=True,
                        choices=[
                            (True, "Outcome approved by EC"),
                            (False, "Outcome Rejected by EC"),
                        ],
                        default=False,
                        null=True,
                        verbose_name="Executive Council Outcome",
                    ),
                ),
                (
                    "ec_notes",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Executive Council Review Notes",
                    ),
                ),
                (
                    "outcome_letter",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "final_letter",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discipline",
                        to="chapters.Chapter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discipline",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Name of Accused",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("viewflow.process", models.Model),
        ),
        migrations.CreateModel(
            name="DisciplinaryAttachment",
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
                (
                    "file",
                    models.FileField(
                        help_text="Please attach a copy of the letter you sent to the member informing them of the outcome of the trial.",
                        upload_to=forms.models.get_discipline_upload_path,
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="forms.DisciplinaryProcess",
                    ),
                ),
            ],
        ),
    ]
