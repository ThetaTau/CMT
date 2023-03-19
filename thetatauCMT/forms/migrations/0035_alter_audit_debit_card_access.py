# Generated by Django 3.2.15 on 2023-03-19 06:20

from django.db import migrations
import forms.models


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0034_auto_20230117_1806"),
    ]

    operations = [
        migrations.AlterField(
            model_name="audit",
            name="debit_card_access",
            field=forms.models.MultiSelectField(
                choices=[
                    ("None", "None"),
                    ("adviser", "Adviser"),
                    ("board member", "Board Member"),
                    ("committee chair", "Committee Chair"),
                    ("corresponding secretary", "Corresponding Secretary"),
                    (
                        "diversity, equity, and inclusion chair",
                        "Diversity, Equity, And Inclusion Chair",
                    ),
                    ("employer/ee", "Employer/Ee"),
                    ("events chair", "Events Chair"),
                    ("faculty adviser", "Faculty Adviser"),
                    ("fundraising chair", "Fundraising Chair"),
                    ("house corporation president", "House Corporation President"),
                    ("house corporation treasurer", "House Corporation Treasurer"),
                    ("housing chair", "Housing Chair"),
                    ("marshal", "Marshal"),
                    ("other appointee", "Other Appointee"),
                    ("parent", "Parent"),
                    ("pd chair", "Pd Chair"),
                    ("pledge/new member educator", "Pledge/New Member Educator"),
                    ("project chair", "Project Chair"),
                    ("recruitment chair", "Recruitment Chair"),
                    ("regent", "Regent"),
                    ("risk management chair", "Risk Management Chair"),
                    ("rube goldberg chair", "Rube Goldberg Chair"),
                    ("scholarship chair", "Scholarship Chair"),
                    ("scribe", "Scribe"),
                    ("service chair", "Service Chair"),
                    ("social/brotherhood chair", "Social/Brotherhood Chair"),
                    ("treasurer", "Treasurer"),
                    ("vice regent", "Vice Regent"),
                    ("website/social media chair", "Website/Social Media Chair"),
                ],
                max_length=5000,
                verbose_name="Which members have access to the chapter debit card? Select all that apply.",
            ),
        ),
    ]
