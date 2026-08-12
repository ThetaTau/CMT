import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField
from viewflow.models import Process

from core.models import NAT_OFFICERS_CHOICES, EnumClass, resolve_config_actor
from thetatauCMT.configs.models import Config

# ---------------------------------------------------------------------------
# Config-driven reviewer assignment
# ---------------------------------------------------------------------------
# Each flow node's responsible actor is resolved from the EXISTING config
# system (``thetatauCMT.configs.models.Config`` -- a key/value table).  The
# value stored for a key may be either a username / email OR a national-officer
# role name from ``core.models.NAT_OFFICERS`` (e.g. ``"regional director"``).
REVIEWER_VOLUNTEER = "VolunteerReviewer"
REVIEWER_VETTING = "VettingReviewer"
REVIEWER_INTERVIEWER = "Interviewer"
REVIEWER_TRAINING = "TrainingAdministrator"
REVIEWER_CONFIRMER = "Confirmer"
REVIEWER_APPOINTMENT = "AppointmentProcessor"
REVIEWER_CENTRAL_OFFICE = "CentralOffice"

REVIEWER_CONFIG_KEYS = [
    REVIEWER_VOLUNTEER,
    REVIEWER_VETTING,
    REVIEWER_INTERVIEWER,
    REVIEWER_TRAINING,
    REVIEWER_CONFIRMER,
    REVIEWER_APPOINTMENT,
    REVIEWER_CENTRAL_OFFICE,
]


def get_reviewer_for(node_key):
    """Return the responsible reviewer ``User`` for a flow node, from config.

    Resolution order:

    1. the actor configured for ``node_key`` in ``configs.Config``,
    2. the ``CentralOffice`` config actor (unless already resolving it),
    3. the Executive Director (``settings.EXECUTIVE_DIRECTOR``),
    4. ``None`` -- viewflow simply leaves the task unassigned.
    """
    user = resolve_config_actor(Config.get_value(node_key))
    if user is None and node_key != REVIEWER_CENTRAL_OFFICE:
        user = resolve_config_actor(Config.get_value(REVIEWER_CENTRAL_OFFICE))
    if user is None:
        executive_director = getattr(settings, "EXECUTIVE_DIRECTOR", None)
        if executive_director:
            user = resolve_config_actor(executive_director)
    return user


def get_appointment_letter_path(instance, filename):
    return f"nominations/appointment_letters/{instance.pk}_{filename}"


def get_denial_letter_path(instance, filename):
    return f"nominations/denial_letters/{instance.pk}_{filename}"


