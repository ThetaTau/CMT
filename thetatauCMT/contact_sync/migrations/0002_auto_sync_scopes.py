import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contact_sync", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usercontactsynctoken",
            name="auto_sync_scopes",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=100),
                blank=True,
                default=list,
                help_text="Scopes to push on each scheduled run — 'national' or 'region:<slug>'.",
                size=None,
            ),
        ),
    ]
