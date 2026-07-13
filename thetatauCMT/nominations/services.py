"""Service helpers for the nominations flow.

Kept separate so the tokenized consent view (an external, non-logged-in actor)
can drive the viewflow task without importing the flow at module load time
(which would create an import cycle: flows -> views -> services -> flows).
"""

from django.utils import timezone
from viewflow.activation import STATUS
from viewflow.models import Task


def _active_consent_task(nomination):
    from .flows import NominationFlow  # local import breaks the import cycle

    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.nominee_consent,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


def has_active_consent_task(nomination):
    """Whether the nomination is still waiting for the nominee's consent."""
    return _active_consent_task(nomination) is not None


def complete_consent_task(nomination):
    """Complete the waiting ``nominee_consent`` task, advancing the flow.

    Returns the completed task, or ``None`` when there is no active consent task
    (already responded / process moved on).
    """
    task = _active_consent_task(nomination)
    if task is None:
        return None
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    nomination.log_contact(
        kind="response",
        subject=f"Nominee responded: {nomination.get_consent_status_display()}",
        recipient=nomination.nominee_email_address or "",
        notes=nomination.consent_notes or "",
    )
    return task


def _follow_up_wait_task(nomination):
    from .flows import NominationFlow  # local import breaks the import cycle

    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.follow_up_wait,
        status=STATUS.NEW,
    ).first()


def _active_training_task(nomination):
    from .flows import NominationFlow

    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.training,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


def has_active_training_task(nomination):
    return _active_training_task(nomination) is not None


def mark_training_complete(nomination, training_key, completed_by=None, provider=None):
    """Mark one required training complete via the provider; advance the flow to
    confirmation only when BOTH required trainings are complete.

    Callable from the manual mark-complete view OR a future LMS/Vector webhook.
    Returns ``True`` when the flow advanced (both complete), ``False`` otherwise.
    """
    from .providers import get_training_provider

    provider = provider or get_training_provider()
    provider.mark_complete(nomination, training_key, completed_by=completed_by)
    nomination.refresh_from_db()
    if not provider.all_required_complete(nomination):
        return False
    if not nomination.training_completed:
        nomination.training_completed = True
        nomination.save(update_fields=["training_completed"])
    task = _active_training_task(nomination)
    if task is None:
        return False
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    notify_nominee_progress(
        nomination,
        "You've completed the required volunteer training.",
        "Your nomination is now with Central Office for final confirmation.",
    )
    return True


def _active_appointment_task(nomination):
    from .flows import NominationFlow

    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.appointment,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


def has_active_appointment_task(nomination):
    return _active_appointment_task(nomination) is not None


def appointment_checklist(nomination):
    """The five appointment checklist items and whether each is done (VWI-9)."""
    return {
        "letter_uploaded": bool(nomination.appointment_letter),
        "letter_emailed": nomination.appointment_letter_sent_at is not None,
        "chapters_notified": nomination.chapters_notified,
        "ppm_ordered": nomination.ppm_ordered,
        "added_to_natoff_lists": nomination.added_to_natoff_lists,
    }


def appointment_complete(nomination):
    return all(appointment_checklist(nomination).values())


def add_to_natoff_lists(nomination):
    """Add the appointee to the existing natoff list (Django ``natoff`` group)."""
    from django.contrib.auth.models import Group

    if nomination.nominee_id:
        group, _created = Group.objects.get_or_create(name="natoff")
        group.user_set.add(nomination.nominee)
    nomination.added_to_natoff_lists = True
    nomination.save(update_fields=["added_to_natoff_lists"])


def try_complete_appointment(nomination):
    """Complete the appointment task (-> End appointed) once every checklist
    item is done. Returns True when the flow advanced."""
    if not appointment_complete(nomination):
        return False
    task = _active_appointment_task(nomination)
    if task is None:
        return False
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    return True


def chapter_notification_recipients(nomination):
    """Emails of the affected chapter / region for an appointment notification."""
    recipients = []
    nominee = nomination.nominee
    if nominee is not None and getattr(nominee, "chapter", None) is not None:
        chapter = nominee.chapter
        if chapter.email:
            recipients.append(chapter.email)
        region = getattr(chapter, "region", None)
        if region is not None and region.email:
            recipients.append(region.email)
    return recipients


