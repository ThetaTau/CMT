# Generated by Django 3.2.15 on 2023-09-11 00:20

from django.db import migrations, models
import django.db.models.deletion

CHAPTER_OFFICER = {
    "corresponding secretary",
    "regent",
    "scribe",
    "treasurer",
    "vice regent",
}

COUNCIL = {
    "grand regent",
    "grand scribe",
    "grand treasurer",
    "grand vice regent",
    "grand marshal",
    "grand inner guard",
    "grand outer guard",
    "council delegate",
}

NATIONAL_OFFICER = {
    "national operations manager",
    "regional director",
    "candidate chapter director",
    "expansion director",
    "professional development director",
    "service director",
    "alumni programs director",
    "national director",
    "cmt director",
    "volunteer director",
    "educational foundation board of director",
}

NATIONAL_COMMITTEE = {
    "national officer",
    "data & evaluation coordinator",
    "diversity, equity, & inclusion coordinator",
    "editor-in-chief of the gear",
    "student advisory committee, chair",
}

ADVISOR_ROLES = {
    "adviser",
    "faculty adviser",
    "house corporation president",
    "house corporation treasurer",
}

COMMITTEE_CHAIR = {
    "board member",
    "committee chair",
    "diversity, equity, and inclusion chair",
    "employer/ee",
    "events chair",
    "fundraising chair",
    "housing chair",
    "marshal",
    "other appointee",
    "parent",
    "pd chair",
    "pledge/new member educator",
    "project chair",
    "recruitment chair",
    "risk management chair",
    "rube goldberg chair",
    "recruitment chair",
    "scholarship chair",
    "service chair",
    "social/brotherhood chair",
    "website/social media chair",
}

FOUNDATION_ALUMNI = {
    "president",
    "vice president",
    "secretary",
    "treasurer",
    "trustee",
}

CENTRAL = {
    "executive director",
    "director of chapter services",
    "director of operations",
    "director of programs",
    "administrative assistant",
}


def set_roles(apps, schema_editor):
    """
    Role.objects.create(
            name=role_name,
            officer: True,
            executive_council: False,
            chapter: True,
            national: False,
            alumni: False,
            central_office: False,
        )
    """
    Role = apps.get_model("users", "Role")
    for role_name in CHAPTER_OFFICER:
        Role.objects.create(
            name=role_name,
            officer=True,
            chapter=True,
        )
    for role_name in COUNCIL:
        Role.objects.create(
            name=role_name,
            officer=True,
            executive_council=True,
            national=True,
        )
    for role_name in NATIONAL_OFFICER:
        Role.objects.create(
            name=role_name,
            officer=True,
            national=True,
        )
    for role_name in NATIONAL_COMMITTEE:
        Role.objects.create(
            name=role_name,
            national=True,
        )
    for role_name in ADVISOR_ROLES:
        Role.objects.create(
            name=role_name,
            chapter=True,
        )
    for role_name in COMMITTEE_CHAIR:
        Role.objects.create(
            name=role_name,
            chapter=True,
        )
    for role_name in FOUNDATION_ALUMNI:
        Role.objects.create(
            name=role_name,
            foundation=True,
        )
    for role_name in FOUNDATION_ALUMNI:
        Role.objects.create(
            name=role_name,
            alumni=True,
        )

    for role_name in CENTRAL:
        Role.objects.create(
            name=role_name,
            central_office=True,
        )


def unset_roles(apps, schema_editor):
    pass


ROLE_ALIGN = {
    "colony director": "candidate chapter director",
    # Colonies used to use old terms.
    # Not likely to have foundation/alumni officers in old system
    "president": "regent",
    "secretary": "scribe",
    "vice president": "vice regent",
}
EXTRA_ARGS = {"treasurer": {"chapter": True}}


def link_roles(apps, schema_editor):
    """ """
    Role = apps.get_model("users", "Role")
    UserRoleChange = apps.get_model("users", "UserRoleChange")
    user_role_changes = UserRoleChange.objects.all()
    total = user_role_changes.count()
    for count, role in enumerate(user_role_changes):
        print(f"{count}/{total}")
        role_name = role.role
        role_name = ROLE_ALIGN.get(role_name, role_name)
        extra_kwargs = EXTRA_ARGS.get(role_name, {})
        try:
            role_obj = Role.objects.get(name=role_name, **extra_kwargs)
        except Role.DoesNotExist:
            raise ValueError(f"Missing role: {role_name}")
        except Role.MultipleObjectsReturned:
            raise ValueError(f"Multiple roles: {role_name}")
        role.role_link = role_obj
    UserRoleChange.objects.bulk_update(user_role_changes, ["role_link"])


def unlink_roles(apps, schema_editor):
    UserRoleChange = apps.get_model("users", "UserRoleChange")
    user_role_changes = UserRoleChange.objects.all()
    for role in user_role_changes:
        role_obj = role.role_link
        role.role = role_obj.name
    UserRoleChange.objects.bulk_update(user_role_changes, ["role"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0027_memberupdate"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                ("officer", models.BooleanField(default=False)),
                ("executive_council", models.BooleanField(default=False)),
                ("chapter", models.BooleanField(default=False)),
                ("national", models.BooleanField(default=False)),
                ("alumni", models.BooleanField(default=False)),
                ("foundation", models.BooleanField(default=False)),
                ("central_office", models.BooleanField(default=False)),
            ],
        ),
        migrations.AddField(
            model_name="userrolechange",
            name="role_link",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="users",
                to="users.role",
            ),
        ),
        migrations.RunPython(set_roles, unset_roles),
        migrations.RunPython(link_roles, unlink_roles),
    ]
