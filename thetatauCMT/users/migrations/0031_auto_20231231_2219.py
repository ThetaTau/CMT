# Generated by Django 3.2.15 on 2024-01-01 05:19

from django.conf import settings
from django.db import migrations
import django.db.models.deletion
import django_userforeignkey.models.fields


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0030_auto_20231021_1229"),
    ]

    operations = [
        migrations.AddField(
            model_name="userorgparticipate",
            name="created_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="org_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="userorgparticipate",
            name="modified_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="org_modified",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="userrolechange",
            name="created_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="role_change_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="userrolechange",
            name="modified_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="role_change_modified",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="usersemestergpa",
            name="created_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gpa_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="usersemestergpa",
            name="modified_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="gpa_modified",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="usersemesterservicehours",
            name="created_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="service_hours_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="usersemesterservicehours",
            name="modified_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="service_hours_modified",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="userstatuschange",
            name="created_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="status_change_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
        migrations.AddField(
            model_name="userstatuschange",
            name="modified_by",
            field=django_userforeignkey.models.fields.UserForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="status_change_modified",
                to=settings.AUTH_USER_MODEL,
                verbose_name="The user that created this object",
            ),
        ),
    ]