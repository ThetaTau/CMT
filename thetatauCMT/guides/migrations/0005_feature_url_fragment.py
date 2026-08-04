from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("guides", "0004_roleguide_roleguidestep"),
    ]

    operations = [
        migrations.AddField(
            model_name="feature",
            name="url_fragment",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Element id to scroll to on the destination page, without the '#'. "
                    "Use when the feature is a control on a larger page rather than a page of its own."
                ),
                max_length=100,
                verbose_name="URL fragment",
            ),
        ),
    ]
