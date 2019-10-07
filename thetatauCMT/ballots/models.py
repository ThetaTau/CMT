import os
from enum import Enum
from datetime import datetime, timedelta
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from core.models import TimeStampedModel, ALL_OFFICERS_CHOICES


def get_ballot_attachment_upload_path(instance, filename):
    return os.path.join(
        'ballots', instance.ballot_type,
        f"{instance.slug}_{filename}")


def return_date_time():
    now = datetime.today()
    return now + timedelta(days=30)


class Ballot(TimeStampedModel):
    class Meta:
        unique_together = ('name', 'due_date')

    class TYPES(Enum):
        colony = ('colony', 'Colony Petition')
        chapter = ('chapter', 'Chapter Petition')
        suspension = ('suspension', 'Suspension')
        other = ('other', 'Other')

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    class VOTERS(Enum):
        convention = ('convention', 'Theta Tau Convention')
        council = ('council', 'Theta Tau Executive Council')
        nat_off = ('nat_off', 'Theta Tau National Officers')

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    sender = models.CharField("From", max_length=50, default="Grand Scribe")
    slug = models.SlugField(unique=False)
    # eg. NJIT Colony Petition
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20, choices=[x.value for x in TYPES])
    attachment = models.FileField(
        upload_to=get_ballot_attachment_upload_path, null=True, blank=True)
    description = models.TextField()
    due_date = models.DateField(default=return_date_time)
    voters = models.CharField(
        max_length=50, default="convention",
        choices=[x.value for x in VOTERS])

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse('users:detail')

    def save(self):
        self.slug = slugify(self.name)
        super().save()

    @property
    def ayes(self):
        return self.completed.filter(motion='aye').count()

    @property
    def nays(self):
        return self.completed.filter(motion='nay').count()

    @property
    def abstains(self):
        return self.completed.filter(motion='abstain').count()

    @classmethod
    def counts(cls):
        return cls.objects.values('name', 'type', 'due_date', 'voters', 'slug',
                                  'pk'). \
            annotate(
            ayes=models.Count('completed__motion',
                              filter=models.Q(completed__motion='aye')),
            nays=models.Count('completed__motion',
                              filter=models.Q(completed__motion='nay')),
            abstains=models.Count('completed__motion',
                                  filter=models.Q(completed__motion='abstain')),
        )


class BallotComplete(TimeStampedModel):
    class Meta:
        unique_together = ('user', 'ballot')

    class MOTION(Enum):
        aye = ('aye', 'Aye')
        nay = ('nay', 'Nay')
        abstain = ('abstain', 'Abstain')
        incomplete = ('incomplete', 'Incomplete')

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    ROLES = ALL_OFFICERS_CHOICES

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="ballots")
    ballot = models.ForeignKey(Ballot,
                               on_delete=models.CASCADE,
                               related_name="completed")
    motion = models.CharField(max_length=20, choices=[x.value for x in MOTION])
    role = models.CharField(max_length=50, choices=ROLES)
