import warnings
from datetime import timedelta
from django.db import models
from django.db.utils import ProgrammingError
from address.models import AddressField
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
from core.models import TODAY_END, annotate_role_status, CHAPTER_OFFICER, semester_start_date
from regions.models import Region


GREEK_ABR = {
    'a': 'alpha',
    'albany': 'ua colony',
    'ua': 'ua colony',
    'b': 'beta',
    'csf': 'csf colony',
    'cslb': 'cslb colony',
    'd': 'delta',
    'dg': 'delta gamma',
    'dxl': 'drexel colony',
    'e': 'epsilon',
    'eb': 'epsilon beta',
    'ed': 'epsilon delta',
    "eg": "epsilon gamma",
    'fit': 'fit colony',
    'gb': 'gamma beta',
    'h': 'eta',
    'hd': 'eta delta',
    'he': 'eta epsilon',
    'hg': 'eta gamma',
    'id': 'iota delta',
    'ie': 'iota epsilon',
    'ig': 'iota gamma',
    'jmu': 'jmu colony',
    'k': 'kappa',
    'kb': 'kappa beta',
    'kd': 'kappa delta',
    'ke': 'kappa epsilon',
    'kg': 'kappa gamma',
    'lb': 'lambda beta',
    'ld': 'lambda delta',
    'le': 'lambda epsilon',
    'lg': 'lambda gamma',
    'm': 'mu',
    'md': 'mu delta',
    'me': 'mu epsilon',
    'mg': 'mu gamma',
    'nau': 'nau colony',
    'nd': 'nu delta',
    'ne': 'nu epsilon',
    'ng': 'nu gamma',
    'njit': 'njit colony',
    'o': 'omicron',
    'ob': 'omicron beta',
    'od': 'omicron delta',
    'og': 'omicron gamma',
    'omb': 'omega beta',
    'omg': 'omega',
    'omga': 'omega gamma',
    'omgd': 'omega delta',
    'p': 'rho',
    'pb': 'rho beta',
    'pd': 'rho delta',
    'pg': 'rho gamma',
    'phd': 'phi delta',
    'phg': 'phi gamma',
    'phi': 'phi',
    'pi': 'pi',
    'pid': 'pi delta',
    'pig': 'pi gamma',
    'psb': 'psi beta',
    'psd': 'psi delta',
    'psg': 'psi gamma',
    'row': 'row colony',
    's': 'sigma',
    'scu': 'scu colony',
    'sd': 'sigma delta',
    'sg': 'sigma gamma',
    't': 'tau',
    'tb': 'tau beta',
    'td': 'tau delta',
    'test': 'test',
    'tg': 'tau gamma',
    'thd': 'theta delta',
    'the': 'theta epsilon',
    'thg': 'theta gamma',
    'tu': 'tu colony',
    'u': 'upsilon',
    'ub': 'upsilon beta',
    'ucsb': 'ucsb colony',
    'ud': 'upsilon delta',
    'ug': 'upsilon gamma',
    'unh': 'unh colony',
    'uw': 'uw colony',
    'vic': 'victoria colony',
    'x': 'chi',
    'xb': 'chi beta',
    'xd': 'chi delta',
    'xg': 'chi gamma',
    'xi': 'xi',
    'xib': 'xi beta',
    'xid': 'xi delta',
    'xig': 'xi gamma',
    'z': 'zeta',
    'zd': 'zeta delta',
    'ze': 'zeta epsilon',
    'zg': 'zeta gamma',
}


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

    def events_last_month(self):
        return self.events.filter(date__lte=TODAY_END, date__gte=TODAY_END - timedelta(30))

    def events_semester(self):
        semester_start = semester_start_date()
        return self.events.filter(date__lte=TODAY_END, date__gte=semester_start)

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

    def get_current_officers_council(self, combine=True):
        return annotate_role_status(
            self.members.filter(
                roles__role__in=CHAPTER_OFFICER,
                roles__start__lte=TODAY_END, roles__end__gte=TODAY_END
            ), combine=combine)

    def next_badge_number(self):
        return self.members.filter(~models.Q(status__status='pnm'),
                                   ~models.Q(badge_number=999999999)
                                   ).aggregate(models.Max('badge_number'))

    @classmethod
    def schools(cls):
        try:
            return [(school['pk'], school['school']) for school in cls.objects.values('school', 'pk').order_by('school')]
        except ProgrammingError:
            warnings.warn("Could not find school relation")
            return []

    @classmethod
    def get_school_chapter(cls, school_name):
        try:
            return cls.objects.get(
                school=school_name,
            )
        except cls.DoesNotExist:
            warnings.warn("Could not find school")
            return None



class ChapterCurricula(models.Model):
    chapter = models.ForeignKey(Chapter,
                                on_delete=models.CASCADE,
                                related_name="curricula")
    major = models.CharField(max_length=100)
