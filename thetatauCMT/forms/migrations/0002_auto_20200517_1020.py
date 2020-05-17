# Generated by Django 2.2.12 on 2020-05-17 17:20

import address.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("submissions", "0002_submission_user"),
        ("chapters", "0002_chapter_region"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("address", "0002_auto_20160213_1726"),
        ("forms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="statuschange",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="status_changes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="riskmanagement",
            name="submission",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="risk_management_forms",
                to="submissions.Submission",
            ),
        ),
        migrations.AddField(
            model_name="riskmanagement",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="risk_form",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="prematurealumnus",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="prealumn_form",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="pledgeprogram",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledge_programs",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="pledgeprocess",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledge_process",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="pledgeprocess",
            name="pledges",
            field=models.ManyToManyField(
                blank=True, null=True, related_name="process", to="forms.Pledge"
            ),
        ),
        migrations.AddField(
            model_name="pledgeform",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledge_forms",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="pledge",
            name="address",
            field=address.models.AddressField(
                on_delete=django.db.models.deletion.PROTECT, to="address.Address"
            ),
        ),
        migrations.AddField(
            model_name="pledge",
            name="major",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledges",
                to="chapters.ChapterCurricula",
            ),
        ),
        migrations.AddField(
            model_name="pledge",
            name="school_name",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pledge_forms_full",
                to="chapters.Chapter",
                to_field="school",
            ),
        ),
        migrations.AddField(
            model_name="osm",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="osm",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="osm",
            name="nominate",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="osm",
                to=settings.AUTH_USER_MODEL,
                verbose_name="OSM Nomination",
            ),
        ),
        migrations.AddField(
            model_name="osm",
            name="officer1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="osm_off1",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Officer Signature",
            ),
        ),
        migrations.AddField(
            model_name="osm",
            name="officer2",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="osm_off2",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Officer Signature",
            ),
        ),
        migrations.AddField(
            model_name="initiationprocess",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="initiation_process",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="initiationprocess",
            name="initiations",
            field=models.ManyToManyField(
                blank=True, null=True, related_name="process", to="forms.Initiation"
            ),
        ),
        migrations.AddField(
            model_name="initiation",
            name="badge",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="initiation",
                to="forms.Badge",
            ),
        ),
        migrations.AddField(
            model_name="initiation",
            name="guard",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="initiation",
                to="forms.Guard",
            ),
        ),
        migrations.AddField(
            model_name="initiation",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="initiation",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="depledge",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="depledge",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="convention",
            name="alternate",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="alternate",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Alternate Signature",
            ),
        ),
        migrations.AddField(
            model_name="convention",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="convention",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="convention",
            name="delegate",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="delegate",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Delegate Signature",
            ),
        ),
        migrations.AddField(
            model_name="convention",
            name="officer1",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conv_off1",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Officer Signature",
            ),
        ),
        migrations.AddField(
            model_name="convention",
            name="officer2",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conv_off2",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Officer Signature",
            ),
        ),
        migrations.AddField(
            model_name="chapterreport",
            name="chapter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="info",
                to="chapters.Chapter",
            ),
        ),
        migrations.AddField(
            model_name="chapterreport",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chapter_form",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="audit",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="audit_form",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="pledgeprogram", unique_together={("chapter", "year", "term")},
        ),
        migrations.AlterUniqueTogether(
            name="pledgeform", unique_together={("name", "email")},
        ),
    ]