def _active_denial_task(nomination):
    from .flows import NominationFlow

    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.denial_central_office,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


def has_active_denial_task(nomination):
    return _active_denial_task(nomination) is not None


def try_complete_denial(nomination):
    """Complete the CentralOffice denial task (-> End denied) once the denial
    letter is uploaded AND emailed. Returns True when the flow advanced."""
    if not (nomination.denial_letter and nomination.denial_letter_sent_at):
        return False
    task = _active_denial_task(nomination)
    if task is None:
        return False
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    return True


def is_awaiting_follow_up(nomination):
    """Whether the nomination is parked awaiting a follow-up re-contact."""
    return _follow_up_wait_task(nomination) is not None


def nominations_awaiting_follow_up(before=None):
    """Nominations parked awaiting follow-up, optionally only those last
    contacted on/before ``before`` (used by the daily follow-up command).
    """
    from .flows import NominationFlow
    from .models import Nomination

    process_ids = Task.objects.filter(
        flow_task=NominationFlow.follow_up_wait,
        status=STATUS.NEW,
    ).values_list("process_id", flat=True)
    queryset = Nomination.objects.filter(pk__in=list(process_ids), finished__isnull=True)
    if before is not None:
        queryset = queryset.filter(last_contacted__lte=before)
    return queryset


def recontact_nomination(nomination):
    """Re-issue the consent link (fresh token + email) and return the process
    to awaiting the nominee's response.

    This is the hook the daily follow-up command (VWI-12) calls for nominations
    parked awaiting follow-up. Advancing the parked ``follow_up_wait`` task loops
    the flow back through ``send_consent_request`` (which rotates the token,
    re-sends the email, and stamps ``last_contacted``) to ``nominee_consent``.

    Returns ``True`` when a re-contact happened, ``False`` otherwise.
    """
    from .flows import NominationFlow

    task = _follow_up_wait_task(nomination)
    if task is None:
        return False
    NominationFlow.follow_up_wait.run(task)
    return True


def nominations_awaiting_response(before=None):
    """Nominations still waiting for the nominee's first/consent response
    (parked at ``nominee_consent``), optionally only those last contacted
    on/before ``before``. Excludes declined / finished records.
    """
    from .flows import NominationFlow
    from .models import Nomination

    process_ids = Task.objects.filter(
        flow_task=NominationFlow.nominee_consent,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).values_list("process_id", flat=True)
    queryset = Nomination.objects.filter(pk__in=list(process_ids), finished__isnull=True, not_interested=False)
    if before is not None:
        queryset = queryset.filter(last_contacted__lte=before)
    return queryset


def resend_consent_request(nomination):
    """Reissue the consent token + email for a nomination still awaiting the
    nominee's response, WITHOUT advancing the flow. Updates ``last_contacted``
    so the daily command re-fires only after the next interval.

    Returns ``True`` when a resend happened.
    """
    from .notifications import NomineeConsentNotification
    from .tokens import consent_link, issue_consent_token

    if not has_active_consent_task(nomination):
        return False
    issue_consent_token(nomination)
    if nomination.nominee_email_address:
        NomineeConsentNotification(nomination, consent_link(nomination)).send()
    nomination.last_contacted = timezone.now()
    nomination.save(update_fields=["last_contacted"])
    nomination.log_contact(
        kind="consent_request",
        subject="Consent request re-sent",
        recipient=nomination.nominee_email_address or "",
    )
    return True


def get_follow_up_interval_months(default=6):
    """The re-contact interval in months, from the config system (VWI-1)."""
    from thetatauCMT.configs.models import Config

    raw = Config.get_value("follow_up_interval_months")
    try:
        value = int(str(raw).strip())
        return value if value > 0 else default
    except (ValueError, TypeError):
        return default


def notify_nominee_progress(nomination, headline, message="", kind="progress"):
    """Email the nominee a progress update AND record the contact (WI #9/#12).

    Sending is best-effort (skipped when we have no nominee email); the contact
    is always logged so the nomination admin shows the full communication trail.
    """
    from .notifications import NominationProgressNotification

    if nomination.nominee_email_address:
        NominationProgressNotification(nomination, headline, message).send()
    nomination.log_contact(
        kind=kind,
        subject=headline,
        recipient=nomination.nominee_email_address or "",
        notes=message,
    )
