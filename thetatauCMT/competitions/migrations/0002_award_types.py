"""Q24 A: the three chapter award types the Case Competition records its results with.

Found or made by name, so an award type an Admin already created is reused. Reversing leaves
them in place, because grants may point at them.
"""

from django.db import migrations

AWARD_TYPES = [
    {
        "name": "NECC Regional Qualifier",
        "description": (
            "A chapter whose proposal was selected as a Regional Qualifier in the National Engineering Case "
            "Competition, advancing to the funded final round."
        ),
        "eligibility": "Chapters whose proposal judges and the competition managers selected, up to two per region.",
    },
    {
        "name": "NECC First Place",
        "description": "The chapter that won first place in the National Engineering Case Competition.",
        "eligibility": "Regional Qualifiers that made a final submission. Announced at Convention.",
    },
    {
        "name": "NECC Second Place",
        "description": "The chapter that won second place in the National Engineering Case Competition.",
        "eligibility": "Regional Qualifiers that made a final submission. Announced at Convention.",
    },
]


def add_award_types(apps, schema_editor):
    AwardType = apps.get_model("awards", "AwardType")
    if not AwardType.objects.exists():
        # A brand-new database: `loaddata award_types` comes later and uses fixed pks 1 to 30, which
        # would overwrite rows made here. Publishing results makes any missing type by name instead
        # (judging.award_type_for).
        return
    for values in AWARD_TYPES:
        if AwardType.objects.filter(name__iexact=values["name"]).exists():
            continue
        AwardType.objects.create(
            **values,
            category="Case Competition",
            level="chapter",
            grant_method="direct",
            recurrence="recurring",
            single_winner=values["name"] != "NECC Regional Qualifier",
            allow_multiple_winners=values["name"] == "NECC Regional Qualifier",
            is_active=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("awards", "0012_awardtype_eligibility"),
        ("competitions", "0001_initial"),
    ]

    operations = [migrations.RunPython(add_award_types, migrations.RunPython.noop)]
