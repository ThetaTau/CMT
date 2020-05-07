# Generated by Django 2.2.12 on 2020-05-06 00:48

import core.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('chapters', '0016_auto_20200103_1544'),
        ('viewflow', '0008_jsonfield_and_artifact'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('forms', '0039_auto_20200429_2142'),
    ]

    operations = [
        migrations.CreateModel(
            name='OSM',
            fields=[
                ('process_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='viewflow.Process')),
                ('year', models.IntegerField(choices=[(2016, 2016), (2017, 2017), (2018, 2018), (2019, 2019), (2020, 2020), (2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024), (2025, 2025), (2026, 2026), (2027, 2027)], default=2020)),
                ('term', models.CharField(choices=[('fa', 'Fall'), ('sp', 'Spring'), ('wi', 'Winter'), ('su', 'Summer')], max_length=2)),
                ('meeting_date', models.DateField(default=django.utils.timezone.now, validators=[core.models.no_future])),
                ('selection_process', models.TextField(verbose_name='How was the Chapter Outstanding Student Member chosen? What process was used to select them?')),
                ('approved_o1', models.BooleanField(choices=[(True, 'Approve'), (False, 'Deny')], default=False, verbose_name='Officer Approved')),
                ('approved_o2', models.BooleanField(choices=[(True, 'Approve'), (False, 'Deny')], default=False, verbose_name='Officer Approved')),
                ('chapter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='osm', to='chapters.Chapter')),
                ('nominate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='osm', to=settings.AUTH_USER_MODEL, verbose_name='OSM Nomination')),
                ('officer1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='osm_off1', to=settings.AUTH_USER_MODEL, verbose_name='Officer Signature')),
                ('officer2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='osm_off2', to=settings.AUTH_USER_MODEL, verbose_name='Officer Signature')),
            ],
            options={
                'abstract': False,
            },
            bases=('viewflow.process', models.Model),
        ),
    ]
