"""Service helpers for the awards app.

Currently focused on AWI-2: resolving the current award cycle and enforcing the
per-cycle winner / nomination rules that are configured on
:class:`~thetatauCMT.awards.models.AwardType`. The winner / nomination counts
are supplied by the caller; they are wired to real ``AwardGrant`` counts once
grants land in AWI-3.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import resolve_config_actor, user_is_national_officer

from .eligibility import is_eligible
from .models import AwardCycle, AwardGrant, AwardNominationProcess, AwardType, GrantAudit
from .signals import award_granted

SINGLE_WINNER_MSG = "This award allows only one winner per cycle; a winner already exists for this cycle."
MULTIPLE_NOMINATION_MSG = "This award does not allow multiple nominations for the same recipient in a cycle."
GRANT_METHOD_NOT_DIRECT_MSG = "This award is not configured for direct granting."
NOT_ELIGIBLE_MSG = "The selected recipient is not eligible for this award, or is outside your scope."


def resolve_current_cycle(on_date=None, period_type=None):
    """Return the :class:`AwardCycle` in effect on ``on_date`` (default: today).

    When several cycles are active at once, the one with the most recent
    ``start_date`` wins. ``period_type`` narrows the search to a single kind of
    period (year / term / event). Returns ``None`` when no cycle is active.
    """
    cycles = AwardCycle.objects.current(on_date)
    if period_type:
        cycles = cycles.filter(period_type=period_type)
    return cycles.first()


def check_winner_allowed(award_type, current_winner_count):
    """Raise :class:`ValidationError` when granting another winner would break
    the award's single-winner-per-cycle rule.

    ``current_winner_count`` is the number of existing winners in the target
    cycle.
    """
    if not award_type.can_add_winner(current_winner_count):
        raise ValidationError(SINGLE_WINNER_MSG)


def check_nomination_allowed(award_type, existing_nomination_count):
    """Raise :class:`ValidationError` when the recipient already has a
    nomination in the cycle and the award does not allow multiple nominations.
    """
    if not award_type.can_add_nomination(existing_nomination_count):
        raise ValidationError(MULTIPLE_NOMINATION_MSG)


def _recipient_kwargs(recipient):
    """Map a recipient object to the matching ``AwardGrant`` recipient FK kwarg."""
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.models import User

    if isinstance(recipient, User):
        return {"recipient_member": recipient}
    if isinstance(recipient, Chapter):
        return {"recipient_chapter": recipient}
    if isinstance(recipient, Region):
        return {"recipient_region": recipient}
    raise ValueError(f"Unsupported award recipient type: {type(recipient).__name__}")


def write_grant_audit(grant, action, actor=None, detail=None):
    """Append a :class:`GrantAudit` row (the append-only history for a grant)."""
    return GrantAudit.objects.create(grant=grant, action=action, actor=actor, detail=detail or {})


@transaction.atomic
def grant_award(award_type, cycle, recipient, granted_by, *, effective_date=None, reason="", source=None):
    """Create and return a single :class:`AwardGrant`.

    ``recipient`` is a ``User`` / ``Chapter`` / ``Region``; the matching
    ``recipient_*`` FK is populated. ``effective_date`` may be backdated (it
    defaults to today) while ``granted_at`` stays the real system time. Writes a
    ``created`` (or ``imported``) audit entry in the same transaction.
    """
    source = source or AwardGrant.Source.DIRECT
    grant = AwardGrant(
        award_type=award_type,
        cycle=cycle,
        granted_by=granted_by,
        effective_date=effective_date or timezone.now().date(),
        reason=reason,
        source=source,
        **_recipient_kwargs(recipient),
    )
    grant.save()
    action = GrantAudit.Action.IMPORTED if source == AwardGrant.Source.IMPORT else GrantAudit.Action.CREATED
    write_grant_audit(
        grant,
        action,
        actor=granted_by,
        detail={
            "award_type": str(award_type),
            "cycle": str(cycle),
            "recipient": grant.recipient_display,
            "recipient_kind": grant.recipient_kind,
            "effective_date": grant.effective_date.isoformat(),
            "source": source,
        },
    )
    return grant


def grant_award_to_members(award_type, cycle, members, granted_by, *, effective_date=None, reason="", source=None):
    """Create one identical :class:`AwardGrant` per member in ``members``.

    Used for group awards: every member receives their own individual grant.
    Returns the list of created grants.
    """
    return [
        grant_award(award_type, cycle, member, granted_by, effective_date=effective_date, reason=reason, source=source)
        for member in members
    ]


@transaction.atomic
def revoke_grant(grant, revoked_by, reason=""):
    """Revoke ``grant`` -- never deletes it.

    Sets ``status=revoked`` plus who / when / why and writes a ``revoked`` audit
    entry. Idempotent: a no-op (no duplicate audit) on an already-revoked grant.
    """
    if grant.is_revoked:
        return grant
    grant.status = AwardGrant.Status.REVOKED
    grant.revoked_by = revoked_by
    grant.revoked_at = timezone.now()
    grant.revoke_reason = reason
    grant.save(update_fields=["status", "revoked_by", "revoked_at", "revoke_reason", "modified"])
    write_grant_audit(grant, GrantAudit.Action.REVOKED, actor=revoked_by, detail={"reason": reason})
    return grant


def count_active_winners(award_type, cycle):
    """Number of active (non-revoked) grants of ``award_type`` within ``cycle``.

    Bridges the AWI-2 winner rules to real grants -- pass this to
    :func:`check_winner_allowed` before granting another winner.
    """
    return AwardGrant.objects.active().for_cycle(award_type, cycle).count()


def can_grant_awards(user):
    """Whether ``user`` may use the direct-grant path at all.

    Any officer qualifies: National Officers / Admins, chapter officers, or
    Regional Directors. Recipient-level scope is still enforced per grant by the
    eligibility engine (see :func:`direct_grant`).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user_is_national_officer(user):
        return True
    if getattr(user, "is_chapter_officer_group", False):
        return True
    return bool(list(getattr(user, "director_regions", []) or []))


