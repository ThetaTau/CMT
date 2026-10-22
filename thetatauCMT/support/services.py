"""Chapter Support Specialist (CSS) rules shared by the rest of the site.

See docs/specs/chapter-support-specialist.md. This module grows with each work item; it
starts with the role check and the home chapter used for non-member CSS accounts.
"""

import datetime
import html
from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from core.models import CSS_ROLE

CSS_HOME_CHAPTER_CONFIG_KEY = "CSS_HOME_CHAPTER"
# Production's inactive "Central Office" chapter (Q23). The Config setting overrides it.
DEFAULT_CSS_HOME_CHAPTER_SLUG = "central-office"

# Shown whenever a CSS tries to change something (Q1, S14).
VIEW_ONLY_MESSAGE = "Chapter Support Specialists have view-only access. The chapter's officers make changes."

# URL names a CSS may still submit to while viewing an assigned chapter: actions that only
# touch their own account (Q22). Everything else that changes data is refused by
# ``thetatauCMT.support.middleware.ViewOnlyCSSMiddleware``.
PERSONAL_ACTIONS = frozenset(
    {
        "support:switch",
        "account_logout",
        "logout",
        "account_change_password",
        "account_set_password",
        "account_email",
        "account_reauthenticate",
        "account_reset_password",
        "account_reset_password_from_key",
        "password_reset",
        "password_reset_confirm",
        "socialaccount_connections",
        "two-factor-setup",
        "two-factor-remove",
        "two-factor-backup-tokens",
        "two-factor-authenticate",
        "rmp",
        "forms:rmp",
        "tc_accept_page",
        "tc_accept_specific_page",
        "tc_accept_specific_version_page",
        "electronic_terms",
        "users:detail",
        "users:profile_picture",
        "users:unsubscribe",
        "guides:acknowledge",
        "guides:whats-new-seen",
        "events:feeds",
        "events:feed_tasks",
        "events:feed_edit",
        "events:feed_delete",
        "events:feed_subscribe_chapter",
        "contact_sync:google_sync",
        "contact_sync:google_disconnect",
        "contact_sync:google_auto_sync",
        "contact_sync:microsoft_sync",
        "contact_sync:microsoft_disconnect",
        "contact_sync:microsoft_auto_sync",
        "jobs:add_search",
        "jobs:update_search",
    }
)
# Whole URL namespaces that only read data even though they POST (dashboard callbacks).
PERSONAL_ACTION_NAMESPACES = frozenset({"the_django_plotly_dash"})

# Cached on the user object for the rest of the request (see ``css_state``).
_CSS_STATE_ATTR = "_support_css_state"


class CSSHomeChapterError(ImproperlyConfigured):
    """The configured CSS home chapter is missing, or is active and so could give access."""


@dataclass(frozen=True)
class CSSState:
    """Where a user stands as a Chapter Support Specialist for this request.

    ``is_css``: holds the CSS role today. ``chapter_ids``: chapters with a current
    assignment. ``viewing``: the chapter they are looking at (None when not a CSS, or a
    National Officer, whose own chapter switcher wins). ``standing_in``: viewing one of
    their assigned chapters, so they see what its Regent sees, view only.
    """

    is_css: bool = False
    chapter_ids: frozenset = field(default_factory=frozenset)
    viewing: object = None
    standing_in: bool = False


NOT_CSS = CSSState()


def _as_date(value):
    if value is None:
        return timezone.localdate()
    if isinstance(value, datetime.datetime):
        return value.date()
    return value


def holds_css_role(user, on=None):
    """Whether ``user`` holds the dated Chapter Support Specialist role on ``on`` (default today).

    Reads the role rows rather than ``current_roles`` so a start date in the future or the
    past can be checked, which assignment validation needs.
    """
    if user is None or getattr(user, "pk", None) is None:
        return False
    day = _as_date(on)
    return user.roles.filter(role=CSS_ROLE, start__lte=day, end__gte=day).exists()


def css_home_chapter_slug():
    from thetatauCMT.configs.models import Config

    configured = html.unescape(Config.get_value(CSS_HOME_CHAPTER_CONFIG_KEY)).strip()
    return configured or DEFAULT_CSS_HOME_CHAPTER_SLUG


