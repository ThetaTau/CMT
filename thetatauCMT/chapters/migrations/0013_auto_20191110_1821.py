# Generated by Django 2.2.3 on 2019-11-11 01:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chapters', '0012_chapter_colony'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chapter',
            name='school',
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
    ]