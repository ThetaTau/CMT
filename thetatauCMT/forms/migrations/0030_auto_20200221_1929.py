# Generated by Django 2.2.3 on 2020-02-22 02:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0029_auto_20200221_1555'),
    ]

    operations = [
        migrations.RenameField(
            model_name='prematurealumnus',
            old_name='verbose_consideration',
            new_name='consideration',
        ),
    ]
