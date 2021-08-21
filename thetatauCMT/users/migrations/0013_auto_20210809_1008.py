# Generated by Django 2.2.12 on 2021-08-09 17:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_auto_20210726_1021"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_name",
            field=models.CharField(
                blank=True,
                help_text="Prefered First Name - eg my first name is Kevin but I go by my middle name Henry.",
                max_length=255,
                null=True,
                verbose_name="Preferred Name",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="nickname",
            field=models.CharField(
                blank=True,
                help_text="Other than first name and preferred first name - eg Bud, Skip, Frank The Tank, Etc. Do NOT indicate 'pledge names'",
                max_length=30,
            ),
        ),
    ]
