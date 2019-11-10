import os
from enum import Enum
from datetime import datetime, timedelta
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from core.models import TimeStampedModel, ALL_OFFICERS_CHOICES
from users.models import UserRoleChange
from tasks.models import Task, TaskDate, TaskChapter


def get_ballot_attachment_upload_path(instance, filename):
    return os.path.join(
        'ballots', instance.type,
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

        @classmethod
        def get_access(cls, level):
            return {
                '': [],
                'convention': ['convention'],
                'nat_off': ['convention', 'nat_off'],
                'council': ['convention', 'nat_off', 'council'],
            }[level]

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
        if self.voters == 'convention' and not self.pk:
            new_task = Task(
                name=self.name,
                owner='regent',
                type='form',
                resource='ballots:vote',
                description=f"{self.TYPES.get_value(self.type)}: {self.description}",
            )
            new_task.save()
            due_date = TaskDate(
                task=new_task,
                school_type='all',
                date=self.due_date,
            )
            due_date.save()
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
        # django-sql-utils SubQueryCount is not needed provided values does not
        # NOT have the item filtering against, eg. completed__motion should
        # NOT be in the values() list as it will show up multiple times
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

    @classmethod
    def user_ballots(cls, user):
        voted = BallotComplete.objects.filter(
            ballot=models.OuterRef('pk'), user=user)
        role_level, _ = user.get_user_role_level()
        filter_list = cls.VOTERS.get_access(role_level)
        if role_level == 'convention':
            natoffs = UserRoleChange.get_current_natoff().values_list('user__pk', flat=True)
            voted = BallotComplete.objects.filter(
                ~models.Q(user__in=natoffs),  # Natoff vote should not count for chapter
                ballot=models.OuterRef('pk'), user__chapter=user.chapter)
        ballot_query = cls.objects.values('name', 'type', 'due_date',
                                          'voters', 'slug', 'pk').\
            filter(voters__in=filter_list).annotate(
                motion=models.Subquery(voted.values('motion'))
                )
        return ballot_query

    def get_completed(self, user):
        role_level, _ = user.get_user_role_level()
        if role_level == 'convention':
            natoffs = UserRoleChange.get_current_natoff().values_list('user__pk', flat=True)
            query = self.completed.filter(
                ~models.Q(user__in=natoffs), user__chapter=user.chapter
            )
        else:
            query = self.completed.filter(user=user)
        return query.first()


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

    def save(self):
        natoffs = UserRoleChange.get_current_natoff().values_list('user__pk', flat=True)
        if self.ballot.voters == 'convention' and self.user.pk not in natoffs:
            task = Task.objects.filter(
                name=self.ballot.name,
                ).first()
            task_date = TaskDate.objects.filter(
                task=task
            ).first()
            task_complete = TaskChapter(
                task=task_date,
                chapter=self.user.chapter,
            )
            task_complete.save()
        super().save()
