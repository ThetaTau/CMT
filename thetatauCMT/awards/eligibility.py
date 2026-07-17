"""Configurable eligibility engine for awards (AWI-4).

Combines the :class:`~thetatauCMT.awards.models.EligibilityRule` rows attached to
an award type -- member-status filters, chapter / region scope restrictions, an
explicit recipient-kind guard, and pluggable custom hooks -- together with the
acting user's role scope, to answer "who may receive this award?".

Extension point: register a custom check with :func:`register_eligibility_hook`
and reference it from a ``custom_hook`` rule's ``hook_key``. A hook is called as
``hook(queryset, award_type=?, cycle=?, actor=?, params=?)`` and returns a
(further-filtered) queryset of recipients.
"""

from core.models import ACTIVE_STATUSES, user_is_national_officer

from .models import EligibilityRule

# Map an EligibilityRule.MemberStatus value to the concrete User.current_status
# values that satisfy it.
MEMBER_STATUS_FILTERS = {
    EligibilityRule.MemberStatus.ACTIVE: list(ACTIVE_STATUSES),
    EligibilityRule.MemberStatus.ALUMNI: ["alumni", "alumniCC"],
    EligibilityRule.MemberStatus.PNM: ["pnm"],
}

# ---------------------------------------------------------------------------
# Pluggable hook registry (extension point)
# ---------------------------------------------------------------------------
_ELIGIBILITY_HOOKS = {}


def register_eligibility_hook(key):
    """Decorator: register a pluggable eligibility check under ``key``."""

    def decorator(func):
        _ELIGIBILITY_HOOKS[key] = func
        return func

    return decorator


def get_eligibility_hook(key):
    return _ELIGIBILITY_HOOKS.get(key)


# ---------------------------------------------------------------------------
# Recipient-kind helpers
# ---------------------------------------------------------------------------
def _base_queryset(kind):
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.models import User

    if kind == "member":
        return User.objects.all()
    if kind == "chapter":
        return Chapter.objects.all()
    if kind == "region":
        return Region.objects.all()
    raise ValueError(f"Unknown recipient kind: {kind}")


def _object_kind(recipient):
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.models import User

    if isinstance(recipient, User):
        return "member"
    if isinstance(recipient, Chapter):
        return "chapter"
    if isinstance(recipient, Region):
        return "region"
    return None


# ---------------------------------------------------------------------------
# Rule / hook / actor-scope application
# ---------------------------------------------------------------------------
def _apply_rules(queryset, kind, rules):
    # recipient-kind guard: if any recipient_kind rules list a kind (in params),
    # the award's kind must be among them or nothing is eligible.
    allowed_kinds = {
        r.params.get("kind")
        for r in rules
        if r.rule_type == EligibilityRule.RuleType.RECIPIENT_KIND and isinstance(r.params, dict) and r.params.get("kind")
    }
    if allowed_kinds and kind not in allowed_kinds:
        return queryset.none()

    # member-status filters (member recipients only)
    if kind == "member":
        statuses = set()
        for rule in rules:
            if rule.rule_type == EligibilityRule.RuleType.MEMBER_STATUS and rule.member_status:
                statuses.update(MEMBER_STATUS_FILTERS.get(rule.member_status, []))
        if statuses:
            queryset = queryset.filter(current_status__in=statuses)

    # chapter-scope restrictions
    chapter_ids = []
    for rule in rules:
        if rule.rule_type == EligibilityRule.RuleType.CHAPTER_SCOPE:
            chapter_ids.extend(rule.chapters.values_list("pk", flat=True))
    if chapter_ids:
        if kind == "member":
            queryset = queryset.filter(chapter_id__in=chapter_ids)
        elif kind == "chapter":
            queryset = queryset.filter(pk__in=chapter_ids)

    # region-scope restrictions
    region_ids = []
    for rule in rules:
        if rule.rule_type == EligibilityRule.RuleType.REGION_SCOPE:
            region_ids.extend(rule.regions.values_list("pk", flat=True))
    if region_ids:
        if kind == "member":
            queryset = queryset.filter(chapter__region_id__in=region_ids)
        elif kind == "chapter":
            queryset = queryset.filter(region_id__in=region_ids)
        elif kind == "region":
            queryset = queryset.filter(pk__in=region_ids)

    return queryset


def _apply_hooks(queryset, rules, award_type, cycle, actor):
    for rule in rules:
        if rule.rule_type != EligibilityRule.RuleType.CUSTOM_HOOK or not rule.hook_key:
            continue
        hook = get_eligibility_hook(rule.hook_key)
        if hook is None:
            continue
        queryset = hook(queryset, award_type=award_type, cycle=cycle, actor=actor, params=rule.params or {})
    return queryset


def _apply_actor_scope(queryset, kind, actor):
    """Narrow ``queryset`` to what ``actor`` has authority over.

    National officers / admins: unrestricted. Regional directors: their
    region(s). Everyone else (chapter officers / members): their own chapter.
    """
    if actor is None or user_is_national_officer(actor):
        return queryset
    regions = list(getattr(actor, "director_regions", []) or [])
    if regions:
        region_ids = [region.pk for region in regions]
        if kind == "member":
            return queryset.filter(chapter__region_id__in=region_ids)
        if kind == "chapter":
            return queryset.filter(region_id__in=region_ids)
        if kind == "region":
            return queryset.filter(pk__in=region_ids)
    chapter = getattr(actor, "current_chapter", None)
    if chapter is None:
        return queryset.none()
    if kind == "member":
        return queryset.filter(chapter_id=chapter.pk)
    if kind == "chapter":
        return queryset.filter(pk=chapter.pk)
    return queryset.none()  # region award; a chapter-scoped actor has no authority


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_eligible_recipients(award_type, cycle=None, actor=None):
    """Return a queryset of recipients eligible for ``award_type``.

    Combines every :class:`EligibilityRule` on the award with the ``actor``'s
    role scope. ``cycle`` is forwarded to custom hooks. Pass ``actor=None`` for
    an unrestricted (system) check.
    """
    kind = award_type.recipient_kind
    rules = list(award_type.eligibility_rules.all().prefetch_related("chapters", "regions"))
    queryset = _base_queryset(kind)
    queryset = _apply_rules(queryset, kind, rules)
    queryset = _apply_hooks(queryset, rules, award_type, cycle, actor)
    queryset = _apply_actor_scope(queryset, kind, actor)
    return queryset.distinct()


def is_eligible(award_type, recipient, cycle=None, actor=None):
    """Whether ``recipient`` (a User / Chapter / Region) is eligible for the award.

    Returns ``False`` immediately when the recipient's kind does not match the
    award's level-derived recipient kind.
    """
    if _object_kind(recipient) != award_type.recipient_kind:
        return False
    return get_eligible_recipients(award_type, cycle=cycle, actor=actor).filter(pk=recipient.pk).exists()
