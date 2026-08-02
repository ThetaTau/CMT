"""Visibility rules for the feature catalog (TWI-3).

Every catalog, role-guide and What's-New surface asks this module what a
user may see. Keeping the rules here -- rather than in each view or template --
is what stops the catalog from advertising a page the viewer would be bounced
off of.

Two impersonation mechanisms must survive every change in this file:

``natoff_hidden``
    A National Officer can toggle "hide national officer functionality" to
    preview the site as a member. The toggle-aware properties
    (:attr:`User.is_national_officer_group`, :attr:`User.is_officer_group`) and
    :func:`core.models.user_is_national_officer` all respect it. The raw
    ``in_national_officer_group`` does **not** -- never use it here.

``UserAlter``
    A National Officer can impersonate another chapter and role.
    ``User.current_chapter`` and ``User.chapter_officer()`` already apply the
    alteration, so use those instead of ``user.chapter`` / ``user.current_roles``.
"""

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import constants as message_constants
from django.db import IntegrityError
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.models import ALL_ROLES, NAT_OFFICERS, user_is_national_officer
from thetatauCMT.configs.models import Config
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate

from .models import Audience, Feature, FeatureArea, RoleGuide, UserAcknowledgement

#: The two kinds of thing the What's New feed carries.
KIND_ANNOUNCEMENT = "announcement"
KIND_FEATURE = "feature"
FEED_KINDS = (KIND_ANNOUNCEMENT, KIND_FEATURE)

#: Set once the modal has been shown -- or once we know there is nothing to
#: show -- so the feed costs at most one round of queries per session.
WHATS_NEW_SESSION_KEY = "whats_new_seen"

#: Path prefixes the unprompted modal never interrupts, on top of
#: ``settings.TERMS_EXCLUDE_URL_LIST``. ``/workflow/`` is Viewflow's task UI.
MODAL_EXCLUDED_PREFIXES = ("/workflow/", "/accounts/", "/account/", "/admin/", "/terms/")

#: Audiences in increasing privilege. A user sees an entry when the entry's
#: audience ranks no higher than their own.
AUDIENCE_RANK = {
    Audience.PUBLIC: 0,
    Audience.MEMBER: 1,
    Audience.OFFICER: 2,
    Audience.NATOFF: 3,
}


def _is_authenticated(user):
    return user is not None and getattr(user, "is_authenticated", False)


def user_audience(user):
    """The highest :class:`~thetatauCMT.guides.models.Audience` ``user`` satisfies.

    Superusers map to ``natoff`` -- there is no separate superuser audience,
    because superuser-only tooling is excluded from the catalog. A National
    Officer previewing as a member drops to whatever they would see with the
    toggle on, which is the point of the toggle.
    """
    if not _is_authenticated(user):
        return Audience.PUBLIC
    # Subsumes superuser, natoff group membership and national-officer roles,
    # and already returns False while "view as member" is on.
    if user_is_national_officer(user):
        return Audience.NATOFF
    if user.is_officer_group:
        return Audience.OFFICER
    return Audience.MEMBER


def _audience_allows(viewer_audience, entry_audience):
    return AUDIENCE_RANK.get(entry_audience, AUDIENCE_RANK[Audience.NATOFF]) <= AUDIENCE_RANK[viewer_audience]


class _FlagCache:
    """Memoizes ``Config.feature_enabled`` so filtering a list of entries costs
    one query per distinct flag rather than one per entry."""

    def __init__(self):
        self._known = {}

    def enabled(self, key):
        if not key:
            return True
        if key not in self._known:
            self._known[key] = Config.feature_enabled(key)
        return self._known[key]


def get_visible_areas(user):
    """Active areas whose audience and feature flag admit ``user``."""
    viewer_audience = user_audience(user)
    allowed = [audience for audience in Audience.values if _audience_allows(viewer_audience, audience)]
    areas = FeatureArea.objects.active().filter(audience__in=allowed)
    flags = _FlagCache()
    return [area for area in areas if flags.enabled(area.feature_flag)]


def get_visible_features(user, area=None):
    """Active features ``user`` may see, optionally limited to one ``area``.

    A feature's blank ``audience`` / ``feature_flag`` inherit the area's, so both
    are read through the model's ``effective_*`` properties.
    """
    viewer_audience = user_audience(user)
    features = Feature.objects.active().select_related("area", "task")
    if area is not None:
        features = features.filter(area=area)
    flags = _FlagCache()
    return [
        feature
        for feature in features
        if _audience_allows(viewer_audience, feature.effective_audience)
        and flags.enabled(feature.effective_feature_flag)
    ]


