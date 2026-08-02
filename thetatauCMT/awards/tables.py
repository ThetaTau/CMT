import django_tables2 as tables
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.tables import CMTTable

from .models import AwardGrant


def _context_chapter(grant):
    """The chapter a grant is associated with, for the directory's context column.

    A member grant surfaces the member's chapter; a chapter grant surfaces the
    chapter itself; a region grant has no single chapter.
    """
    kind = grant.recipient_kind
    if kind == "member" and grant.recipient_member_id:
        return grant.recipient_member.chapter
    if kind == "chapter":
        return grant.recipient_chapter
    return None


def _context_region(grant):
    """The region a grant is associated with (recipient region, or the recipient's
    chapter's region for member / chapter recipients)."""
    if grant.recipient_kind == "region":
        return grant.recipient_region
    chapter = _context_chapter(grant)
    return chapter.region if chapter is not None else None


def _recipient_url(grant):
    kind = grant.recipient_kind
    try:
        if kind == "member" and grant.recipient_member_id:
            return reverse("users:profile", kwargs={"username": grant.recipient_member.username})
        if kind == "chapter" and grant.recipient_chapter_id:
            return reverse("chapters:detail", kwargs={"slug": grant.recipient_chapter.slug})
        if kind == "region" and grant.recipient_region_id:
            return reverse("regions:detail", kwargs={"slug": grant.recipient_region.slug})
    except NoReverseMatch:
        return None
    return None


class AwardGrantTable(CMTTable):
    """Public directory of award winners (AWI-11).

    Lists one row per :class:`~thetatauCMT.awards.models.AwardGrant`. The award
    links to its "all winners of X" page, the cycle to its "winners in cycle Y"
    page, and the recipient / chapter / region to their detail pages. The
    ``status`` column is excluded by the view unless revoked grants are shown.
    """

    award_type = tables.Column(
        verbose_name="Award",
        order_by=("award_type__name",),
        linkify=lambda record: reverse("awards:type_winners", args=[record.award_type_id]),
    )
    recipient = tables.Column(accessor="recipient_display", orderable=False, verbose_name="Recipient")
    kind = tables.Column(accessor="recipient_kind", orderable=False, verbose_name="Type")
    chapter = tables.Column(empty_values=(), orderable=False, verbose_name="Chapter")
    region = tables.Column(empty_values=(), orderable=False, verbose_name="Region")
    cycle = tables.Column(
        verbose_name="Award Period",
        order_by=("cycle__name",),
        linkify=lambda record: reverse("awards:cycle_winners", args=[record.cycle_id]),
    )
    effective_date = tables.DateColumn(verbose_name="Awarded")
    status = tables.Column(verbose_name="Status")

    class Meta:
        model = AwardGrant
        order_by = "-effective_date"
        fields = ("award_type", "recipient", "kind", "chapter", "region", "cycle", "effective_date", "status")
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No award winners match the current filters."

    def render_recipient(self, record):
        url = _recipient_url(record)
        if url:
            return format_html('<a href="{}">{}</a>', url, record.recipient_display)
        return record.recipient_display

    def render_kind(self, value):
        return value.title() if value else "\u2014"

    def render_chapter(self, record):
        chapter = _context_chapter(record)
        if chapter is None:
            return "\u2014"
        try:
            url = reverse("chapters:detail", kwargs={"slug": chapter.slug})
        except NoReverseMatch:
            return str(chapter)
        return format_html('<a href="{}">{}</a>', url, str(chapter))

    def render_region(self, record):
        region = _context_region(record)
        if region is None:
            return "\u2014"
        try:
            url = reverse("regions:detail", kwargs={"slug": region.slug})
        except NoReverseMatch:
            return str(region)
        return format_html('<a href="{}">{}</a>', url, str(region))

    def render_status(self, record):
        css = "bg-danger" if record.is_revoked else "bg-success"
        return format_html('<span class="badge {}">{}</span>', css, record.get_status_display())
