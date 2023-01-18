# Generated by Django 3.2.15 on 2023-01-18 01:06

import core.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0033_pledgeprogram_test"),
    ]

    operations = [
        migrations.AlterField(
            model_name="audit",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="chapterreport",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="convention",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="osm",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="pledgeprogram",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="riskmanagement",
            name="year",
            field=models.IntegerField(
                default=core.models.current_year,
                validators=[
                    django.core.validators.MinValueValidator(2016),
                    django.core.validators.MaxValueValidator(
                        core.models.current_year_plus_10
                    ),
                ],
            ),
        ),
    ]
