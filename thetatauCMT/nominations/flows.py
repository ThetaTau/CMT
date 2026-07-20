from django.utils import timezone
from django.utils.decorators import method_decorator
from viewflow import flow
from viewflow.base import Flow, this
from viewflow.compat import _
from viewflow.flow import views as flow_views

from core.flows import FilterableFlowViewSet, register_factory

from .models import (
    REVIEWER_APPOINTMENT,
    REVIEWER_CENTRAL_OFFICE,
    REVIEWER_CONFIRMER,
    REVIEWER_INTERVIEWER,
    REVIEWER_TRAINING,
    REVIEWER_VETTING,
    Nomination,
    get_reviewer_for,
)
from .views import ConfirmationView, NominationCreateView

# ---------------------------------------------------------------------------
# Branch condition helpers
# ---------------------------------------------------------------------------
# Defined as named module-level functions (rather than inline lambdas) so the
# routing logic can be unit-tested directly with a stubbed activation.
_INTERESTED = Nomination.CONSENT.interested.value[0]
_NOT_INTERESTED = Nomination.CONSENT.not_interested.value[0]
_FOLLOW_UP = Nomination.CONSENT.follow_up_later.value[0]


def nominee_is_interested(activation):
    return activation.process.consent_status == _INTERESTED


def nominee_is_not_interested(activation):
    return activation.process.consent_status == _NOT_INTERESTED


def nominee_wants_follow_up(activation):
    return activation.process.consent_status == _FOLLOW_UP


def vetting_passed(activation):
    return activation.process.vetting_passed is True


def interview_passed(activation):
    return activation.process.interview_passed is True


def confirmation_approved(activation):
    return activation.process.confirmed is True


