"""The Regent's chapter emails for Chapter Support Specialists (CSSWI-6; Q13, Q14, Q25).

Every send listed in the spec's Email inventory hands its email to :func:`notify_support`
just before it goes out, usually through :class:`SupportCopyMixin`. Time-sensitive kinds
(the ``CSS_REALTIME_EMAILS`` Config setting, S16) put the chapter's CSSs on CC and leave a
one-line digest entry; every other kind reaches them only through the daily digest, so the
entry keeps the email's body. Emails follow assignments, never the CSS's chapter switcher.
"""

import html
import logging

from django.db import transaction
from django.template import Context
from django.template.loader import get_template
from django.template.loader_tags import BlockNode

from .models import SupportDigestEntry
from .services import chapter_support_specialists, config_list

logger = logging.getLogger(__name__)

Kind = SupportDigestEntry.Kind

REALTIME_CONFIG_KEY = "CSS_REALTIME_EMAILS"
# The "CC as sent" rows of the spec's Email inventory.
DEFAULT_REALTIME_KINDS = frozenset(
    {
        Kind.WORKFLOW_ESCALATION,
        Kind.BALLOT,
        Kind.BALLOT_RECEIPT,
        Kind.BALLOT_VOTE_REMOVED,
        Kind.EXPULSION,
        Kind.DISCIPLINARY,
        Kind.OFFICER_UPDATE,
        Kind.TRANSITION_PAST_DUE,
    }
)


def realtime_kinds():
    """The kinds a CSS gets on CC as they are sent.

    ``CSS_REALTIME_EMAILS`` lists kind codes (such as ``ballot_receipt``); ``none`` sends
    everything through the digest. Unset, or with no known code, it means the defaults.
    """
    values = {value.lower() for value in config_list(REALTIME_CONFIG_KEY)}
    if "none" in values:
        return frozenset()
    chosen = frozenset(kind for kind in Kind if kind.value in values)
    return chosen or DEFAULT_REALTIME_KINDS


def notify_support(notification, chapter, kind, link=""):
    """Hand a herald email the chapter's Regent gets to the chapter's CSSs.

    Call it just before ``send()``. Returns the CSSs it covered.
    """
    if chapter is None:
        return []
    specialists = [person for person in chapter_support_specialists(chapter) if person.email]
    if not specialists:
        return []
    realtime = kind in realtime_kinds()
    body = ""
    if realtime:
        cc = list(notification.cc or [])
        already = {email.lower() for email in [*(notification.to_emails or []), *cc] if email}
        for person in specialists:
            if person.email.lower() not in already:
                cc.append(person.email)
                already.add(person.email.lower())
        notification.cc = cc
    else:
        body = email_body_html(notification)
    subject = (notification.get_subject() or "")[:255]
    SupportDigestEntry.objects.bulk_create(
        [
            SupportDigestEntry(
                user=person, chapter=chapter, kind=kind, subject=subject, body_html=body, link=link, realtime=realtime
            )
            for person in specialists
        ]
    )
    return specialists


def email_body_html(notification):
    """The email's own content, without the outer layout, for embedding in a digest."""
    context = notification.get_context_data()
    if "html" not in notification.render_types:
        return f"<pre>{html.escape(notification.render('text', context))}</pre>"
    template = get_template(f"herald/html/{notification.template_name}.html").template
    blocks = [node for node in template.nodelist.get_nodes_by_type(BlockNode) if node.name == "content"]
    if not blocks:
        return notification.render("html", context)
    render_context = Context(context, autoescape=True)
    with render_context.render_context.push_state(template), render_context.bind_template(template):
        return blocks[0].render(render_context)


def copy_to_support(notification, chapter, kind, link=""):
    """:func:`notify_support` that never stops the officers' email; errors are logged."""
    try:
        with transaction.atomic():
            return notify_support(notification, chapter, kind, link=link)
    except Exception:
        logger.exception("Could not copy %s to the Chapter Support Specialists", type(notification).__name__)
        return []


class SupportCopyMixin:
    """For a Regent email: ``send`` first hands it to the chapter's CSSs.

    Set ``support_chapter`` (None means no CSS copy) and ``support_kind`` in ``__init__``.
    """

    support_chapter = None
    support_kind = None
    support_link = ""

    def send(self, *args, **kwargs):
        if self.support_chapter is not None and self.support_kind:
            copy_to_support(self, self.support_chapter, self.support_kind, link=self.support_link)
        return super().send(*args, **kwargs)
