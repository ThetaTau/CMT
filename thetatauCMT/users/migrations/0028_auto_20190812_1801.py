# Generated by Django 2.2.3 on 2019-08-13 01:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0027_auto_20190810_1635'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useralter',
            name='role',
            field=models.CharField(choices=[('treasurer', 'Treasurer'), ('scribe', 'Scribe'), ('vice regent', 'Vice Regent'), ('corresponding secretary', 'Corresponding Secretary'), ('regent', 'Regent'), (None, '------------')], max_length=50, null=True),
        ),
    ]
