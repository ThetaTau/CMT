# Generated by Django 2.2.12 on 2022-05-18 03:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("survey", "0014_survey_redirect_url"),
        ("surveys", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Survey",
            fields=[
                (
                    "survey_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="survey.Survey",
                    ),
                ),
                ("slug", models.SlugField(unique=True)),
                (
                    "anonymous",
                    models.BooleanField(
                        default=False,
                        help_text="Can the survey be submitted anonymously?",
                    ),
                ),
            ],
            bases=("survey.survey",),
        ),
    ]
