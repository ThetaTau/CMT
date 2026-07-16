from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0038_contact_visibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="useralter",
            name="hide_natoff",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When on, national-officer-only abilities are hidden so the site "
                    "can be previewed as a regular member (or, with a role selected "
                    "above, as that chapter officer)."
                ),
                verbose_name="Hide national officer functionality",
            ),
        ),
    ]
