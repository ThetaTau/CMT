# Generated by Django 2.2.12 on 2022-01-17 02:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0003_geararticle_picture"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="name",
            field=models.CharField(max_length=200, verbose_name="Submission Name"),
        ),
    ]
