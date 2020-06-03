from import_export import resources
from import_export.fields import Field
from .models import (
    Initiation,
    Depledge,
    Pledge,
    PledgeForm,
    StatusChange,
    PledgeProgram,
)


class InitiationResource(resources.ModelResource):
    chapter = Field("user__chapter__name")

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


class PledgeFormResource(resources.ModelResource):
    chapter = Field("chapter__name")

    class Meta:
        model = PledgeForm
        fields = (
            "name",
            "created",
            "reason",
            "email",
        )


class PledgeProgramResource(resources.ModelResource):
    chapter = Field("chapter__name")

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
