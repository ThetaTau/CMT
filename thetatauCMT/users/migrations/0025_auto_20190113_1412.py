# Generated by Django 2.0.3 on 2019-01-13 21:12

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0024_auto_20181209_2148'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='graduation_year',
            field=models.PositiveIntegerField(default=2019, help_text='Use the following format: YYYY', validators=[django.core.validators.MinValueValidator(1950), django.core.validators.MaxValueValidator(2029)]),
        ),
        migrations.AlterField(
            model_name='usersemestergpa',
            name='year',
            field=models.IntegerField(choices=[(2016, 2016), (2017, 2017), (2018, 2018), (2019, 2019), (2020, 2020), (2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024), (2025, 2025), (2026, 2026)], default=2019),
        ),
        migrations.AlterField(
            model_name='usersemesterservicehours',
            name='year',
            field=models.IntegerField(choices=[(2016, 2016), (2017, 2017), (2018, 2018), (2019, 2019), (2020, 2020), (2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024), (2025, 2025), (2026, 2026)], default=2019),
        ),
    ]