# Generated by Django 2.2.3 on 2020-03-09 00:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0030_initiationprocess'),
    ]

    operations = [
        migrations.AddField(
            model_name='initiationprocess',
            name='invoice',
            field=models.PositiveIntegerField(default=999999999, verbose_name='Invoice Number'),
        ),
    ]