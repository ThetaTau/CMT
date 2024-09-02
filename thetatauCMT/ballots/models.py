import os
from enum import Enum
from datetime import datetime, timedelta
from multiselectfield import MultiSelectField
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from core.models import (
    TimeStampedModel,
    ALL_OFFICERS_CHOICES,
    NAT_OFFICERS_CHOICES,
    CHAPTER_OFFICER,
)
from users.models import UserRoleChange
from tasks.models import Task, TaskDate, TaskChapter


def get_ballot_attachment_upload_path(instance, filename):
    return os.path.join("ballots", instance.type, f"{instance.slug}_{filename}")


def return_date_time():
    now = datetime.today()
    return now + timedelta(days=30)


class MultiSelectField(MultiSelectField):
    # Not Django 2.0+ ready yet, https://github.com/goinnn/django-multiselectfield/issues/74
    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


class Ballot(TimeStampedModel):
    class Meta:
        unique_together = ("name", "due_date")

    class TYPES(Enum):
        candidate_chapter = ("candidate_chapter", "Candidate Chapter Petition")
        chapter = ("chapter", "Chapter Petition")
        suspension = ("suspension", "Suspension")
        other = ("other", "Other")

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    VOTERS = [("all_chapters", "All Chapters")] + NAT_OFFICERS_CHOICES

    sender = models.CharField("From", max_length=50, default="Grand Scribe")
    slug = models.SlugField(unique=False)
    # eg. NJIT Candidate Chapter Petition
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20, choices=[x.value for x in TYPES])
    attachment = models.FileField(
        upload_to=get_ballot_attachment_upload_path, null=True, blank=True
    )
    description = models.TextField()
    due_date = models.DateField(default=return_date_time)
    voters = MultiSelectField(
        "Who is allowed to vote on this ballot?", choices=VOTERS, max_length=500
    )

    def __str__(self):
        return f"{self.name}"

    def save(self):
        self.slug = slugify(self.name)
        if "all_chapters" in self.voters and not self.pk:
            new_task = Task(
                name=self.name,
                owner="regent",
                type="form",
                resource="ballots:vote",
                description=f"{self.TYPES.get_value(self.type)}: {self.description}",
            )
            new_task.save()
            due_date = TaskDate(
                task=new_task,
                school_type="all",
                date=self.due_date,
            )
            due_date.save()
        super().save()

    @property
    def ayes(self):
        return self.completed.filter(motion="aye").count()

    @property
    def nays(self):
        return self.completed.filter(motion="nay").count()

    @property
    def abstains(self):
        return self.completed.filter(motion="abstain").count()

    @classmethod
    def counts(cls):
        # django-sql-utils SubQueryCount is not needed provided values does not
        # NOT have the item filtering against, eg. completed__motion should
        # NOT be in the values() list as it will show up multiple times
        return cls.objects.values(
            "name", "type", "due_date", "voters", "slug", "pk"
        ).annotate(
            ayes=models.Count(
                "completed__motion", filter=models.Q(completed__motion="aye")
            ),
            nays=models.Count(
                "completed__motion", filter=models.Q(completed__motion="nay")
            ),
            abstains=models.Count(
                "completed__motion", filter=models.Q(completed__motion="abstain")
            ),
        )

    @classmethod
    def user_ballots(cls, user):
        voted = BallotComplete.objects.filter(ballot=models.OuterRef("pk"), user=user)
        completed = BallotComplete.objects.filter(user=user).values_list(
            "ballot__pk", flat=True
        )
        roles = user.current_roles
        roles = roles if roles is not None else []
        chapter_officer = list(set(roles) & set(CHAPTER_OFFICER))
        if chapter_officer:
            roles.append("all_chapters")
        condition = models.Q(voters__contains=roles[0])
        for role in roles[1:]:
            condition |= models.Q(voters__contains=role)
        ballot_query_current = (
            cls.objects.values("name", "type", "due_date", "voters", "slug", "pk")
            .filter(condition)
            .annotate(motion=models.Subquery(voted.values("motion")))
        )
        ballot_query_past = (
            cls.objects.values("name", "type", "due_date", "voters", "slug", "pk")
            .filter(pk__in=completed)
            .exclude(pk__in=ballot_query_current.values_list("pk", flat=True))
            .annotate(motion=models.Subquery(voted.values("motion")))
        )
        return ballot_query_current | ballot_query_past

    def get_completed(self, user):
        query = self.completed.filter(user=user)
        return query.first()


class BallotComplete(TimeStampedModel):
    class Meta:
        unique_together = ("user", "ballot")

    class MOTION(Enum):
        aye = ("aye", "Aye")
        nay = ("nay", "Nay")
        abstain = ("abstain", "Abstain")
        incomplete = ("incomplete", "Incomplete")

        @classmethod
        def get_value(cls, member):
            return cls[member.lower()].value[1]

    ROLES = ALL_OFFICERS_CHOICES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ballots"
    )
    ballot = models.ForeignKey(
        Ballot, on_delete=models.CASCADE, related_name="completed"
    )
    motion = models.CharField(max_length=20, choices=[x.value for x in MOTION])
    role = models.CharField(max_length=50, choices=ROLES)

    def save(self):
        natoffs = UserRoleChange.get_current_natoff().values_list("user__pk", flat=True)
        if "all_chapters" in self.ballot.voters and self.user.pk not in natoffs:
            task = Task.objects.filter(
                name=self.ballot.name,
            ).first()
            task_date = TaskDate.objects.filter(task=task).first()
            if not TaskChapter.check_previous(task_date, self.user.chapter):
                task_complete = TaskChapter(
                    task=task_date,
                    chapter=self.user.chapter,
                )
                task_complete.save()
        super().save()
