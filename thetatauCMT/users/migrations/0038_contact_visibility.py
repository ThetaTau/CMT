from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0037_profile_picture"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your email addresses on your member profile. National Officers can always see them.",
                max_length=10,
                verbose_name="Email visibility",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your phone number on your member profile. National Officers can always see it.",
                max_length=10,
                verbose_name="Phone visibility",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="address_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your mailing address on your member profile. National Officers can always see it.",
                max_length=10,
                verbose_name="Address visibility",
            ),
        ),
        migrations.AddField(
            model_name="historicaluser",
            name="email_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your email addresses on your member profile. National Officers can always see them.",
                max_length=10,
                verbose_name="Email visibility",
            ),
        ),
        migrations.AddField(
            model_name="historicaluser",
            name="phone_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your phone number on your member profile. National Officers can always see it.",
                max_length=10,
                verbose_name="Phone visibility",
            ),
        ),
        migrations.AddField(
            model_name="historicaluser",
            name="address_visibility",
            field=models.CharField(
                choices=[
                    ("no_one", "No one (private)"),
                    ("officers", "My chapter's officers only"),
                    ("chapter", "Members of my chapter"),
                    ("members", "Any member on the site"),
                ],
                default="no_one",
                help_text="Who may see your mailing address on your member profile. National Officers can always see it.",
                max_length=10,
                verbose_name="Address visibility",
            ),
        ),
    ]