def _resolve_url_token(token, user):
    """Value for a ``@token`` in ``url_kwargs``, or ``None`` if unavailable.

    Chapter and region are non-nullable, so the only real miss is an anonymous
    viewer. A slug that is somehow unset still fails safely -- it produces a
    ``NoReverseMatch`` that :func:`resolve_feature_url` catches.
    """
    if not _is_authenticated(user):
        return None
    if token == "@username":
        return user.username
    if token == "@chapter_slug":
        return user.current_chapter.slug
    if token == "@region_slug":
        return user.current_chapter.region.slug
    return None


def resolve_feature_url(feature, user):
    """The link for a feature's card, or ``None`` to render it unlinked.

    Never raises: an unknown token, an anonymous viewer, and a ``url_name`` that
    does not reverse all fall back to ``None``.
    """
    if feature.external_url:
        return feature.external_url
    if not feature.url_name:
        return None
    kwargs = {}
    for name, value in (feature.url_kwargs or {}).items():
        if isinstance(value, str) and value.startswith("@"):
            value = _resolve_url_token(value, user)
            if value is None:
                return None
        kwargs[name] = value
    try:
        url = reverse(feature.url_name, kwargs=kwargs)
    except NoReverseMatch:
        return None
    return f"{url}#{feature.url_fragment}" if feature.url_fragment else url


def get_duty_roles(user):
    """The duty roles ``user`` is responsible for, as a set of `ALL_ROLES` values.

    This is targeting information ("this is a Treasurer thing"), not permission
    -- a risk management chair is a plain member for access purposes.
    """
    if not _is_authenticated(user):
        return set()
    roles = set(user.chapter_officer()) | set(user.current_roles or [])
    return roles & set(ALL_ROLES)


#: Officer order for the "who submits it" chips. ``ALL_ROLES`` is alphabetical,
#: which would lead with Corresponding Secretary; chapters read their officers in
#: this order. Anything not listed sorts alphabetically after these five.
OFFICER_ORDER = ("regent", "vice regent", "scribe", "treasurer", "corresponding secretary")


def _role_sort_key(role):
    return (OFFICER_ORDER.index(role) if role in OFFICER_ORDER else len(OFFICER_ORDER), role)


def _task_owner_roles(features):
    """Map ``task_id`` -> every officer who owes that task, in two queries.

    A task is one row per *owner*, so the Audit is five ``Task`` rows sharing a
    name. A feature can only link one of them, which would otherwise advertise
    the Audit as a Treasurer job. Look the name up and take every owner of it.
    """
    task_ids = {feature.task_id for feature in features if feature.task_id}
    if not task_ids:
        return {}
    names = dict(Task.objects.filter(id__in=task_ids).values_list("id", "name"))
    owners = defaultdict(set)
    for name, owner in Task.objects.filter(name__in=set(names.values())).values_list("name", "owner"):
        owners[name].add(owner)
    return {task_id: owners[name] for task_id, name in names.items()}


def feature_roles(feature, task_owners=None):
    """Who submits this feature: its own roles plus every owner of its task.

    ``feature.roles`` stays the hand-authored part -- it carries the roles a task
    cannot express, such as the Risk Management Chair who prepares the H&S
    programme the Regent formally owes.
    """
    roles = set(feature.roles or [])
    if task_owners is not None:
        roles |= task_owners.get(feature.task_id, set())
    return sorted(roles, key=_role_sort_key)


# ---------------------------------------------------------------------------
# Catalog page (TWI-9)
# ---------------------------------------------------------------------------