def css_home_chapter():
    """The inactive chapter that non-member CSS accounts belong to (Q8, Q23).

    It must be inactive: inactive chapters cannot be assigned, so the home chapter never
    gives a CSS access to anything by itself.
    """
    from thetatauCMT.chapters.models import Chapter

    slug = css_home_chapter_slug()
    chapter = Chapter.objects.filter(slug=slug).first()
    if chapter is None:
        raise CSSHomeChapterError(
            f'No chapter has the slug "{slug}". Set the {CSS_HOME_CHAPTER_CONFIG_KEY} Config setting to the '
            "slug of the inactive Central Office chapter."
        )
    if chapter.active:
        raise CSSHomeChapterError(
            f'The CSS home chapter "{chapter}" is active. It must be inactive so it never gives a Chapter '
            "Support Specialist access by itself."
        )
    return chapter


def css_state(user):
    """The user's :class:`CSSState` for this request, worked out once and cached on the user.

    ``request.user`` lives for one request, so the cache never outlives it. Code that
    changes a CSS's role, assignments or chosen chapter during a request (or a test that
    reuses a user object) calls :func:`clear_css_state`. Someone without the CSS role in
    ``current_roles`` costs no queries.
    """
    if user is None or not getattr(user, "is_authenticated", False) or getattr(user, "pk", None) is None:
        return NOT_CSS
    cached = getattr(user, _CSS_STATE_ATTR, None)
    if cached is not None:
        return cached
    state = _compute_css_state(user)
    setattr(user, _CSS_STATE_ATTR, state)
    return state


def clear_css_state(user):
    if user is not None and hasattr(user, _CSS_STATE_ATTR):
        delattr(user, _CSS_STATE_ATTR)


def is_member_account(user):
    """A CSS who is also a member (Q9) keeps their own chapter; a staff account does not."""
    return getattr(user, "current_status", "") != "css"


def _compute_css_state(user):
    if CSS_ROLE not in (getattr(user, "current_roles", None) or []) or not holds_css_role(user):
        return NOT_CSS
    from .models import ChapterSupportAssignment

    chapter_ids = frozenset(
        ChapterSupportAssignment.objects.current().filter(user=user).values_list("chapter_id", flat=True)
    )
    if user.in_national_officer_group:
        # A National Officer keeps the national switcher and powers (S7); the CSS
        # assignments still decide their CSS emails.
        return CSSState(is_css=True, chapter_ids=chapter_ids)
    viewing = _viewing_chapter(user, chapter_ids)
    standing_in = viewing is not None and viewing.pk in chapter_ids and viewing.pk != user.chapter_id
    return CSSState(is_css=True, chapter_ids=chapter_ids, viewing=viewing, standing_in=standing_in)


def _viewing_chapter(user, chapter_ids):
    """The chapter switcher's choice if still allowed, else the fallbacks in the spec."""
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.users.models import UserAlter

    member = is_member_account(user)
    alter = UserAlter.objects.filter(user=user).select_related("chapter").first()
    if alter is not None and (alter.chapter_id in chapter_ids or (member and alter.chapter_id == user.chapter_id)):
        return alter.chapter
    if member:
        return user.chapter
    if chapter_ids:
        return Chapter.objects.filter(pk__in=chapter_ids).order_by("name").first()
    return user.chapter


def css_chapters(user):
    """The chapters a CSS currently serves, by name."""
    from thetatauCMT.chapters.models import Chapter

    state = css_state(user)
    if not state.chapter_ids:
        return Chapter.objects.none()
    return Chapter.objects.filter(pk__in=state.chapter_ids).order_by("name")


def chapter_support_specialists(chapter, on=None):
    """The CSSs serving ``chapter`` on ``on`` (default today): a current assignment and role.

    The chapter page lists them (Q11, Q18), and their chapter emails go to these people.
    """
    from thetatauCMT.users.models import User

    from .models import ChapterSupportAssignment

    day = _as_date(on)
    assigned = ChapterSupportAssignment.objects.current(day).filter(chapter=chapter).values("user_id")
    return (
        User.objects.filter(
            pk__in=assigned, is_active=True, roles__role=CSS_ROLE, roles__start__lte=day, roles__end__gte=day
        )
        .distinct()
        .order_by("last_name", "first_name")
    )


