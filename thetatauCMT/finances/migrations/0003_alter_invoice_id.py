# Generated by Django 3.2.15 on 2022-08-21 01:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finances", "0002_auto_20220625_1139"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]