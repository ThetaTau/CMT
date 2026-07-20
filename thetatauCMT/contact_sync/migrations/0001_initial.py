from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserContactSyncToken",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("google", "Google Contacts"),
                            ("microsoft", "Microsoft Contacts"),
                        ],
                        max_length=32,
                    ),
                ),
                ("access_token_encrypted", models.TextField(blank=True, default="")),
                ("refresh_token_encrypted", models.TextField(blank=True, default="")),
                ("token_type", models.CharField(blank=True, default="Bearer", max_length=32)),
                ("scope", models.TextField(blank=True, default="")),
                ("account_email", models.EmailField(blank=True, default="", max_length=254)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_sync_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="contact_sync_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("provider", "user_id"),
                "unique_together": {("user", "provider")},
            },
        ),
    ]