def supports(user, chapter):
    """Whether ``user`` is a CSS with a current assignment to ``chapter``."""
    chapter_id = getattr(chapter, "pk", chapter)
    return chapter_id is not None and chapter_id in css_state(user).chapter_ids


def standing_in(user):
    """Whether ``user`` is a CSS viewing one of their assigned chapters right now."""
    return css_state(user).standing_in


def wants_css_landing(user):
    """Whether Home and signing in open the CSS landing page (Q24 A).

    Every CSS who is not a National Officer; National Officers keep their own home (S7).
    """
    return css_state(user).is_css and not user.in_national_officer_group


def css_dashboard_chapter_ids(user):
    """The chapters a CSS may see on the region dashboard, or None for no limit (CSSWI-8).

    The dashboard asks for its scope from the browser, so a CSS who is not a National
    Officer is held to their assigned chapters, plus their own if they are a member (Q9),
    whatever scope a request names.
    """
    if not wants_css_landing(user):
        return None
    ids = set(css_state(user).chapter_ids)
    if is_member_account(user):
        ids.add(user.chapter_id)
    return ids


def own_records_chapter(user):
    """The chapter a user's own paperwork, such as their RMP, is filed under.

    A CSS standing in sees an assigned chapter as ``current_chapter``, but what they sign
    for themselves belongs to their real chapter, never to the chapter they are viewing.
    """
    if standing_in(user):
        return user.chapter
    return user.current_chapter


def is_personal_action(resolver_match):
    """Whether a submission to this URL only touches the user's own account (Q22)."""
    if resolver_match is None:
        return False
    if resolver_match.view_name in PERSONAL_ACTIONS:
        return True
    return bool(set(resolver_match.namespaces) & PERSONAL_ACTION_NAMESPACES)


CSS_MANAGERS_CONFIG_KEY = "CSS_MANAGERS"


def config_list(key):
    """A Config setting as a list: entries separated by commas or new lines.

    Config values are rich text, and ``Config.get_value`` strips the tags, which would join
    one-per-line entries (``<p>a</p><p>b</p>`` becomes ``ab``), so line-ending tags become
    new lines first.
    """
    import re

    from django.utils.html import strip_tags

    from thetatauCMT.configs.models import Config

    raw = str(Config.get_value(key, clean=False))
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", raw)
    text = html.unescape(strip_tags(raw))
    return [value.strip() for value in re.split(r"[,\n]", text) if value.strip()]


def css_manager_ids():
    """Who may create CSS accounts and assign chapters, besides Admins (Q6).

    The ``CSS_MANAGERS`` Config setting lists usernames, emails or National Officer role
    names, separated by commas or new lines. Unset, it means the Executive Director.
    """
    from django.conf import settings
    from django.db.models import Q

    from core.models import NAT_OFFICERS
    from thetatauCMT.users.models import User

    values = config_list(CSS_MANAGERS_CONFIG_KEY) or [settings.EXECUTIVE_DIRECTOR]
    roles = {role.lower(): role for role in NAT_OFFICERS}
    ids = set()
    for value in values:
        role = roles.get(value.lower())
        if role is not None:
            ids.update(User.objects.filter(current_roles__contains=[role]).values_list("pk", flat=True))
        else:
            ids.update(
                User.objects.filter(Q(username__iexact=value) | Q(email__iexact=value)).values_list("pk", flat=True)
            )
    return ids


