from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0036_unsubscribe_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_picture",
            field=models.ImageField(
                blank=True,
                help_text="Optional photo displayed on your public member profile.",
                null=True,
                upload_to="profile_pictures/%Y/%m/",
                verbose_name="Profile Picture",
            ),
        ),
        migrations.AddField(
            model_name="historicaluser",
            name="profile_picture",
            field=models.CharField(
                blank=True,
                help_text="Optional photo displayed on your public member profile.",
                max_length=100,
                null=True,
                verbose_name="Profile Picture",
            ),
        ),
    ]
