# Generated by Django 2.0.3 on 2018-08-09 05:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chapters', '0006_auto_20180705_1132'),
        ('scores', '0003_initial_scores_data'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='scorechapter',
            unique_together={('term', 'year', 'type', 'chapter')},
        ),
    ]