from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0042_contact_visibility_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="useralter",
            name="hide_admin",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When on, administrator-only abilities are hidden so the site can be "
                    "previewed without them. Combine with the national officer toggle and "
                    "no role above to see exactly what a regular member sees."
                ),
                verbose_name="Hide admin functionality",
            ),
        ),
    ]