def get_catalog(user, now=None):
    """Everything ``/features/`` renders, grouped by area, in a fixed number of queries.

    Returns a list of ``{"area", "features"}`` dicts in area
    order, where each entry of ``features`` is
    ``{"feature", "url", "is_new", "roles", "duty_roles"}``.

    Deliberately *not* built from :func:`get_new_features` or a per-card call to
    :func:`resolve_feature_url` inside the template: both would re-run the
    visibility query, and the catalog renders every feature the viewer can see.
    Areas with nothing visible in them are dropped rather than rendered as an
    empty heading.

    ``is_new`` intentionally reuses the What's New rule -- released within
    ``settings.NEW_FEATURE_MAX_AGE_DAYS`` *and* not yet acknowledged -- so
    clicking "Got it" in the modal also clears the badge here. One lifecycle,
    not two.
    """
    now = now or timezone.now()
    cutoff = (now - timedelta(days=settings.NEW_FEATURE_MAX_AGE_DAYS)).date()
    areas = get_visible_areas(user)
    features = get_visible_features(user)
    task_owners = _task_owner_roles(features)
    duty_roles = get_duty_roles(user) if any(feature.roles or feature.task_id for feature in features) else set()
    acknowledged = _acknowledged_ids(user, Feature) if features else set()

    by_area = defaultdict(list)
    for feature in features:
        roles = feature_roles(feature, task_owners)
        by_area[feature.area_id].append(
            {
                "feature": feature,
                "url": resolve_feature_url(feature, user),
                "is_new": (
                    feature.released_at is not None and feature.released_at >= cutoff and feature.id not in acknowledged
                ),
                "roles": roles,
                "duty_roles": sorted(set(roles) & duty_roles, key=_role_sort_key),
            }
        )
    return [
        {
            "area": area,
            "features": by_area[area.id],
        }
        for area in areas
        if by_area[area.id]
    ]


def get_feature_groups(user, groups, fallback_area_key=""):
    """Registry entries arranged into purpose groups for a landing page (TWI-9b).

    ``groups`` is a list of ``{"key", "label", "description", "features"}`` where
    ``features`` names registry keys in display order. Anything visible in
    ``fallback_area_key`` that no group claims is appended under "Everything
    else", so adding a registry entry can never make a form silently vanish from
    the page that has always listed it.

    Each entry gains ``due`` and ``cadence`` from the linked ``tasks.Task``, for
    the *viewer's own chapter*, in two queries for the whole page.
    """
    entries = {}
    for block in get_catalog(user):
        for entry in block["features"]:
            entries[entry["feature"].key] = entry

    claimed = set()
    result = []
    for group in groups:
        chosen = [entries[key] for key in group["features"] if key in entries]
        claimed.update(group["features"])
        if chosen:
            result.append({**group, "entries": chosen})
    if fallback_area_key:
        leftovers = [
            entry
            for entry in entries.values()
            if entry["feature"].area.key == fallback_area_key and entry["feature"].key not in claimed
        ]
        if leftovers:
            result.append(
                {
                    "key": "other",
                    "label": "Everything else",
                    "description": "Forms that do not fit the groups above.",
                    "features": [],
                    "entries": leftovers,
                }
            )
    _attach_task_schedule(result, user)
    return result


def _attach_task_schedule(groups, user):
    """Set ``due`` and ``cadence`` on every entry, in a fixed number of queries.

    A per-card call to :meth:`Task.incomplete_dates_for_task_chapter` would be
    one query per row; the forms landing has around forty. Both facts come from
    the same ``TaskDate`` fetch instead.

    Dates are read across every ``Task`` row sharing the linked task's name, so
    the Audit reports the same deadline whichever officer's row a feature
    happens to point at. A date counts as outstanding until *every* officer who
    owes it has closed it out.
    """
    entries = [entry for group in groups for entry in group["entries"]]
    for entry in entries:
        entry["due"] = None
        entry["cadence"] = ""
    chapter = getattr(user, "current_chapter", None)
    linked = {entry["feature"].task_id for entry in entries if entry["feature"].task_id}
    if chapter is None or not linked:
        return

    # One feature links one Task row, but the obligation is the whole name.
    names = dict(Task.objects.filter(id__in=linked).values_list("id", "name"))
    siblings = defaultdict(set)
    for task_id, name in Task.objects.filter(name__in=set(names.values())).values_list("id", "name"):
        siblings[name].add(task_id)
    task_ids = {task_id for group in siblings.values() for task_id in group}

    rows = TaskDate.objects.filter(
        Q(school_type=chapter.school_type) | Q(school_type="all"),
        task_id__in=task_ids,
    ).values_list("id", "task_id", "date", "archived")
    # ``TaskChapter.task`` points at a TaskDate, so this is the set of dates this
    # chapter has already closed out.
    done = set(
        TaskChapter.objects.filter(chapter=chapter, task__task_id__in=task_ids).values_list("task_id", flat=True)
    )

    today = timezone.now().date()
    horizon = today - timedelta(days=90)
    by_task = defaultdict(list)
    for date_id, task_id, day, archived in rows:
        by_task[task_id].append((date_id, day, archived))

    schedule = {}
    for name, group in siblings.items():
        dates = [row for task_id in group for row in by_task[task_id]]
        outstanding = sorted(
            day for date_id, day, archived in dates if not archived and date_id not in done and day >= horizon
        )
        # How often, not how many: count the distinct day-of-year the task falls
        # on across every year on record. Counting this calendar year's rows
        # instead would report a yearly task as never once its date had passed
        # and been archived, and would count five owners' identical rows five
        # times. These recurrences come from ``tasks/.../date_data.csv``.
        recurrences = len({(day.month, day.day) for _, day, _ in dates})
        schedule[name] = {
            "due": outstanding[0] if outstanding else None,
            "cadence": "Every term" if recurrences > 1 else ("Once a year" if recurrences == 1 else ""),
        }
    for entry in entries:
        name = names.get(entry["feature"].task_id)
        if name is not None:
            entry.update(schedule[name])