@transaction.atomic
def direct_grant(award_type, cycle, recipient, granted_by, *, effective_date=None, reason=""):
    """Grant a direct award to a single recipient, enforcing all rules.

    Validates that the award is direct-grantable, that ``recipient`` is eligible
    AND within ``granted_by``'s scope (AWI-4), and that the per-cycle winner
    rules hold (AWI-2). Creates an ``AwardGrant(source=direct)`` and fires the
    :data:`award_granted` signal (the AWI-8 certificate / AWI-9 notification
    extension point).
    """
    if award_type.grant_method != AwardType.GrantMethod.DIRECT:
        raise ValidationError(GRANT_METHOD_NOT_DIRECT_MSG)
    if not is_eligible(award_type, recipient, cycle=cycle, actor=granted_by):
        raise ValidationError(NOT_ELIGIBLE_MSG)
    check_winner_allowed(award_type, count_active_winners(award_type, cycle))
    grant = grant_award(
        award_type,
        cycle,
        recipient,
        granted_by,
        effective_date=effective_date,
        reason=reason,
        source=AwardGrant.Source.DIRECT,
    )
    award_granted.send(sender=AwardGrant, grant=grant, actor=granted_by)
    return grant


def allowed_nominator_scopes(actor):
    """The set of nominator scopes ``actor`` may use, hierarchically by role.

    Everyone may nominate for member-scope awards; officers additionally for
    officer-scope awards; National Officers / Admins for all three scopes.
    """
    scopes = {AwardType.NominatorScope.MEMBER.value}
    if actor is None or not getattr(actor, "is_authenticated", False):
        return scopes
    if user_is_national_officer(actor):
        scopes.update({AwardType.NominatorScope.OFFICER.value, AwardType.NominatorScope.NATIONAL.value})
    elif getattr(actor, "is_chapter_officer_group", False) or bool(list(getattr(actor, "director_regions", []) or [])):
        scopes.add(AwardType.NominatorScope.OFFICER.value)
    return scopes


def nominatable_award_types(actor):
    """Active nomination-workflow awards whose ``nominator_scope`` overlaps the
    scopes ``actor``'s role may use (drives the per-role nomination award list).
    """
    scopes = allowed_nominator_scopes(actor)
    base = AwardType.objects.active().filter(grant_method=AwardType.GrantMethod.NOMINATION_WORKFLOW)
    ids = [award.pk for award in base if set(award.nominator_scope) & scopes]
    return AwardType.objects.filter(pk__in=ids)


def count_nominations_for(award_type, cycle, recipient):
    """Number of non-rejected nominations of ``award_type`` in ``cycle`` for
    ``recipient`` -- feeds the per-cycle multiple-nomination rule.
    """
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.models import User

    if isinstance(recipient, User):
        field = "recipient_member"
    elif isinstance(recipient, Chapter):
        field = "recipient_chapter"
    elif isinstance(recipient, Region):
        field = "recipient_region"
    else:
        return 0
    return (
        AwardNominationProcess.objects.filter(award_type=award_type, cycle=cycle, **{field: recipient})
        .exclude(result=AwardNominationProcess.Result.REJECTED)
        .count()
    )


# Base configs key for the nomination approver; ``AwardApprover:<level>`` is
# tried first, then the bare ``AwardApprover`` key.
AWARD_APPROVER_CONFIG = "AwardApprover"


def get_award_approver(award_type):
    """Resolve the config-driven approver for a nomination of ``award_type``.

    Looks up ``AwardApprover:<level>`` then ``AwardApprover`` in the configs
    table (value = username / email OR a national-officer role name), finally
    falling back to ``settings.EXECUTIVE_DIRECTOR``. Returns ``None`` when
    unresolved (viewflow then leaves the review task unassigned).
    """
    from thetatauCMT.configs.models import Config

    for key in (f"{AWARD_APPROVER_CONFIG}:{award_type.level}", AWARD_APPROVER_CONFIG):
        user = resolve_config_actor(Config.get_value(key))
        if user is not None:
            return user
    executive_director = getattr(settings, "EXECUTIVE_DIRECTOR", None)
    if executive_director:
        return resolve_config_actor(executive_director)
    return None


@transaction.atomic
def grant_from_nomination(nomination, approver):
    """Create the ``AwardGrant`` for an approved nomination (source=nomination).

    Fires the :data:`award_granted` signal (the AWI-8 certificate / AWI-9
    notification hook), mirroring :func:`direct_grant`.
    """
    grant = grant_award(
        nomination.award_type,
        nomination.cycle,
        nomination.recipient,
        approver,
        reason=nomination.justification,
        source=AwardGrant.Source.NOMINATION,
    )
    award_granted.send(sender=AwardGrant, grant=grant, actor=approver)
    return grant
