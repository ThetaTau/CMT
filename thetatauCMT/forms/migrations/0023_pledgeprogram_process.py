# Generated by Django 2.2.12 on 2021-12-29 04:28

from django.db import migrations, models
import django.db.models.deletion
import forms.models


class Migration(migrations.Migration):

    dependencies = [
        ("viewflow", "0008_jsonfield_and_artifact"),
        ("forms", "0022_default_disc_opts"),
    ]

    operations = [
        migrations.CreateModel(
            name="PledgeProgramProcess",
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
                        verbose_name="Pledge program approval status",
                    ),
                ),
                (
                    "approval_comments",
                    models.TextField(
                        blank=True, verbose_name="If rejecting, please explain why."
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("viewflow.process",),
        ),
        migrations.AddField(
            model_name="pledgeprogram",
            name="schedule",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=forms.models.get_pledge_program_upload_path,
            ),
        ),
        migrations.AddField(
            model_name="pledgeprogram",
            name="process",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledge_programs",
                to="forms.PledgeProgramProcess",
            ),
        ),
    ]
