from django.db import models
from address.models import AddressField
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
from core.models import TODAY_END, annotate_role_status
from regions.models import Region


class Chapter(models.Model):
    class Meta:
        ordering = ['name', ]

    TYPES = [
        ('semester', 'Semester'),
        ('quarter', 'Quarter'),
    ]

    name = models.CharField(max_length=50)
    region = models.ForeignKey(Region, on_delete=models.PROTECT,
                               related_name='chapters')
    slug = models.SlugField(max_length=50, null=True, default=None, unique=True)
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    address = AddressField(on_delete=models.SET_NULL, blank=True, null=True, unique=True)
    balance = models.DecimalField(default=0, decimal_places=2,
                                  max_digits=7,
                                  help_text="Balance chapter owes.")
    balance_date = models.DateField(auto_now_add=True)
    tax = models.PositiveIntegerField(
        blank=True, null=True, unique=True,
        help_text="Tax number, if chapter participates in group exemption.")
    greek = models.CharField(max_length=10, blank=True,
                             help_text="Greek letter abbreviation")
    active = models.BooleanField(default=True)
    school = models.CharField(max_length=50, blank=True)
    school_type = models.CharField(
        default='semester',
        max_length=10,
        choices=TYPES
    )

    def __str__(self):
        return f"{self.name}"  # in {self.region} Region at {self.school}

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_actives_for_date(self, date):
        # Do not annotate, need the queryset not a list
        return self.members.filter(status__status__in=["active", "activepend", "alumnipend"],
                                   status__start__lte=date,
                                   status__end__gte=date
                                   )

    def actives(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(status__status__in=["active", "activepend", "alumnipend"],
                                   status__start__lte=TODAY_END,
                                   status__end__gte=TODAY_END
                                   )

    def pledges(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(status__status="pnm",
                                   status__start__lte=TODAY_END,
                                   status__end__gte=TODAY_END
                                   )

    def get_current_officers(self, combine=True):
        return annotate_role_status(
            self.members.filter(
                roles__start__lte=TODAY_END, roles__end__gte=TODAY_END
            ), combine=combine)

    def next_badge_number(self):
        return self.members.filter(~models.Q(status__status='pnm'),
                                   ~models.Q(badge_number=999999999)
                                   ).aggregate(models.Max('badge_number'))

    @classmethod
    def schools(cls):
        return [(school['pk'], school['school']) for school in cls.objects.values('school', 'pk').order_by('school')]


class ChapterCurricula(models.Model):
    chapter = models.ForeignKey(Chapter,
                                on_delete=models.CASCADE,
                                related_name="curricula")
    major = models.CharField(max_length=100)
