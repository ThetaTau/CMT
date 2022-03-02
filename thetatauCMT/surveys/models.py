from django.conf import settings
from django.db import models
from core.models import TimeStampedModel, EnumClass


class DepledgeSurvey(TimeStampedModel):
    BOOL_CHOICES = ((True, "Yes"), (False, "No"))

    class REASONS(EnumClass):
        volunteer = ("volunteer", "Voluntarily decided not to continue")
        time = ("time", "Unable/unwilling to meet time commitment")
        grades = ("grades", "Unable/unwilling to meet academic requirement")
        financial = ("financial", "Unable/unwilling to meet financial commitment")
        violation = ("violation", "Policy/Procedure Violation")
        vote = ("vote", "Poor fit with the chapter/candidate chapter")
        withdrew = ("withdrew", "Withdrew from Engineering/University")
        transfer = ("transfer", "Transferring to another school")
        other = ("other", "Other")

    class HOW(EnumClass):
        me = ("me", "Decided by me")
        chapter = ("chapter", "Decided by the chapter")
        other = ("other", "Other")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="depledge_survey",
    )
    reason = models.CharField(
        "What was the reason for your depledging?",
        max_length=10,
        choices=[x.value for x in REASONS],
    )
    reason_other = models.CharField(
        "Other reason for depledging",
        max_length=100,
        null=True,
        blank=True,
    )
    decided = models.CharField(
        "How was your depledging decided?",
        max_length=10,
        choices=[x.value for x in HOW],
    )
    decided_other = models.CharField(
        "Decided in another way",
        max_length=100,
        null=True,
        blank=True,
    )
    enjoyed = models.TextField(
        "Was there a part of the education program that you particularly enjoyed or found helpful?",
        null=True,
        blank=True,
    )
    improve = models.TextField(
        "Do you have any suggestions to improve the education program?",
        null=True,
        blank=True,
    )
    extra_notes = models.TextField(
        "Is there anything else you'd like to share?",
        null=True,
        blank=True,
    )
    contact = models.BooleanField(
        "Would you like someone to contact you?", choices=BOOL_CHOICES, default=False
    )
