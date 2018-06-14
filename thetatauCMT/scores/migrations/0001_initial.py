# Generated by Django 2.0.3 on 2018-06-14 18:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('chapters', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScoreChapter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField(choices=[(2016, 2016), (2017, 2017), (2018, 2018), (2019, 2019), (2020, 2020), (2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024), (2025, 2025)], default=2018)),
                ('term', models.CharField(choices=[('fa', 'Fall'), ('sp', 'Spring'), ('wi', 'Winter'), ('su', 'Summer')], max_length=2)),
                ('score', models.FloatField(default=0)),
                ('chapter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='chapters.Chapter')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScoreType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=200)),
                ('section', models.CharField(choices=[('Bro', 'Brotherhood'), ('Ops', 'Operate'), ('Pro', 'Professional'), ('Ser', 'Service')], max_length=3)),
                ('points', models.PositiveIntegerField(default=0, help_text='Total number of points possible in year')),
                ('formula', models.CharField(help_text='Formula for calculating score', max_length=200)),
                ('name_short', models.CharField(max_length=20)),
                ('type', models.CharField(choices=[('Evt', 'Event'), ('Sub', 'Submit'), ('Spe', 'Special')], max_length=3)),
                ('base_points', models.FloatField(default=0)),
                ('attendance_multiplier', models.FloatField(default=0)),
                ('member_add', models.FloatField(default=0)),
                ('special', models.CharField(max_length=200)),
            ],
        ),
        migrations.AddField(
            model_name='scorechapter',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chapters', to='scores.ScoreType'),
        ),
    ]
