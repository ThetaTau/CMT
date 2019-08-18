from django.db import models
from django.utils import timezone
from djmoney.models.fields import MoneyField
from core.models import TimeStampedModel
from chapters.models import Chapter


class Transaction(TimeStampedModel):
    TYPES = [
        ('pledge', 'Pledge Fees'),
        ('late', 'Late Fees'),
        ('member', 'Member Dues'),
        ('colony', 'Colony Dues'),
        ('insurance', 'Insurance'),
        ('fine', 'Fine'),
        ('payment', 'Payment'),
        ('award', 'Award'),
        ('misc', 'Misc'),
        ('jewelery', 'Jewelery'),
    ]
    type = models.CharField(max_length=20, choices=TYPES)
    due_date = models.DateField(default=timezone.now)
    central_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.CharField(max_length=1000)
    paid = models.BooleanField(default=False)
    # Open Balance calculated from all amounts and payments
    quantity = models.PositiveIntegerField()  # Number of members, etc.
    # How much each is
    unit_cost = MoneyField(max_digits=19, decimal_places=4, default_currency='USD')
    total = MoneyField(max_digits=19, decimal_places=4, default_currency='USD')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                default=1,
                                related_name="finances")

    def save(self, *args, **kwargs):
        self.total = self.unit_cost * self.quantity
        super().save(*args, **kwargs)

    @property
    def aging(self):
        # calculated from Date Created vs current date
        age = None
        if not self.paid:
            age = self.due_date - timezone.now()
        return age

    @classmethod
    def open_balance_chapter(cls, chapter):
        # chapter.finances.filter(paid=False).aggregate(models.Sum('total'))
        balance = cls.objects.filter(
            chapter=chapter, paid=False).aggregate(models.Sum('total'))['total__sum']
        if balance is None:
            balance = 0
        return round(balance, 2)


"""
Colony Dues are $30/member, due 11/1 and 3/15 of each year.

Semiannual Chapter Dues payable @ $80 each if
mailed by November 1 and March 15 of each year.
$5 of dues per person are set aside to subsidize your
chapter's future National Convention participation.
As penalty, dues is $90 per member if sent late.
See actual Dues List sent separately for itemized list
of student members.
Do not attempt to edit Dues List, send appropriate
Membership Status Change and/or Initiation Report
to modify names.
Add to list any initiated and not yet reported.
Minimum per chapter is $1600.


"""
