from django.db import models
from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
from djmoney.models.fields import MoneyField

from core.models import ACTIVE_STATUSES, TimeStampedModel
from thetatauCMT.chapters.models import Chapter


class Invoice(TimeStampedModel):
    due_date = models.DateField(default=timezone.now)
    central_id = models.CharField(max_length=50, null=True, blank=True)
    description = CKEditor5Field()
    total = MoneyField(max_digits=19, decimal_places=4, default_currency="USD")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, default=1, related_name="invoices")
    link = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )

    @classmethod
    def open_balance_chapter(cls, chapter):
        balance = cls.objects.filter(chapter=chapter).aggregate(models.Sum("total"))["total__sum"]
        if balance is None:
            balance = 0
        return round(balance, 2)

    @classmethod
    def open_balances_all(cls):
        return cls.objects.values(
            "chapter__name",
            "chapter__region__name",
            "chapter__candidate_chapter",
        ).annotate(
            balance=models.Sum("total"),
        )


def _latest_audit_value(field):
    """Subquery pulling ``field`` from a chapter's most recently reported audit.

    Audits are submitted per-officer, so a chapter can accumulate several. We
    surface the single most recently reported one (ordered by submission time).
    Keeping the selection isolated here makes it easy to change later — e.g. to
    average the last few audits instead of taking only the latest.
    """
    from thetatauCMT.forms.models import Audit

    latest = Audit.objects.filter(user__chapter=OuterRef("pk")).order_by("-created")
    return Subquery(latest.values(field)[:1])


def chapter_balance_overview():
    """Active chapters annotated for the finances balances overview.

    Adds, per chapter, the current membership counts (actives and PNMs), the
    open invoice balance, and the dues figures from the chapter's most recent
    audit (member dues, PNM pledging fees/dues, and the reporting frequency).
    """
    today = timezone.now().date()
    invoice_balance = (
        Invoice.objects.filter(chapter=OuterRef("pk"))
        .order_by()
        .values("chapter")
        .annotate(amount=models.Sum("total"))
        .values("amount")
    )
    return (
        Chapter.objects.filter(active=True)
        .select_related("region")
        .annotate(
            actives_count=Count(
                "members",
                filter=Q(members__current_status__in=ACTIVE_STATUSES),
                distinct=True,
            ),
            pnm_count=Count(
                "members",
                filter=Q(
                    members__status__status="pnm",
                    members__status__start__lte=today,
                    members__status__end__gte=today,
                ),
                distinct=True,
            ),
            open_balance=Coalesce(
                Subquery(invoice_balance, output_field=DecimalField(max_digits=19, decimal_places=4)),
                Value(0),
                output_field=DecimalField(max_digits=19, decimal_places=4),
            ),
            audit_dues_member=_latest_audit_value("dues_member"),
            audit_dues_pledge=_latest_audit_value("dues_pledge"),
            audit_frequency=_latest_audit_value("frequency"),
            audit_year=_latest_audit_value("year"),
            audit_term=_latest_audit_value("term"),
            audit_created=_latest_audit_value("created"),
        )
    )
