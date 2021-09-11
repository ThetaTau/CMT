from django.db import models
from django.utils import timezone
from djmoney.models.fields import MoneyField
from ckeditor_uploader.fields import RichTextUploadingField
from core.models import TimeStampedModel
from chapters.models import Chapter


class Invoice(TimeStampedModel):
    due_date = models.DateField(default=timezone.now)
    central_id = models.PositiveIntegerField(null=True, blank=True)
    description = RichTextUploadingField()
    total = MoneyField(max_digits=19, decimal_places=4, default_currency="USD")
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, default=1, related_name="invoices"
    )
    link = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )

    @classmethod
    def open_balance_chapter(cls, chapter):
        balance = cls.objects.filter(chapter=chapter).aggregate(models.Sum("total"))[
            "total__sum"
        ]
        if balance is None:
            balance = 0
        return round(balance, 2)

    @classmethod
    def open_balances_all(cls):
        return cls.objects.values(
            "chapter__name",
            "chapter__region__name",
            "chapter__candidate_chapter",
            "chapter__region__slug",
        ).annotate(
            chapter=models.F("chapter__name"),
            colony=models.F("chapter__candidate_chapter"),
            region=models.F("chapter__region__name"),
            region_slug=models.F("chapter__region__slug"),
            balance=models.Sum("total"),
        )