def can_manage_css(user):
    """Admins, plus the people named in ``CSS_MANAGERS``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    if getattr(user, "natoff_hidden", False):
        return False
    return user.pk in css_manager_ids()


# --- Managing CSSs (CSSWI-5) -------------------------------------------------------------


class CSSAccountError(Exception):
    """A CSS account could not be created; the message says why, for the manager."""


def can_view_css_directory(user):
    """CSS managers, and National Officers read only (Q6)."""
    from core.models import user_is_national_officer

    return can_manage_css(user) or user_is_national_officer(user)


def current_css_users(on=None):
    """Everyone holding the CSS role on ``on`` (default today), by name."""
    from thetatauCMT.users.models import User

    day = _as_date(on)
    return (
        User.objects.filter(roles__role=CSS_ROLE, roles__start__lte=day, roles__end__gte=day)
        .distinct()
        .select_related("chapter")
        .order_by("last_name", "first_name")
    )


def grant_css_role(user, start=None):
    from core.models import forever
    from thetatauCMT.users.models import UserRoleChange

    role = UserRoleChange.objects.create(user=user, role=CSS_ROLE, start=_as_date(start), end=forever())
    clear_css_state(user)
    return role


def create_css_account(*, first_name, last_name, email):
    """Make the person with ``email`` a CSS. Returns ``(user, outcome)``.

    A new person gets a staff account: status ``css`` (Q7) in the home chapter (Q23). An
    existing member keeps their status and chapter and gains the role (Q9). A former CSS
    staff account switched off by :func:`remove_css` is switched back on. The outcome is
    ``"created"``, ``"member"`` or ``"restored"``; the first and last need the welcome email.
    """
    from allauth.account.models import EmailAddress
    from django.db import transaction
    from django.db.models import Q

    from thetatauCMT.users.models import User

    email = email.strip()
    existing = (
        User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email) | Q(emailaddress__email__iexact=email))
        .distinct()
        .order_by("pk")
        .first()
    )
    with transaction.atomic():
        if existing is not None:
            if holds_css_role(existing):
                raise CSSAccountError(f"{existing} is already a Chapter Support Specialist.")
            outcome = "member"
            if not existing.is_active:
                if is_member_account(existing):
                    raise CSSAccountError(
                        f"{existing}'s account is switched off. Switch it on in the admin first if they "
                        "should be a Chapter Support Specialist."
                    )
                existing.is_active = True
                existing.save(update_fields=["is_active"])
                outcome = "restored"
            elif not is_member_account(existing):
                outcome = "restored"
            grant_css_role(existing)
            return existing, outcome
        try:
            home = css_home_chapter()
        except CSSHomeChapterError as error:
            raise CSSAccountError(str(error)) from error
        user = User.objects.create(
            username=email,
            email=email,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            name=f"{first_name.strip()} {last_name.strip()}",
            chapter=home,
        )
        # Production requires a verified email to sign in. The set-password link goes only to
        # this address, so using it proves the address; without this row the first sign-in
        # would stop for a second, verification email.
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        user.set_current_status("css")
        grant_css_role(user)
        return user, "created"


def set_password_url(user):
    """A one-time link to set the password; it lasts ``PASSWORD_RESET_TIMEOUT`` (3 days)."""
    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.urls import reverse
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    path = reverse(
        "password_reset_confirm",
        kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
        },
    )
    return f"{settings.CURRENT_URL}{path}"


def assign_chapter(css, chapter, *, start=None, end=None, notes="", by=None):
    """Assign ``chapter`` to ``css``; raises ``ValidationError`` when the rules say no."""
    from .models import ChapterSupportAssignment

    assignment = ChapterSupportAssignment(
        user=css, chapter=chapter, start=_as_date(start), end=end, notes=notes, created_by=by
    )
    assignment.full_clean()
    assignment.save()
    clear_css_state(css)
    return assignment


def end_assignment(assignment, end, by=None):
    """End an assignment after ``end``. One that has not started before today is removed."""
    today = timezone.localdate()
    if assignment.start >= today:
        assignment.delete()
        return None
    assignment.end = end
    assignment.ended_by = by
    assignment.full_clean()
    assignment.save()
    return assignment


def remove_css(css, by=None):
    """End the CSS role and every assignment now (S21). A staff account is switched off."""
    from django.db import transaction

    today = timezone.localdate()
    yesterday = today - datetime.timedelta(days=1)
    with transaction.atomic():
        for assignment in css.support_assignments.exclude(end__lt=today):
            end_assignment(assignment, yesterday, by=by)
        dropped = False
        for role in css.roles.filter(role=CSS_ROLE, end__gte=today):
            if role.start >= today:
                role.delete()
                dropped = True
            else:
                role.end = yesterday
                role.save()
        css.refresh_from_db()
        if dropped and CSS_ROLE in (css.current_roles or []):
            # Deleting a role row does not update the denormalized list; ending one does.
            css.current_roles = [role for role in css.current_roles if role != CSS_ROLE]
            css.save(update_fields=["current_roles"])
        if not is_member_account(css) and css.is_active:
            css.is_active = False
            css.save(update_fields=["is_active"])
    clear_css_state(css)