#: The guide every National Officer gets, whatever their particular office.
#: The national surface is audience-gated rather than role-tagged, and there are
#: eighteen roles in ``NAT_OFFICERS`` -- one guide for the audience beats
#: eighteen near-identical ones, and beats a Grand Regent having none at all.
NATIONAL_GUIDE_ROLE = "national officer"


def get_role_guides(user):
    """Active :class:`RoleGuide` rows for the duty roles ``user`` holds (TWI-12).
    Ordered by the guides' own ``order``, so a Regent who is also Risk Management
    Chair sees the more senior office first. Returns ``[]`` for a member with no
    duty role rather than every guide -- the index page is what lists them all.

    Anyone *currently acting as* a National Officer also gets
    :data:`NATIONAL_GUIDE_ROLE`, whether or not that is one of their roles. A
    National Officer previewing as a member loses it again, because
    :func:`user_audience` already respects the toggle.
    """
    duty_roles = get_duty_roles(user)
    if user_audience(user) == Audience.NATOFF:
        duty_roles = duty_roles | {NATIONAL_GUIDE_ROLE}
    if not duty_roles:
        return []
    return list(RoleGuide.objects.active().filter(role__in=duty_roles))


def get_role_guide_detail(guide, user):
    """The blocks a role guide page renders.

    * ``open_items`` -- live ``TaskDate`` rows for this role and *the viewer's own
      chapter*, straight from :meth:`TaskDate.incomplete_dates_for_chapter`, so
      the table matches the home page rather than inventing a second definition
      of "overdue". ``archived`` rows are already excluded there.
    * ``steps`` -- the guide's own copy, with any step pointing at a feature the
      viewer cannot see dropped. Advertising a page that would bounce them is
      worse than a shorter list.
    * ``tools`` -- catalog features belonging to this role, so a new officer can
      see the whole surface without reading the catalog end to end. Membership
      is :func:`feature_roles`, not the raw ``roles`` field, so a duty carried by
      a ``tasks.Task`` -- the Audit, which five officers owe -- lands on all five
      guides rather than only the one the registry entry happens to link.
    * ``national_tools`` -- for a national office, everything else gated to
      National Officers. Those pages are audience-gated rather than role-tagged,
      so without this a Regional Director's guide would list their four region
      pages and none of the national ones.

    Both tool lists are filtered to what the *viewer* may see, not what the role
    may: a member reading someone else's guide is not shown pages they would be
    bounced off.
    """
    steps = list(guide.steps.select_related("feature", "feature__area", "task"))
    viewer_audience = user_audience(user)
    flags = _FlagCache()
    visible_steps = [
        {"step": step, "url": resolve_feature_url(step.feature, user) if step.feature else None}
        for step in steps
        if step.feature is None or _feature_visible(step.feature, viewer_audience, flags)
    ]

    visible = get_visible_features(user)
    task_owners = _task_owner_roles(visible)
    is_national = guide.role in NAT_OFFICERS
    tools, national_tools = [], []
    for feature in visible:
        if guide.role in feature_roles(feature, task_owners):
            tools.append(feature)
        elif is_national and feature.effective_audience == Audience.NATOFF:
            national_tools.append(feature)

    open_items = TaskDate.objects.none()
    chapter = getattr(user, "current_chapter", None)
    if chapter is not None:
        open_items = TaskDate.incomplete_dates_for_chapter(chapter).filter(task__owner=guide.role)

    return {
        "guide": guide,
        "steps": visible_steps,
        "tools": tools,
        "national_tools": national_tools,
        "open_items": open_items,
    }