@register_factory(viewset_class=FilterableFlowViewSet)
class NominationFlow(Flow):
    """Volunteer Nomination lifecycle.

    ::

        Start(recommendation) -> nominee_consent
          -> [interested]     vetting -> [pass] interview -> [pass] training
          -> confirmation -> [confirm] appointment -> End(appointed)

    Branch outcomes (records are always retained):

    * ``not_interested``          -> End(closed)
    * ``follow_up_later``         -> flagged for re-contact (VWI-4 / VWI-11)
    * vetting / interview *fail*  -> rejection -> End(rejected)
    * confirmation *deny*         -> denial   -> End(denied)

    Every reviewer node is assigned from the config system via
    :func:`get_reviewer_for` and gated by an auto-created per-task permission.
    """

    process_class = Nomination
    process_title = _("Volunteer Nomination")
    process_description = _(
        "Recommend a member for a volunteer position and shepherd them through "
        "consent, vetting, interview, training, confirmation and appointment."
    )
    summary_template = "{{ flow_class.process_title }} - {{ process.nominee_display }}"

    # 1. Recommendation form (one submission == one Nomination) --------------
    start = flow.Start(
        NominationCreateView,
        task_title=_("Submit Volunteer Recommendation"),
    ).Next(this.send_consent_request)

    # 2. Issue the tokenized consent link and email the nominee --------------
    send_consent_request = flow.Handler(
        this.send_consent_request_func,
        task_title=_("Email Nominee Consent Request"),
    ).Next(this.nominee_consent)

    # 3. Nominee consent (external actor) ------------------------------------
    # The nominee responds via the tokenized no-login link (NomineeConsentView),
    # which completes this waiting task. Assigned to the nominee when they are a
    # member (informational); non-member nominees leave it unassigned.
    nominee_consent = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["consent_status", "consent_notes"],
            task_title=_("Nominee Consent"),
            task_description=_("The nominee indicates whether they are interested."),
            task_result_summary=_("Nominee response: {{ process.get_consent_status_display }}"),
        )
        .Assign(lambda act: act.process.nominee)
        .Next(this.check_consent)
    )

    check_consent = (
        flow.Switch(task_title=_("Route on nominee response"))
        .Case(this.vetting, cond=nominee_is_interested)
        .Case(this.closed, cond=nominee_is_not_interested)
        .Case(this.follow_up, cond=nominee_wants_follow_up)
        .Default(this.follow_up)
    )

    # 4. Vetting (reference / background check) ------------------------------
    vetting = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["reference_check", "vetting_notes", "vetting_passed"],
            task_title=_("Vetting Review"),
            task_result_summary=_("Vetting {{ process.vetting_passed|yesno:'passed,failed,pending' }}"),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_VETTING))
        .Permission(auto_create=True)
        .Next(this.check_vetting)
    )

    check_vetting = (
        flow.If(cond=vetting_passed, task_title=_("Vetting passed?"))
        .Then(this.notify_vetting_passed)
        .Else(this.rejection)
    )

    notify_vetting_passed = flow.Handler(
        this.notify_vetting_passed_func,
        task_title=_("Notify Nominee \u2014 Vetting Passed"),
    ).Next(this.interview)

    # 5. Interview -----------------------------------------------------------
    interview = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["interview_conducted", "interview_date", "interview_notes", "interview_passed"],
            task_title=_("Interview"),
            task_result_summary=_("Interview {{ process.interview_passed|yesno:'passed,failed,pending' }}"),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_INTERVIEWER))
        .Permission(auto_create=True)
        .Next(this.check_interview)
    )

    check_interview = (
        flow.If(cond=interview_passed, task_title=_("Interview passed?"))
        .Then(this.notify_interview_passed)
        .Else(this.rejection)
    )

    notify_interview_passed = flow.Handler(
        this.notify_interview_passed_func,
        task_title=_("Notify Nominee \u2014 Interview Passed"),
    ).Next(this.training)

    # 6. Training (manual mark now; pluggable LMS/Vector provider) -----------
    # Completed by ``services.mark_training_complete`` (via the TrainingView or a
    # future LMS/Vector webhook) only once BOTH required trainings are done.
    training = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["training_notes"],
            task_title=_("Training"),
            task_result_summary=_("Training {{ process.training_completed|yesno:'completed,incomplete' }}"),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_TRAINING))
        .Permission(auto_create=True)
        .Next(this.confirmation)
    )

    # 7. Confirmation (Central Office review) -------------------------------
    confirmation = (
        flow.View(
            ConfirmationView,
            fields=["confirmed", "confirmation_notes"],
            task_title=_("Confirmation"),
            task_result_summary=_("Confirmation {{ process.confirmed|yesno:'approved,denied,pending' }}"),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_CONFIRMER))
        .Permission(auto_create=True)
        .Next(this.check_confirmation)
    )

    check_confirmation = (
        flow.If(cond=confirmation_approved, task_title=_("Confirmed?"))
        .Then(this.notify_confirmed)
        .Else(this.denial_central_office)
    )

    notify_confirmed = flow.Handler(
        this.notify_confirmed_func,
        task_title=_("Notify Nominee \u2014 Confirmed"),
    ).Next(this.appointment)

    # 7. Appointment ---------------------------------------------------------
    appointment = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["appointment_notes"],
            task_title=_("Appointment"),
            task_result_summary=_("Appointment processed"),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_APPOINTMENT))
        .Permission(auto_create=True)
        .Next(this.apply_appointment)
    )

    apply_appointment = flow.Handler(
        this.apply_appointment_func,
        task_title=_("Record Appointment"),
    ).Next(this.appointed)

    # --- Non-happy-path handlers -------------------------------------------
    # Vetting / interview failure: thank-you communication + End (retain record;
    # do NOT set not_interested).
    rejection = flow.Handler(
        this.mark_rejected,
        task_title=_("Send Thank-you & Close"),
    ).Next(this.rejected)

    # Confirmation deny: routed to the configured CentralOffice to upload and
    # email a denial letter (DenialCentralOfficeView drives completion), then End.
    denial_central_office = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["denial_reason"],
            task_title=_("Central Office Denial"),
            task_description=_("Upload and email the denial letter to the nominee."),
        )
        .Assign(lambda act: get_reviewer_for(REVIEWER_CENTRAL_OFFICE))
        .Permission(auto_create=True)
        .Next(this.denied)
    )

    follow_up = flow.Handler(
        this.mark_follow_up,
        task_title=_("Flag for Follow-up"),
    ).Next(this.follow_up_wait)

    # Parked "awaiting follow-up" state. The daily follow-up command (VWI-12)
    # advances this Function task via ``services.recontact_nomination``, which
    # loops back to ``send_consent_request`` (fresh token + email) and on to
    # ``nominee_consent`` -- returning the process to awaiting the nominee's
    # response.
    follow_up_wait = flow.Function(
        this.follow_up_placeholder,
        task_loader=lambda flow_task, task: task,
        task_title=_("Awaiting Follow-up"),
    ).Next(this.send_consent_request)

    # --- End nodes ----------------------------------------------------------
    appointed = flow.End(
        task_title=_("Appointed"),
        task_result_summary=_("{{ process.nominee_display }} was appointed."),
    )
    closed = flow.End(
        task_title=_("Closed \u2014 Not Interested"),
        task_result_summary=_("Nominee declined; record retained."),
    )
    rejected = flow.End(
        task_title=_("Rejected"),
        task_result_summary=_("Nomination did not pass review; record retained."),
    )
    denied = flow.End(
        task_title=_("Denied"),
        task_result_summary=_("Appointment was not confirmed; record retained."),
    )

    # --- Handler implementations -------------------------------------------
    def send_consent_request_func(self, activation):
        """Issue a fresh tokenized consent link, email it, and record contact."""
        from .notifications import NomineeConsentNotification
        from .tokens import consent_link, issue_consent_token

        nomination = activation.process
        issue_consent_token(nomination)
        if nomination.nominee_email_address:
            NomineeConsentNotification(nomination, consent_link(nomination)).send()
        now = timezone.now()
        nomination.last_contacted = now
        nomination.last_activity = now
        nomination.save(update_fields=["last_contacted", "last_activity"])
        nomination.log_contact(
            kind="consent_request",
            subject="Consent request emailed",
            recipient=nomination.nominee_email_address or "",
        )

    def notify_vetting_passed_func(self, activation):
        from .services import notify_nominee_progress

        notify_nominee_progress(
            activation.process,
            "Your nomination has cleared reference and background review.",
            "The next step is a short interview; someone will be in touch to schedule it.",
        )

    def notify_interview_passed_func(self, activation):
        from .services import notify_nominee_progress

        notify_nominee_progress(
            activation.process,
            "Thanks for interviewing \u2014 you're moving on to required training.",
            "Please complete the required volunteer trainings so we can confirm your appointment.",
        )

    def notify_confirmed_func(self, activation):
        from .services import notify_nominee_progress

        notify_nominee_progress(
            activation.process,
            "You've been confirmed for a Theta Tau volunteer role.",
            "Central Office is now processing your appointment and will send your appointment letter.",
        )

    @method_decorator(flow.flow_func)
    def follow_up_placeholder(self, activation, task):
        """Parked wait node; advanced by the daily follow-up re-contact hook."""
        activation.prepare()
        activation.done()
        return activation

    def apply_appointment_func(self, activation):
        activation.process.appointed = True
        activation.process.save()

    def mark_rejected(self, activation):
        # Vetting / interview failure: send a "thank you, not at this time"
        # note. Record is retained and not_interested is deliberately NOT set.
        from .notifications import RejectionThankYouNotification

        nomination = activation.process
        if nomination.nominee_email_address:
            RejectionThankYouNotification(nomination).send()
        now = timezone.now()
        nomination.rejection_sent_at = now
        nomination.last_activity = now
        nomination.save(update_fields=["rejection_sent_at", "last_activity"])
        nomination.log_contact(
            kind="email",
            subject="Thank-you (not selected at this time)",
            recipient=nomination.nominee_email_address or "",
        )

    def mark_follow_up(self, activation):
        nomination = activation.process
        nomination.consent_status = _FOLLOW_UP
        nomination.last_activity = timezone.now()
        nomination.save()
