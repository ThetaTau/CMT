# Generated by Django 2.0.3 on 2018-09-08 16:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chapters', '0007_chapter_school_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chapter',
            name='balance_date',
            field=models.DateField(auto_now_add=True),
        ),
    ]