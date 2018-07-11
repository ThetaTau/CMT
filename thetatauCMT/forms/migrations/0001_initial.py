# Generated by Django 2.0.3 on 2018-07-10 13:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chapters', '0006_auto_20180705_1132'),
    ]

    operations = [
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('code', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=500)),
                ('cost', models.DecimalField(decimal_places=2, default=0, help_text='Cost of item.', max_digits=7)),
            ],
        ),
        migrations.CreateModel(
            name='Depledge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('reason', models.CharField(choices=[('volunteer', 'Voluntarily decided not to continue'), ('time', 'Too much time required'), ('grades', 'Poor grades'), ('interest', 'Lost interest'), ('vote', 'Negative Chapter Vote'), ('withdrew', 'Withdrew from Engineering/University'), ('transfer', 'Transferring to another school'), ('other', 'Other')], max_length=10)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='depledge', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Guard',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('code', models.CharField(max_length=50)),
                ('letters', models.IntegerField(choices=[(1, 'one'), (2, 'two')], default=1)),
                ('description', models.CharField(max_length=500)),
                ('cost', models.DecimalField(decimal_places=2, default=0, help_text='Cost of item.', max_digits=7)),
            ],
        ),
        migrations.CreateModel(
            name='Initiation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('date_graduation', models.DateTimeField(default=django.utils.timezone.now)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('roll', models.PositiveIntegerField(default=999999999)),
                ('gpa', models.FloatField()),
                ('test_a', models.FloatField()),
                ('test_b', models.FloatField()),
                ('badge', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='initiation', to='forms.Badge')),
                ('guard', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='initiation', to='forms.Guard')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='initiation', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='StatusChange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('reason', models.CharField(choices=[('graduate', 'Member is graduating'), ('coop', 'Member is going on CoOp or Study abroad'), ('military', 'Member is being deployed'), ('withdraw', 'Member is withdrawing from school'), ('transfer', 'Member is transferring to another school')], max_length=10)),
                ('degree', models.CharField(choices=[('bs', 'Bachelor of Science'), ('ms', 'Master of Science'), ('mba', 'Master of Business Administration'), ('phd', 'Doctor of Philosophy'), ('ba', 'Bachelor of Arts'), ('ma', 'Master of Arts'), ('me', 'Master of Engineering')], max_length=4)),
                ('date_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_end', models.DateTimeField(default=django.utils.timezone.now)),
                ('employer', models.CharField(max_length=200)),
                ('miles', models.PositiveIntegerField(default=0, help_text='Miles from campus.')),
                ('email_work', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('new_school', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='transfers', to='chapters.Chapter')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
