import html as _html
import re

from django.conf import settings
from django.shortcuts import reverse
from django.template import Context, Template
from django.urls import NoReverseMatch
from django.urls import reverse as url_reverse
from herald import registry
from herald.base import EmailNotification

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.chapters.tables import ChapterStatusTable
from thetatauCMT.configs.models import Config
from thetatauCMT.tasks.models import TaskDate
from thetatauCMT.users.models import User

# ----- Config-driven email body helpers --------------------------------------
# Shared by any EmailNotification whose HTML body lives in a Config row and is
# authored in the CKEditor admin. Kept module-private; call
# ``MemberEmail.from_config(...)`` rather than these directly.

UNSUBSCRIBE_CONTACT_EMAIL = "central.office@thetatau.org"

# CKEditor often wraps parts of a ``{{ ... }}`` token in inline ``<span>``
# styling, producing broken markup like ``{{<span>user.name}</span>}`` that
# Django's template parser rejects. The token regex matches each token even
# when tags landed between the inner ``}`` and outer ``}`` so we can strip
# them from the token body before Django sees it.
_TOKEN_RE = re.compile(r"\{\{(.*?)\}(?:<[^>]*>|\s)*\}", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
# CKEditor spacing artifacts: empty paragraphs and leading ``<br>``.
_EMPTY_P_RE = re.compile(r"<p>\s*(?:&nbsp;|<br\s*/?>)\s*</p>", re.IGNORECASE)
_P_LEADING_BR_RE = re.compile(r"<p>(?:\s|&nbsp;)*<br\s*/?>\s*", re.IGNORECASE)
# Single-brace ALL_CAPS placeholder like ``{EC_CONTACT}`` → looked up in
# Config with that exact key. Missing keys leave the placeholder in place so
# the omission is visible in the sent email.
_CONFIG_PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def _sanitize_config_template(source):
    def repl(match):
        inner = _TAG_RE.sub("", match.group(1))
        inner = _html.unescape(inner).strip()
        return "{{ " + inner + " }}"

    source = _TOKEN_RE.sub(repl, source)
    source = _EMPTY_P_RE.sub("", source)
    source = _P_LEADING_BR_RE.sub("<p>", source)
    return source


def _substitute_config_placeholders(source):
    def repl(match):
        key = match.group(1)
        value = Config.get_value(key)
        return value if value else match.group(0)

    return _CONFIG_PLACEHOLDER_RE.sub(repl, source)


def _unsubscribe_footer(user, category=None):
    from thetatauCMT.users.views import make_unsubscribe_token

    from .unsubscribe import get_category

    host = getattr(settings, "CURRENT_URL", "").rstrip("/")
    category_obj = get_category(category) if category else None
    token = make_unsubscribe_token(user, category=category_obj.slug if category_obj else None)
    try:
        unsubscribe_path = url_reverse("users:unsubscribe", kwargs={"token": token})
    except NoReverseMatch:
        unsubscribe_path = f"/users/unsubscribe/{token}/"
    unsubscribe_url = f"{host}{unsubscribe_path}"
    if category_obj is not None:
        intro = (
            f"You&rsquo;re receiving this {category_obj.label} email because our "
            "records show you are a Theta Tau member."
        )
        link_text = f"Unsubscribe from {category_obj.label}"
    else:
        intro = "You&rsquo;re receiving this because our records show you are a Theta Tau member."
        link_text = "Manage email preferences"
    return (
        '<hr style="margin: 24px 0 10px 0;border: 0;border-top: 1px solid #cccccc;">'
        '<p style="font-size: 11px;color: #888888;text-align: center;margin: 6px 0;">'
        f"{intro} "
        f'<br><a href="{unsubscribe_url}" style="color: #a00e11;text-decoration: underline;">{link_text}</a>'
        " or email "
        f'<a href="mailto:{UNSUBSCRIBE_CONTACT_EMAIL}?subject=Unsubscribe" style="color: #a00e11;text-decoration: underline;">{UNSUBSCRIBE_CONTACT_EMAIL}</a>'
        "."
        "</p>"
    )


@registry.register_decorator()
class MemberInfoUpdate(EmailNotification):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "member_info_update"  # name of template, without extension
    subject = "[CMT] RMP & Update Member Information"  # subject of email

    def __init__(self, user, updater):
        emails = set(user.emailaddress_set.values_list("email", flat=True)) | {
            user.email,
            user.email_school,
        }
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            updater.email,
        ]
        password = True
        if not user.has_usable_password() or not user.password:
            # Need link to generate password
            password = False
        self.context = {
            "user": user,
            "updater": updater,
            "password": password,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        user = User.objects.order_by("?")[0]
        updater = User.objects.order_by("?")[0]
        return [user, updater]


@registry.register_decorator()
class OfficerMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = "officer_monthly"  # name of template, without extension
    subject = "CMT Monthly Update"  # subject of email

    def __init__(self, chapter):  # optionally customize the initialization
        self.context = {"user": chapter}  # set context for the template rendering
        officer_list, previous = chapter.get_current_officers_council()
        # set list of emails to send to
        emails = chapter.council_emails()
        self.to_emails = emails
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"CMT Monthly Update {chapter_name}"
        self.context = {
            "previous_officers": previous,
            "chapter": chapter_name,
            "last_month_events": chapter.events_last_month().count(),
            "semester_events": chapter.events_semester().count(),
            "count_members": chapter.actives().count(),
            "count_pledges": chapter.pledges().count(),
            "balance": chapter.balance,
            "balance_date": chapter.balance_date,
            "tasks_upcoming": TaskDate.incomplete_dates_for_chapter_next_month(chapter),
            "tasks_overdue": TaskDate.incomplete_dates_for_chapter(chapter),
            "region_announcements": None,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        return [Chapter.objects.order_by("?")[0]]


@registry.register_decorator()
class RDMonthly(EmailNotification):  # extend from EmailNotification for emails
    template_name = "rd_monthly"  # name of template, without extension
    subject = "CMT Monthly Update Region Summary"  # subject of email
    render_types = ["html"]

    def __init__(self, region):  # optionally customize the initialization
        # Chapter, Members, Pledges, Events Last Month, Submissions Last Month, Current Balance, Tasks Overdue
        # List of tasks due next 45 days
        if region == "candidate_chapter":
            email = "ccd@thetatau.org"
            chapters = Chapter.objects.filter(candidate_chapter=True)
        else:
            email = region.email
            chapters = region.chapters.all()
        self.to_emails = {email}
        self.cc = []
        self.reply_to = [
            "cmt@thetatau.org",
        ]
        data = []
        for chapter in chapters:
            if not chapter.active:
                continue
            officers = chapter.get_current_officers_council_specific()
            officer_order = {
                0: "Regent",
                1: "Scribe",
                2: "Vice",
                3: "Treasurer",
                4: "Corresponding Secretary",
            }
            missing = ", ".join([officer_order[ind] for ind, officer in enumerate(officers) if officer is None])
            host = settings.CURRENT_URL
            link = reverse("chapters:detail", kwargs={"slug": chapter.slug})
            link = host + link
            data.append(
                {
                    "name": chapter.name,
                    "slug": chapter.slug,
                    "link": link,
                    "balance": chapter.balance,
                    "balance_date": chapter.balance_date,
                    "officer_missing": missing,
                    "member_count": chapter.actives().count(),
                    "pledge_count": chapter.pledges().count(),
                    "event_count": chapter.events_last_month().count(),
                    "tasks_overdue": TaskDate.incomplete_dates_for_chapter(chapter).count(),
                    "host": host,
                }
            )
        table = ChapterStatusTable(data=data)
        self.context = {
            "region": region,
            "table": table,
            "tasks_upcoming": TaskDate.dates_for_next_month(),
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        # return ["colony"]
        return [Chapter.objects.order_by("?")[0].region]


@registry.register_decorator()
class NewOfficers(EmailNotification):  # extend from EmailNotification for emails
    template_name = "officer_new"  # name of template, without extension
    subject = "Welcome New Theta Tau Officers"  # subject of email

    def __init__(self, new_officers):  # optionally customize the initialization
        self.to_emails = set([officer.email for officer in new_officers])  # set list of emails to send to
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        chapter = new_officers[0].current_chapter
        self.context = {
            "chapter": chapter,
            "region_facebook": chapter.region.facebook,
            "region_web": chapter.region.website,
            "director_emails": chapter.region.email,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from thetatauCMT.users.models import User

        return [
            [
                User.objects.order_by("?")[0],
                User.objects.order_by("?")[0],
                User.objects.order_by("?")[0],
            ]
        ]


@registry.register_decorator()
class OfficerUpdateReminder(EmailNotification):  # extend from EmailNotification for emails
    render_types = ["html"]
    template_name = "officer_update_reminder"  # name of template, without extension
    subject = "Officer update reminder"  # subject of email

    def __init__(self, chapter, emails, officers_to_update):  # optionally customize the initialization
        emails = {email for email in emails if email}
        format_officers = ", ".join(officers_to_update)
        self.to_emails = emails
        # The Regional Director is intentionally NOT cc'd on this daily reminder.
        # RDs receive a single weekly roll-up instead (RegionalDirectorOfficerDigest,
        # sent by the ``region_officer_reminder_digest`` command) so an unresponsive
        # chapter no longer generates a daily email to the RD.
        self.cc = []
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"CMT Officer update {chapter_name}"
        self.context = {
            "chapter": chapter_name,
            "officers": format_officers,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        chapter = Chapter.objects.order_by("?")[0]
        emails, officers_to_update = chapter.get_about_expired_coucil()
        return [
            chapter,
            emails,
            officers_to_update,
        ]


class RegionalDirectorOfficerDigest(EmailNotification):
    """Weekly roll-up emailed to a region's Directors (and the region mailbox).

    Replaces the per-chapter daily CC that used to land on the Regional
    Director for every chapter with an expiring/missing officer. One email is
    sent per region, summarizing every chapter in that region that still needs
    an officer update, so an unresponsive chapter no longer bombards the RD
    daily while the RD still gets a regular prompt to follow up.
    """

    render_types = ["html"]
    template_name = "regional_director_officer_digest"
    subject = "Regional officer update summary"

    def __init__(self, region, chapter_updates):
        # ``chapter_updates`` is a list of {"chapter": Chapter, "officers": str}.
        director_emails = set()
        for director in region.directors.all():
            director_emails |= {email for email in director.emails if email}
        if region.email:
            director_emails.add(region.email)
        self.to_emails = director_emails
        self.cc = []
        self.reply_to = [
            "central.office@thetatau.org",
        ]
        self.subject = f"CMT Weekly Officer Update Summary — {region.name} Region"
        self.context = {
            "region": region,
            "chapter_updates": chapter_updates,
            "count": len(chapter_updates),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from thetatauCMT.regions.models import Region

        region = Region.objects.order_by("?")[0]
        chapter_updates = []
        for chapter in region.chapters.exclude(active=False):
            _, officers_to_update = chapter.get_about_expired_coucil()
            if officers_to_update:
                chapter_updates.append({"chapter": chapter, "officers": ", ".join(officers_to_update)})
        return [region, chapter_updates]


@registry.register_decorator()
class MemberEmail(EmailNotification):
    render_types = ["html"]
    template_name = "member_email"

    def __init__(self, user, title, email_content, context):
        emails = set(user.emailaddress_set.values_list("email", flat=True)) | {
            user.email,
            user.email_school,
        }
        self.subject = title
        rendered_content = Template(email_content).render(Context(context))
        self.to_emails = emails
        self.cc = []
        self.reply_to = []
        self.context = {
            "user": user,
            "host": settings.CURRENT_URL,
            "title": title,
            "email_content": rendered_content,
        }

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        user = User.objects.order_by("?")[0]
        title = "Demo Title"
        email_content = "Hello {{ user.get_full_name }} Demo email content"
        context = {"user": user}
        return [user, title, email_content, context]

    @classmethod
    def from_config(cls, user, config_key, title, context=None, *, unsubscribe=False, category=None):
        """Build a ``MemberEmail`` from an HTML body stored under ``config_key``.

        Pipeline (applied in order):
          1. Fetch ``Config.get_value(config_key, clean=False)``.
          2. Sanitize CKEditor artefacts inside the value (broken
             ``{{ ... }}`` tokens, empty paragraphs, ``<p><br>`` cruft).
          3. Substitute any single-brace ``{ALL_CAPS_KEY}`` placeholder with
             the corresponding ``Config`` row's value (leaves the token in
             place when no matching Config exists).
          4. If ``unsubscribe`` is truthy, append a per-recipient signed
             unsubscribe footer that links to the public confirmation page.
             When ``category`` is a slug from
             ``users.unsubscribe.UNSUBSCRIBE_CATEGORIES``, the footer names
             the mailing list and the confirm page pre-checks it.

        Returns ``None`` when the config row is missing/empty so the caller
        can log and skip. Otherwise returns a ready-to-``send()`` instance.
        """
        raw = Config.get_value(config_key, clean=False)
        if not raw:
            return None
        body = _sanitize_config_template(raw)
        body = _substitute_config_placeholders(body)
        if unsubscribe:
            body += _unsubscribe_footer(user, category=category)
        return cls(user, title, body, context or {})
