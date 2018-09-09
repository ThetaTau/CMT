# Generated by Django 2.0.3 on 2018-09-08 16:08

import core.models
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('forms', '0008_old_forms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='depledge',
            name='date',
            field=models.DateField(default=django.utils.timezone.now, verbose_name='Depledge Date'),
        ),
        migrations.AlterField(
            model_name='initiation',
            name='date',
            field=models.DateField(default=django.utils.timezone.now, verbose_name='Initiation Date'),
        ),
        migrations.AlterField(
            model_name='riskmanagement',
            name='date',
            field=models.DateField(default=django.utils.timezone.now, verbose_name='Submit Date'),
        ),
        migrations.AlterField(
            model_name='statuschange',
            name='date_end',
            field=models.DateField(blank=True, default=core.models.forever, verbose_name='End Date'),
        ),
        migrations.AlterField(
            model_name='statuschange',
            name='date_start',
            field=models.DateField(default=django.utils.timezone.now, verbose_name='Start Date'),
        ),
    ]