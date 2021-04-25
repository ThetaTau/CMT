# Generated by Django 2.2.12 on 2021-04-24 20:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chapters", "0005_chaptercurricula_approved"),
    ]

    operations = [
        migrations.AddField(
            model_name="chapter",
            name="email_corresponding_secretary",
            field=models.EmailField(
                blank=True,
                help_text="A generic email used for communication, NOT the member email",
                max_length=254,
                verbose_name="Corresponding Secretary Generic email address",
            ),
        ),
        migrations.AddField(
            model_name="chapter",
            name="email_regent",
            field=models.EmailField(
                blank=True,
                help_text="A generic email used for communication, NOT the member email",
                max_length=254,
                verbose_name="Regent Generic email address",
            ),
        ),
        migrations.AddField(
            model_name="chapter",
            name="email_scribe",
            field=models.EmailField(
                blank=True,
                help_text="A generic email used for communication, NOT the member email",
                max_length=254,
                verbose_name="Scribe Generic email address",
            ),
        ),
        migrations.AddField(
            model_name="chapter",
            name="email_treasurer",
            field=models.EmailField(
                blank=True,
                help_text="A generic email used for communication, NOT the member email",
                max_length=254,
                verbose_name="Treasurer Generic email address",
            ),
        ),
        migrations.AddField(
            model_name="chapter",
            name="email_vice_regent",
            field=models.EmailField(
                blank=True,
                help_text="A generic email used for communication, NOT the member email",
                max_length=254,
                verbose_name="Vice Regent Generic email address",
            ),
        ),
    ]
