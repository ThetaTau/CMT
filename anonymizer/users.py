from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import fields
from email_signals.models import Signal, SignalConstraint
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
    MemberUpdate,
    HistoricalUser,
)

fake = Factory.create()

register_skip(
    [
        UserAlter,
        UserStatusChange,
        UserSemesterServiceHours,
        UserDemographic,
        UserSemesterGPA,
        Signal,
        SignalConstraint,
    ]
)

register_clean(
    [
        (UserRoleChange, AnonymBase),
        (UserOrgParticipate, AnonymBase),
        (HistoricalUser, AnonymBase),
    ]
)


class UserAnonym(AnonymBase):
    password = fields.password("test")
    email_school = fields.string("{seq}_email_school@thetatau.org")
    email = fields.string("{seq}@thetatau.org")
    username = fields.string("{seq}@thetatau.org")
    middle_name = fields.function(fake.first_name)
    preferred_name = fields.function(fake.first_name)
    preferred_pronouns = fields.function(fake.first_name)
    first_name = fields.function(fake.first_name)
    last_name = fields.function(fake.last_name)
    maiden_name = fields.function(fake.last_name)
    nickname = fields.function(fake.first_name)
    suffix = fields.function(fake.suffix)
    emergency_nickname = fields.function(fake.first_name)
    birth_date = fields.function(fake.date_object)
    graduation_year = fields.function(fake.year)
    class_year = fields.string("sophomore")
    name = fields.function(fake.name)
    badge_number = fields.function(fake.pyint)
    emergency_phone_number = fields.function(fake.msisdn)
    emergency_first_name = fields.function(fake.first_name)
    emergency_middle_name = fields.function(fake.first_name)
    phone_number = fields.function(fake.msisdn)
    emergency_last_name = fields.function(fake.last_name)
    employer = fields.function(fake.company)
    employer_position = fields.function(fake.job)

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
            "unsubscribe_paper_gear",
            "unsubscribe_email",
            "modified",
            "date_joined",
            "employer_changed",
            "is_active",
            "no_contact",
            "charter",
            "current_status",
            "current_roles",
            "officer",
        ]


class MemberUpdateAnonym(AnonymBase):
    badge_number = fields.function(fake.pyint)
    first_name = fields.function(fake.first_name)
    middle_name = fields.function(fake.first_name)
    last_name = fields.function(fake.last_name)
    maiden_name = fields.function(fake.last_name)
    preferred_name = fields.function(fake.first_name)
    preferred_pronouns = fields.function(fake.first_name)
    nickname = fields.function(fake.first_name)
    suffix = fields.function(fake.suffix)
    email = fields.string("{seq}@thetatau.org")
    email_school = fields.string("{seq}_email_school@thetatau.org")
    birth_date = fields.function(fake.date_object)
    phone_number = fields.function(fake.msisdn)
    graduation_year = fields.function(fake.year)
    employer = fields.function(fake.company)
    employer_position = fields.function(fake.job)

    class Meta:
        exclude_fields = [
            "degree",
            "outcome",
            "approved",
            "title",
            "finished",
            "status",
            "id",
            "data",
            "created",
            "flow_class",
            "major_other",
            "artifact_object_id",
            "unsubscribe_email",
            "unsubscribe_paper_gear",
        ]


register_anonym([(User, UserAnonym), (MemberUpdate, MemberUpdateAnonym)])
