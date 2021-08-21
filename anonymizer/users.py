from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import anonym_field
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

register_clean([UserRoleChange, UserOrgParticipate])


class UserAnonym(AnonymBase):
    password = anonym_field.password("test")
    user_id = anonym_field.string("FAKE{seq}")
    email_school = anonym_field.string("{seq}_email_school@thetatau.org")
    email = anonym_field.string("{seq}@thetatau.org")
    username = anonym_field.string("{seq}@thetatau.org")
    middle_name = anonym_field.function(fake.first_name)
    preferred_name = anonym_field.function(fake.first_name)
    first_name = anonym_field.function(fake.first_name)
    last_name = anonym_field.function(fake.last_name)
    maiden_name = anonym_field.function(fake.last_name)
    nickname = anonym_field.function(fake.first_name)
    suffix = anonym_field.function(fake.suffix)
    emergency_nickname = anonym_field.function(fake.first_name)
    birth_date = anonym_field.function(fake.date_object)
    graduation_year = anonym_field.function(fake.year)
    name = anonym_field.function(fake.name)
    badge_number = anonym_field.function(fake.pyint)
    emergency_phone_number = anonym_field.function(fake.msisdn)
    emergency_first_name = anonym_field.function(fake.first_name)
    emergency_middle_name = anonym_field.function(fake.first_name)
    phone_number = anonym_field.function(fake.msisdn)
    emergency_last_name = anonym_field.function(fake.last_name)
    employer = anonym_field.function(fake.company)
    employer_position = anonym_field.function(fake.job)

    class Meta:
        queryset = User.objects.exclude(is_superuser=True)
        exclude_fields = [
            "address_changed",
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
        ]


register_anonym(
    [
        (User, UserAnonym),
    ]
)
