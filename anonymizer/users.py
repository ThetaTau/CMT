from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import fields
from faker import Factory

from users.models import (
    User,
    UserDemographic,
    UserAlter,
    UserStatusChange,
    UserRoleChange,
    UserSemesterServiceHours,
    UserOrgParticipate,
    UserSemesterGPA,
)

fake = Factory.create()

register_skip(
    [
        UserAlter,
        UserStatusChange,
        UserSemesterServiceHours,
        UserDemographic,
        UserSemesterGPA,
    ]
)

register_clean(
    [
        (UserRoleChange, AnonymBase),
        (UserOrgParticipate, AnonymBase),
    ]
)


class UserAnonym(AnonymBase):
    password = fields.password("test")
    user_id = fields.string("FAKE{seq}")
    email_school = fields.string("{seq}_email_school@thetatau.org")
    email = fields.string("{seq}@thetatau.org")
    username = fields.string("{seq}@thetatau.org")
    middle_name = fields.function(fake.first_name)
    preferred_name = fields.function(fake.first_name)
    first_name = fields.function(fake.first_name)
    last_name = fields.function(fake.last_name)
    maiden_name = fields.function(fake.last_name)
    nickname = fields.function(fake.first_name)
    suffix = fields.function(fake.suffix)
    emergency_nickname = fields.function(fake.first_name)
    birth_date = fields.function(fake.date_object)
    graduation_year = fields.function(fake.year)
    name = fields.function(fake.name)
    badge_number = fields.function(fake.pyint)
    emergency_phone_number = fields.function(fake.msisdn)
    emergency_first_name = fields.function(fake.first_name)
    emergency_middle_name = fields.function(fake.first_name)
    phone_number = fields.function(fake.msisdn)
    emergency_last_name = fields.function(fake.last_name)
    employer = fields.function(fake.company)
    employer_position = fields.function(fake.job)
    current_roles = fields.string("")

    class Meta:
        queryset = User.objects.exclude(is_superuser=True)
        exclude_fields = [
            "address_changed",
            "deceased_changed",
            "deceased_date",
            "is_staff",
            "last_login",
            "emergency_relation",
            "degree",
            "title",
            "is_superuser",
            "deceased",
            "modified",
            "date_joined",
            "employer_changed",
            "is_active",
            "no_contact",
            "charter",
            "current_status",
        ]


register_anonym(
    [
        (User, UserAnonym),
    ]
)
