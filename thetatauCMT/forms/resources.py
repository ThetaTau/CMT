from import_export import resources
from import_export.fields import Field
from .models import (
    Initiation,
    Depledge,
    Pledge,
    StatusChange,
    PledgeProgram,
    PrematureAlumnus,
    CollectionReferral,
)


class InitiationResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = Initiation
        fields = (
            "user__name",
            "created",
            "date_graduation",
            "date",
            "roll",
        )


class DepledgeResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = Depledge
        fields = (
            "user__name",
            "created",
            "reason",
            "date",
        )


class PledgeResource(resources.ModelResource):
    class Meta:
        model = Pledge


class PledgeProgramResource(resources.ModelResource):
    chapter = Field("chapter__name")
    school = Field("chapter__school")

    class Meta:
        model = PledgeProgram
        fields = (
            "modified",
            "remote",
            "date_complete",
            "date_initiation",
            "weeks",
            "weeks_left",
            "status",
            "manual",
            "year",
            "term",
        )


class StatusChangeResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = StatusChange
        fields = (
            "user__name",
            "created",
            "reason",
            "degree",
            "date_start",
            "date_end",
            "employer",
            "miles",
            "email_work",
            "new_school",
        )


class PrematureAlumnusResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = PrematureAlumnus
        fields = (
            "user__name",
            "created",
            "approved_exec",
            "exec_comments",
            "prealumn_type",
        )


class CollectionReferralResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = CollectionReferral
        fields = (
            "user__name",
            "created",
            "created_by__name",
            "balance_due",
        )


class ReturnStudentResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = PrematureAlumnus
        fields = (
            "user__name",
            "created",
            "approved_exec",
            "exec_comments",
        )