# ---------------------------------------------------------------------------
# What's New (TWI-6)
# ---------------------------------------------------------------------------


def _announcement_model():
    """``announcements.Announcement``, imported on demand.

    ``announcements.models`` imports :mod:`guides.models` for the shared audience
    vocabulary, so the dependency runs one way only. Importing it at the top of
    this module would reverse an arrow the data model deliberately points in a
    single direction.
    """
    from thetatauCMT.announcements.models import Announcement

    return Announcement


def _acknowledged_ids(user, model_class):
    """Object ids of ``model_class`` this user has already said "got it" to.

    One indexed query per content type. Never filter through the generic
    foreign key -- ``target`` cannot use an index and would fan out into a query
    per row.
    """
    if not _is_authenticated(user):
        return set()
    content_type = ContentType.objects.get_for_model(model_class)
    rows = UserAcknowledgement.objects.filter(user=user, content_type=content_type)
    return set(rows.values_list("object_id", flat=True))


def get_published_announcements(user, duty_roles=None, flags=None, now=None):
    """Announcements published right now that ``user`` is allowed to see.

    The publish window matches the pre-TWI-6 home page exactly (strict
    comparisons on both ends) so an untouched row keeps its current behaviour.
    An announcement tied to a feature the viewer cannot reach is withheld --
    telling someone about a page they will be bounced off of is worse than
    silence.
    """
    if not _is_authenticated(user):
        return []
    now = now or timezone.now()
    flags = flags if flags is not None else _FlagCache()
    viewer_audience = user_audience(user)
    allowed = [audience for audience in Audience.values if _audience_allows(viewer_audience, audience)]
    announcements = list(
        _announcement_model()
        .objects.filter(publish_start__lt=now, publish_end__gt=now, audience__in=allowed)
        .select_related("feature", "feature__area")
    )
    if duty_roles is None:
        duty_roles = get_duty_roles(user) if any(item.roles for item in announcements) else set()

    visible = []
    for announcement in announcements:
        if announcement.roles and not (set(announcement.roles) & duty_roles):
            continue
        feature = announcement.feature
        if feature is not None and not _feature_visible(feature, viewer_audience, flags):
            continue
        visible.append(announcement)
    return visible


def _feature_visible(feature, viewer_audience, flags):
    return _audience_allows(viewer_audience, feature.effective_audience) and flags.enabled(
        feature.effective_feature_flag
    )


def get_new_features(user, flags=None, now=None):
    """Visible features released within ``settings.NEW_FEATURE_MAX_AGE_DAYS``.

    A feature with no ``released_at`` is never "new" -- that field is what an
    admin sets to announce something, so leaving it blank is how you add a
    catalog entry without shouting about it.
    """
    now = now or timezone.now()
    cutoff = (now - timedelta(days=settings.NEW_FEATURE_MAX_AGE_DAYS)).date()
    features = [
        feature
        for feature in get_visible_features(user)
        if feature.released_at is not None and feature.released_at >= cutoff
    ]
    features.sort(key=lambda feature: (feature.released_at, feature.id), reverse=True)
    return features


def _announcement_item(announcement, user, acknowledged):
    feature = announcement.feature
    return {
        "kind": KIND_ANNOUNCEMENT,
        "id": announcement.id,
        "title": announcement.title,
        "body": announcement.content,
        "url": resolve_feature_url(feature, user) if feature is not None else None,
        "is_dismissible": announcement.dismissible,
        "date": announcement.publish_start,
        "is_acknowledged": announcement.id in acknowledged,
    }


def _feature_item(feature, user, acknowledged):
    return {
        "kind": KIND_FEATURE,
        "id": feature.id,
        "title": feature.name,
        "body": feature.short_description or feature.long_description,
        "url": resolve_feature_url(feature, user),
        "is_dismissible": True,
        "date": feature.released_at,
        "is_acknowledged": feature.id in acknowledged,
    }


