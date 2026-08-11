import os
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from multiselectfield import MultiSelectField

from core.models import ALL_OFFICERS_CHOICES, NAT_OFFICERS_CHOICES, TimeStampedModel
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate
from thetatauCMT.users.models import UserRoleChange

# A chapter casts a single vote; only these two officers may cast it.
BALLOT_CHAPTER_ROLES = ["regent", "scribe"]

# Only these national officers may see how anyone voted.
BALLOT_RESULT_ROLES = ["grand regent", "grand scribe"]

# Voting closes at 5pm Pacific on the due date, which is what the ballot emails
# tell every voter. Pacific rather than the site's Phoenix time zone because
# that is the deadline the Grand Scribe publishes.
BALLOT_CLOSE_TIME = time(17, 0)
BALLOT_CLOSE_ZONE = ZoneInfo("America/Los_Angeles")


def ballot_closes_at(due_date):
    """Aware datetime at which a ballot due on ``due_date`` stops accepting votes."""
    return datetime.combine(due_date, BALLOT_CLOSE_TIME, tzinfo=BALLOT_CLOSE_ZONE)


def can_view_ballot_results(user):
    """Whether ``user`` may see the motions cast and the aye/nay/abstain tallies.

    Every officer can see *who has and has not* returned a ballot; only the
    Grand Regent and Grand Scribe (and Admins) may see the votes themselves.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "natoff_hidden", False):
        return False
    if getattr(user, "is_admin", False):
        return True
    return bool(set(user.current_roles or []) & set(BALLOT_RESULT_ROLES))


def voter_role_query(role):
    """Q matching one whole entry of the comma separated ``voters`` list.

    ``voters__contains="regent"`` also matches "grand regent" and "vice regent",
    so every boundary has to be spelled out.
    """
    return (
        models.Q(voters=role)
        | models.Q(voters__startswith=f"{role},")
        | models.Q(voters__endswith=f",{role}")
        | models.Q(voters__contains=f",{role},")
    )


def get_ballot_attachment_upload_path(instance, filename):
    return os.path.join("ballots", instance.type, f"{instance.slug}_{filename}")


def return_date_time():
    return timezone.localdate() + timedelta(days=30)


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
    attachment = models.FileField(upload_to=get_ballot_attachment_upload_path, null=True, blank=True)
    description = models.TextField()
    due_date = models.DateField(default=return_date_time)
    voters = MultiSelectField("Who is allowed to vote on this ballot?", choices=VOTERS, max_length=500)

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse("ballots:detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        previous_due = None
        if not self._state.adding:
            previous_due = Ballot.objects.filter(pk=self.pk).values_list("due_date", flat=True).first()
        super().save(*args, **kwargs)
        if "all_chapters" in self.voters:
            self.sync_chapter_task(previous_due)

    def sync_chapter_task(self, previous_due=None):
        """Put the ballot on every chapter's task list, owned by the Regent.

        ``Task.slug`` is unique on ``name + owner``, so a ballot re-run under the
        same name reuses the existing task and only adds the new due date.
        Editing the due date moves this ballot's date rather than leaving the
        chapters looking at a deadline that no longer exists.
        """
        task, _ = Task.objects.get_or_create(
            slug=slugify(f"{self.name}regent"),
            defaults=dict(
                name=self.name,
                owner="regent",
                type="form",
                resource="ballots:vote",
                description=f"{self.TYPES.get_value(self.type)}: {self.description}"[:1000],
            ),
        )
        dates = TaskDate.objects.filter(task=task, school_type="all")
        if previous_due and previous_due != self.due_date and not dates.filter(date=self.due_date).exists():
            dates.filter(date=previous_due).update(date=self.due_date)
        TaskDate.objects.get_or_create(task=task, school_type="all", date=self.due_date)
        return task

    @classmethod
    def get_by_slug(cls, slug):
        """Newest ballot for ``slug``.

        ``slug`` is not unique (``unique_together`` is name + due date), so a
        ballot re-run under the same name would otherwise raise
        ``MultipleObjectsReturned``.
        """
        return cls.objects.filter(slug=slug).order_by("-due_date", "-pk").first()

    @property
    def closes_at(self):
        return ballot_closes_at(self.due_date)

    @property
    def closes_time_display(self):
        closes = self.closes_at
        hour = closes.hour % 12 or 12
        meridiem = "am" if closes.hour < 12 else "pm"
        return f"{hour}:{closes.minute:02d} {meridiem} {closes:%Z}"

    @property
    def closes_display(self):
        return f"{self.closes_at:%b %d, %Y} at {self.closes_time_display}"

    @property
    def is_open(self):
        return timezone.now() < self.closes_at

    @property
    def is_due_today(self):
        return self.due_date == timezone.localdate()

    @property
    def days_open(self):
        """Days since the ballot went out, which drives the reminder ladder.

        Both sides are read in the project time zone; ``created`` is stored in
        UTC, so comparing it against the server's local date is off by one for
        part of every day.
        """
        return (timezone.localdate() - timezone.localtime(self.created).date()).days

    @property
    def roles_allowed(self):
        """Every role that may cast a vote, chapter officers included."""
        roles = list(self.voters)
        if "all_chapters" in roles:
            roles += BALLOT_CHAPTER_ROLES
        return roles

    def voting_roles_for(self, user):
        return sorted(set(user.current_roles or []) & set(self.roles_allowed))

    @property
    def voters_display(self):
        display = ", ".join(val[1] for val in self.VOTERS if val[0] in self.voters)
        return display.replace("All Chapters", "Chapter Regent or Scribe")

    def chapter_vote(self, chapter):
        """The single vote cast on behalf of ``chapter``, if any."""
        if chapter is None:
            return None
        return self.completed.filter(user__chapter=chapter, role__in=BALLOT_CHAPTER_ROLES).first()

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
        return cls.objects.values("name", "type", "due_date", "voters", "slug", "pk").annotate(
            submitted=models.Count("completed", distinct=True),
            ayes=models.Count("completed__motion", filter=models.Q(completed__motion="aye")),
            nays=models.Count("completed__motion", filter=models.Q(completed__motion="nay")),
            abstains=models.Count("completed__motion", filter=models.Q(completed__motion="abstain")),
        )

    def outstanding_national_voters(self):
        """Current national officers holding a voting role who have not voted."""
        voted = self.completed.values_list("user_id", flat=True)
        return UserRoleChange.get_current_natoff().filter(role__in=list(self.voters)).exclude(user_id__in=voted)

    def outstanding_chapters(self):
        """Active chartered chapters that still owe a vote."""
        from thetatauCMT.chapters.models import Chapter

        if "all_chapters" not in self.voters:
            return Chapter.objects.none()
        voted = self.completed.filter(role__in=BALLOT_CHAPTER_ROLES).values_list("user__chapter_id", flat=True)
        # Candidate chapters do not get a vote.
        return Chapter.objects.filter(active=True, candidate_chapter=False).exclude(pk__in=voted)

    @classmethod
    def voter_roles_for(cls, user):
        """The user's roles, plus ``all_chapters`` when they can cast the chapter vote."""
        roles = list(user.current_roles) if user.current_roles else []
        if set(roles) & set(BALLOT_CHAPTER_ROLES):
            roles.append("all_chapters")
        return roles

    @classmethod
    def voter_condition(cls, roles):
        condition = models.Q(pk__in=[])
        for role in roles:
            condition |= voter_role_query(role)
        return condition

    @classmethod
    def open_ballots(cls):
        """Ballots still accepting votes right now.

        The 5pm close is a time of day, so once it has passed the ballots due
        today drop out even though it is still their due date.
        """
        today = timezone.localdate()
        query = cls.objects.filter(due_date__gte=today)
        if timezone.now() >= ballot_closes_at(today):
            query = query.exclude(due_date=today)
        return query

    @classmethod
    def outstanding_for_user(cls, user):
        """Open ballots this user, or their chapter, still owes a vote on."""
        if not getattr(user, "is_authenticated", False):
            return cls.objects.none()
        roles = cls.voter_roles_for(user)
        if not roles:
            return cls.objects.none()
        voted = models.Q(completed__user=user)
        if "all_chapters" in roles and getattr(user, "chapter_id", None):
            voted |= models.Q(
                completed__user__chapter_id=user.chapter_id,
                completed__role__in=BALLOT_CHAPTER_ROLES,
            )
        return cls.open_ballots().filter(cls.voter_condition(roles)).exclude(voted).order_by("due_date")

    @classmethod
    def user_ballots(cls, user):
        roles = list(user.current_roles) if user.current_roles else []
        chapter_officer = list(set(roles) & set(BALLOT_CHAPTER_ROLES))
        own = models.Q(user=user)
        if chapter_officer and getattr(user, "chapter_id", None):
            # A chapter votes once: the Regent sees the vote the Scribe cast.
            own |= models.Q(user__chapter_id=user.chapter_id, role__in=BALLOT_CHAPTER_ROLES)
        voted = BallotComplete.objects.filter(own, ballot=models.OuterRef("pk")).order_by("-created")
        completed = BallotComplete.objects.filter(own).values_list("ballot__pk", flat=True)
        condition = cls.voter_condition(cls.voter_roles_for(user))
        ballot_query_current = (
            cls.objects.values("name", "type", "due_date", "voters", "slug", "pk")
            .filter(condition)
            .annotate(motion=models.Subquery(voted.values("motion")[:1]))
        )
        ballot_query_past = (
            cls.objects.values("name", "type", "due_date", "voters", "slug", "pk")
            .filter(pk__in=completed)
            .exclude(pk__in=ballot_query_current.values_list("pk", flat=True))
            .annotate(motion=models.Subquery(voted.values("motion")[:1]))
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

    # "incomplete" is a display state for voters who have not returned a ballot,
    # never something anyone can select.
    VOTE_CHOICES = [motion.value for motion in MOTION if motion.value[0] != "incomplete"]

    ROLES = ALL_OFFICERS_CHOICES

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ballots")
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name="completed")
    motion = models.CharField(max_length=20, choices=[x.value for x in MOTION])
    role = models.CharField(max_length=50, choices=ROLES)

    def __str__(self):
        return f"{self.user} on {self.ballot}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.mark_chapter_task_complete()

    def mark_chapter_task_complete(self):
        """Tick the chapter's ballot task once its Regent or Scribe has voted."""
        if "all_chapters" not in self.ballot.voters:
            return
        if self.role not in BALLOT_CHAPTER_ROLES:
            return
        chapter = self.user.chapter
        if chapter is None:
            return
        task = Task.objects.filter(slug=slugify(f"{self.ballot.name}regent")).first()
        if task is None:
            return
        task_date = TaskDate.objects.filter(task=task, date=self.ballot.due_date).first()
        if task_date is None:
            return
        if not TaskChapter.check_previous(task_date, chapter):
            # get_or_create absorbs the unique_together race two officers can hit.
            TaskChapter.objects.get_or_create(task=task_date, chapter=chapter, date=timezone.localdate())