class Nomination(Process):
    """A volunteer nomination, modelled as a viewflow ``Process``.

    One recommendation submission == one ``Nomination`` process.  The lifecycle
    (consent -> vetting -> interview -> training -> confirmation -> appointment)
    is driven by :class:`thetatauCMT.nominations.flows.NominationFlow`.

    Records are retained even when rejected / denied so they can be re-reviewed
    later.  Only a nominee "not interested" response (``not_interested``) blocks
    future recommendations of that member.
    """

    class LEVELS(EnumClass):
        chapter = ("chapter", "Chapter")
        regional = ("regional", "Regional")
        national = ("national", "National")

    class CONSENT(EnumClass):
        pending = ("pending", "Pending")
        interested = ("interested", "Interested")
        not_interested = ("not_interested", "Not interested")
        follow_up_later = ("follow_up_later", "Follow up later")

    # --- Who is being nominated --------------------------------------------
    nominee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="nominations",
        null=True,
        blank=True,
        help_text="The member being nominated, if they already have a record.",
    )
    nominee_name = models.CharField(
        _("Nominee name"),
        max_length=255,
        blank=True,
        help_text="Only needed when the nominee is not yet a member.",
    )
    nominee_email = models.EmailField(
        _("Nominee email"),
        blank=True,
        help_text="Only needed when the nominee is not yet a member.",
    )

    # --- Who nominated them -------------------------------------------------
    nominator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nominations_made",
    )

    # --- What they were nominated for --------------------------------------
    level = MultiSelectField(
        _("Level(s)"),
        choices=[level.value for level in LEVELS],
        max_length=30,
        default="national",
        help_text="One or more levels the member is being recommended for.",
    )
    recommended_positions = MultiSelectField(
        _("Recommended position(s)"),
        choices=NAT_OFFICERS_CHOICES,
        max_length=1000,
        blank=True,
        help_text="One or more positions from the national-officer roles.",
    )
    reason = models.TextField(
        _("Reason for recommendation"),
        help_text="This will be shared with the nominee.",
    )
    discussed_with_nominee = models.BooleanField(
        _("I have discussed this nomination with the nominee"),
        default=False,
    )

    # --- Flags -------------------------------------------------------------
    not_interested = models.BooleanField(
        default=False,
        help_text="Set when the nominee declines; blocks future recommendations.",
    )

    # --- Tokenized (no-login) consent link ---------------------------------
    # Unguessable, unique per nomination so the nominee can respond without an
    # account.  ``consent_token_expires`` makes the link expiring; it is set
    # when the consent email is issued (see ``nominations.tokens``).
    consent_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    consent_token_expires = models.DateTimeField(null=True, blank=True)

    # --- Flow state (drives If / Switch routing; fleshed out in later WIs) --
    consent_status = models.CharField(
        max_length=20,
        choices=[choice.value for choice in CONSENT],
        default="pending",
    )
    # What the nominee themselves expressed interest in at consent time -- kept
    # separate from the nominator's recommendation (``recommended_positions`` /
    # ``level``) so both are preserved.
    interested_positions = MultiSelectField(
        _("Positions the nominee is interested in"),
        choices=NAT_OFFICERS_CHOICES,
        max_length=1000,
        blank=True,
    )
    interested_level = MultiSelectField(
        _("Level(s) the nominee is interested in"),
        choices=[level.value for level in LEVELS],
        max_length=30,
        blank=True,
    )
    # Vetting record (VWI-5): reference/background check + pass/fail outcome.
    reference_check = models.BooleanField(
        _("Reference / background check completed"),
        default=False,
    )
    vetting_passed = models.BooleanField(null=True, blank=True)
    # Interview record (VWI-6): conducted flag + date + continue/stop outcome.
    interview_conducted = models.BooleanField(
        _("Interview conducted"),
        default=False,
    )
    interview_date = models.DateField(_("Interview date"), null=True, blank=True)
    interview_passed = models.BooleanField(null=True, blank=True)
    # Training record (VWI-7): the two required trainings + overall flag.
    training_cmt_complete = models.BooleanField(
        _("CMT LMS Volunteer Training complete"),
        default=False,
    )
    training_vector_complete = models.BooleanField(
        _("Vector CommunityEDU H&S Training complete"),
        default=False,
    )
    training_completed = models.BooleanField(default=False)
    confirmed = models.BooleanField(null=True, blank=True)
    appointed = models.BooleanField(default=False)

    # Appointment record (VWI-9): checklist for the AppointmentProcessor.
    appointment_letter = models.FileField(
        _("Appointment letter"),
        upload_to=get_appointment_letter_path,
        blank=True,
        null=True,
    )
    appointment_letter_sent_at = models.DateTimeField(null=True, blank=True)
    chapters_notified = models.BooleanField(default=False)
    ppm_ordered = models.BooleanField(_("PPM ordered"), default=False)
    added_to_natoff_lists = models.BooleanField(default=False)

    # Rejection / denial record (VWI-10).
    rejection_sent_at = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(blank=True)
    denial_letter = models.FileField(
        _("Denial letter"),
        upload_to=get_denial_letter_path,
        blank=True,
        null=True,
    )
    denial_letter_sent_at = models.DateTimeField(null=True, blank=True)

    # --- Follow-up tracking ------------------------------------------------
    # ``last_contacted`` is set whenever the nominee is emailed the consent
    # link; ``last_activity`` whenever the nomination moves. The daily
    # follow-up command (VWI-12) uses these to decide when to re-contact a
    # nomination that is parked awaiting follow-up.
    last_activity = models.DateTimeField(null=True, blank=True)
    last_contacted = models.DateTimeField(null=True, blank=True)

    # --- Per-step audit notes ----------------------------------------------
    # The viewflow Task / Process history is the primary audit trail; these
    # augment it with free-text context per step.
    consent_notes = models.TextField(blank=True)
    vetting_notes = models.TextField(blank=True)
    interview_notes = models.TextField(blank=True)
    training_notes = models.TextField(blank=True)
    confirmation_notes = models.TextField(blank=True)
    appointment_notes = models.TextField(blank=True)

    @property
    def nominee_display(self):
        """A human label for the nominee whether or not they have a record."""
        if self.nominee_id:
            return str(self.nominee)
        return self.nominee_name or self.nominee_email or "Unknown nominee"

    @property
    def nominee_email_address(self):
        """Where to reach the nominee (member email or supplied non-member email)."""
        if self.nominee_id and self.nominee.email:
            return self.nominee.email
        return self.nominee_email

    @property
    def consent_token_expired(self):
        """True when the tokenized consent link is unusable.

        A link is unusable when no token has been issued (no expiry set) or the
        expiry has passed.
        """
        return self.consent_token_expires is None or timezone.now() > self.consent_token_expires

    @property
    def current_step(self):
        """Human label for the nomination's current (active) step, for tracking."""
        if self.finished is not None:
            if self.appointed:
                return "Appointed"
            if self.not_interested:
                return "Closed \u2014 not interested"
            return "Closed"
        task = self.active_tasks().first()
        if task is not None and task.flow_task is not None:
            return task.flow_task.task_title or task.flow_task.name
        return "In progress"

    def log_contact(self, kind, subject="", recipient="", notes=""):
        """Record a contact/communication with the nominee (VWI polish #12)."""
        return self.contacts.create(
            kind=kind,
            subject=subject,
            recipient=recipient or (self.nominee_email_address or ""),
            notes=notes,
        )

    def __str__(self):
        return f"Nomination of {self.nominee_display} ({self.get_level_display()})"


class NominationContact(models.Model):
    """An append-only log of every contact/communication with the nominee.

    Populated whenever the nominee is emailed (consent, progress updates,
    appointment / denial letters, ...) and shown inline on the Nomination admin.
    """

    nomination = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name="contacts")
    kind = models.CharField(max_length=50)
    subject = models.CharField(max_length=255, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.kind} to {self.recipient} ({self.sent_at:%Y-%m-%d})"