def get_whats_new(user, include_acknowledged=False, limit=None):
    """The merged What's New feed, newest and most urgent first.

    Each item is normalized to ``{kind, id, title, body, url,
    is_dismissible}`` plus two keys the surfaces need: ``date`` (so the home page
    keeps its "Published:" line) and ``is_acknowledged`` (so one call can drive
    both the expanded list and the "already seen" disclosure).

    Announcements come first, ordered by the priority an admin already set, then
    new features newest first. ``include_acknowledged`` is what separates the
    archive page from the unprompted surfaces; a non-dismissible announcement is
    always unacknowledged, so it never sinks into the disclosure.
    """
    if not _is_authenticated(user):
        return []
    now = timezone.now()
    flags = _FlagCache()
    Announcement = _announcement_model()

    announcements = get_published_announcements(user, flags=flags, now=now)
    features = get_new_features(user, flags=flags, now=now)

    acked_announcements = _acknowledged_ids(user, Announcement) if announcements else set()
    acked_features = _acknowledged_ids(user, Feature) if features else set()

    items = [_announcement_item(item, user, acked_announcements) for item in announcements]
    items += [_feature_item(item, user, acked_features) for item in features]
    if not include_acknowledged:
        items = [item for item in items if not item["is_acknowledged"]]
    if limit is not None:
        items = items[:limit]
    return items


def acknowledge(user, items, source=""):
    """Record "got it" for ``items``, a list of ``{"kind": ..., "id": ...}``.

    Returns the number of rows written. Anything the user cannot see, anything
    marked ``dismissible=False``, and anything malformed is skipped in silence
    rather than rejected: a stale tab holding ids that have since been
    deactivated must not be able to spam errors at the user.
    """
    if not _is_authenticated(user) or not items:
        return 0

    wanted = defaultdict(set)
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind not in FEED_KINDS:
            continue
        try:
            wanted[kind].add(int(item.get("id")))
        except (TypeError, ValueError):
            continue
    if not wanted:
        return 0

    Announcement = _announcement_model()
    allowed = {}
    if wanted[KIND_FEATURE]:
        allowed[KIND_FEATURE] = ({feature.id for feature in get_visible_features(user)}, Feature)
    if wanted[KIND_ANNOUNCEMENT]:
        # A pinned announcement has no "Got it" button; refuse the write too, so
        # a hand-rolled POST cannot silence a compliance notice.
        published = get_published_announcements(user)
        allowed[KIND_ANNOUNCEMENT] = ({item.id for item in published if item.dismissible}, Announcement)

    if source not in UserAcknowledgement.Source.values:
        source = ""

    written = 0
    for kind, (visible_ids, model_class) in allowed.items():
        targets = wanted[kind] & visible_ids
        if not targets:
            continue
        content_type = ContentType.objects.get_for_model(model_class)
        for object_id in sorted(targets):
            try:
                _, created = UserAcknowledgement.objects.get_or_create(
                    user=user,
                    content_type=content_type,
                    object_id=object_id,
                    defaults={"source": source},
                )
            except IntegrityError:
                # Two tabs pressing "Got it" at once; the row exists either way.
                continue
            written += int(created)
    return written


def _has_error_message(request):
    """Whether this request is already carrying an error the user must read.

    Peeks at the storage instead of iterating it: iterating sets ``used``, which
    makes the middleware clear the queue -- so a render that never displays the
    messages would silently eat them.
    """
    storage = getattr(request, "_messages", None)
    if storage is None:
        return False
    pending = list(getattr(storage, "_queued_messages", []))
    pending += list(getattr(storage, "_loaded_messages", []))
    return any(message.level >= message_constants.ERROR for message in pending)


def whats_new_modal_allowed(request):
    """Whether an unprompted What's New modal may appear on this request.

    The rules exist because the app already interrupts people:
    ``RMPSignMiddleware`` bounces unsigned users to the risk-management form and
    nags officers about the new-member program, and Viewflow tasks are
    multi-step forms. Stacking a modal on top of any of that is the annoyance
    this feature is supposed to remove, not add.
    """
    if request.method != "GET":
        return False
    if not _is_authenticated(getattr(request, "user", None)):
        return False
    if getattr(request, "session", None) is None or request.session.get(WHATS_NEW_SESSION_KEY):
        return False
    path = request.path
    if path in settings.TERMS_EXCLUDE_URL_LIST:
        return False
    if path.startswith(MODAL_EXCLUDED_PREFIXES):
        return False
    return not _has_error_message(request)
