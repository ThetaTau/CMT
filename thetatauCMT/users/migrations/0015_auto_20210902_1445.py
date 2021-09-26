# Generated by Django 2.2.12 on 2021-09-02 21:45

from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_deceased"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userdemographic",
            name="gender",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("not_listed", "An identity not listed (write-in)"),
                    ("agender", "Agender"),
                    ("cisgender", "Cisgender"),
                    ("female", "Female"),
                    ("genderqueer", "Genderqueer/Gender non-conforming"),
                    ("intersex", "Intersex"),
                    ("male", "Male"),
                    ("nonbinary", "Nonbinary"),
                    ("no_answer", "Prefer not to answer"),
                    ("transgender", "Transgender"),
                ],
                default="no_answer",
                max_length=93,
                null=True,
                verbose_name="How would you describe your gender identity? (Select all that apply)",
            ),
        ),
        migrations.AlterField(
            model_name="userdemographic",
            name="racial",
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ("asian", "Asian"),
                    ("black", "Black or African American"),
                    ("caucasian", "Caucasian / White"),
                    ("islander", "Native Hawaiian or Other Pacific Islander"),
                    ("middle_eastern", "Middle Eastern or North African"),
                    ("not_listed", "An identity not listed (write-in)"),
                    ("latinx/a/o", "Latinx/a/o or Hispanic"),
                    ("native", "Native American / First Nations"),
                    ("no_answer", "Prefer not to answer"),
                ],
                default="no_answer",
                max_length=84,
                null=True,
                verbose_name="With which racial and ethnic group(s) do you identify? (Select all that apply)",
            ),
        ),
    ]