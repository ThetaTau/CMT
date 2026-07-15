import datetime
import os
import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django_userforeignkey.models.fields import UserForeignKey
from email_signals.models import EmailSignalMixin

from core.models import (
    BIENNIUM_END_DATE,
    BIENNIUM_START_DATE,
    CHAPTER_OFFICER_CHOICES,
    TimeStampedModel,
    YearTermModel,
    semester_encompass_start_end_date,
    user_is_national_officer,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.scores.models import ScoreType


def get_event_upload_event(instance, filename):
    chapter_slug = instance.chapter.slug if instance.chapter_id else "national"
    return os.path.join("event-pictures", instance.type.slug, f"{chapter_slug}_{filename}")


class EventQuerySet(models.QuerySet):
    """Chainable helpers for the extended :class:`Event` model."""

    def national(self):
        return self.filter(is_national=True)

    def public(self):
        return self.filter(is_public=True)

    def sub_events(self):
        """Events that are children of another event."""
        return self.filter(parent_event__isnull=False)

    def top_level(self):
        """Events that are not children of another event."""
        return self.filter(parent_event__isnull=True)

    def approved(self):
        return self.filter(approval_status=Event.ApprovalStatus.APPROVED)

    def pending(self):
        return self.filter(approval_status=Event.ApprovalStatus.PENDING)

    def rejected(self):
        return self.filter(approval_status=Event.ApprovalStatus.REJECTED)

    def cross_chapter_visible(self):
        """Public events that have been approved are visible to every chapter."""
        return self.filter(is_public=True, approval_status=Event.ApprovalStatus.APPROVED)

    def visible_to_chapter(self, chapter):
        """Events a given chapter may see.

        A chapter always sees its own events, plus any public event that has
        been approved (cross-chapter visible). Public events that are still
        pending/rejected remain visible only to their originating chapter.
        """
        return self.filter(
            models.Q(chapter=chapter) | models.Q(is_public=True, approval_status=Event.ApprovalStatus.APPROVED)
        ).distinct()

    def alive(self):
        """Events that have not been soft-deleted."""
        return self.filter(deleted=False)

    def dead(self):
        """Soft-deleted events."""
        return self.filter(deleted=True)


_EventQuerySetManager = models.Manager.from_queryset(EventQuerySet)


class EventManager(_EventQuerySetManager):
    """Default manager — hides soft-deleted events so they automatically drop
    out of scoring, listings, calendars, and feeds everywhere ``Event.objects``
    (and reverse relations like ``chapter.events`` / ``type.events``) are used.
    """

    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)


class AllEventManager(_EventQuerySetManager):
    """Unfiltered manager including soft-deleted events (admin / restore / audit)."""


def can_delete_event(user, event):
    """Whether ``user`` may soft-delete ``event``.

    Only chapter officers of the event's own chapter may delete it (National
    Officers and superusers may delete any event, including national ones).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_national_officer_group:
        return True
    if event.chapter_id and user.is_chapter_officer_group:
        current = user.current_chapter
        if current is not None and current.pk == event.chapter_id:
            return True
    return False


class Event(TimeStampedModel, EmailSignalMixin):
    class Meta:
        unique_together = ("name", "date", "chapter")
        # ``all_objects`` (unfiltered) is the base manager so cascade deletes and
        # forward-related access still see soft-deleted rows; ``objects`` (which
        # hides soft-deleted events) stays the default for queries and reverse
        # relations such as ``chapter.events`` / ``type.events``.
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    objects = EventManager()
    all_objects = AllEventManager()

    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="events_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="events_modified",
    )
    name = models.CharField("Event Name", max_length=50)
    date = models.DateField("Event Date", default=timezone.now)
    slug = models.SlugField(unique=False)
    type = models.ForeignKey(ScoreType, on_delete=models.PROTECT, related_name="events")
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="events",
        blank=True,
        null=True,
        help_text="The chapter that owns this event. National events are org-wide and not tied to a chapter.",
    )
    region = models.ForeignKey(
        "regions.Region",
        on_delete=models.PROTECT,
        related_name="events",
        blank=True,
        null=True,
        help_text="Region context for the event. Sub-events inherit this from their parent unless overridden.",
    )
    parent_event = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="sub_events",
        blank=True,
        null=True,
        help_text="If this is a sub-event, the parent event it belongs to.",
    )
    is_national = models.BooleanField(
        default=False,
        help_text="National event (organization-wide). Only National Officers may create these.",
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Public event. Public events created by chapter officers require National Officer approval "
        "before they become visible to other chapters.",
    )
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
        help_text="Approval state for public events. Non-public events do not require approval.",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="events_reviewed",
        blank=True,
        null=True,
        verbose_name="Reviewed by",
        help_text="National Officer who approved or rejected this public event.",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True, verbose_name="Reviewed at")
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Optional reason recorded when a public event is rejected.",
    )
    score = models.FloatField(default=0)
    description = models.CharField(max_length=200)
    # users = models.ManyToManyField(settings.AUTH_USER_MODEL,
    #                                related_name="events")
    members = models.PositiveIntegerField(default=0)
    alumni = models.PositiveIntegerField(default=0)
    pledges = models.PositiveIntegerField(default=0, verbose_name="PNMs")
    # Number of non members
    guests = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    stem = models.BooleanField(
        default=False,
        help_text="Does the event relate to Science Technology Engineering or Math (STEM)?",
    )
    host = models.BooleanField(default=False, help_text="Did this event host another chapter?")
    miles = models.PositiveIntegerField(default=0, help_text="Miles traveled to an event hosted by another chapter.")
    raised = models.DecimalField(
        default=0.00,
        decimal_places=2,
        max_digits=10,
        help_text="How many philanthropy funds " "were raised at this event?",
    )
    virtual = models.BooleanField(default=False, help_text="Was your event virtual?")

    # Soft delete — chapter officers may remove an event without destroying the
    # row. Soft-deleted events are excluded from scoring and every listing via
    # the default manager, but kept for audit / restore.
    deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft-deleted events are hidden and excluded from scoring.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True, verbose_name="Deleted at")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="events_deleted",
        blank=True,
        null=True,
        verbose_name="Deleted by",
    )

    def __str__(self):
        return f"{self.name} on {self.date}"

    def get_absolute_url(self):
        return reverse(
            "events:detail",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "slug": self.slug,
            },
        )

    def get_update_url(self):
        return reverse(
            "events:update",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "event_slug": self.slug,
            },
        )

    def get_attendance_url(self):
        """Non-enumerable (date + slug) URL for this event's attendance roster."""
        return reverse(
            "attendance:roster",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "event_slug": self.slug,
            },
        )

    def get_attendance_rollup_url(self):
        """Non-enumerable (date + slug) URL for this event's sub-event rollup."""
        return reverse(
            "attendance:rollup",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "event_slug": self.slug,
            },
        )

    def get_rsvp_url(self):
        """Non-enumerable (date + slug) URL for a member RSVP (WI-10)."""
        return reverse(
            "attendance:rsvp",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "event_slug": self.slug,
            },
        )

    def get_delete_url(self):
        """Non-enumerable (date + slug) URL for the soft-delete confirmation."""
        return reverse(
            "events:delete",
            kwargs={
                "year": self.date.year,
                "month": self.date.month,
                "day": self.date.day,
                "event_slug": self.slug,
            },
        )

    def soft_delete(self, user=None):
        """Mark the event deleted (kept for audit) and drop it from scoring.

        The default manager hides it everywhere; re-running the chapter score
        removes this event's points from the term aggregate.
        """
        self.deleted = True
        self.deleted_at = timezone.now()
        if user is not None and getattr(user, "pk", None):
            self.deleted_by = user
        self.save(calculate_score=False)
        if self.chapter_id is not None:
            self.type.update_chapter_score(self.chapter, self.date)

    def restore(self, user=None):
        """Undo a soft delete and restore the event's points to the aggregate."""
        self.deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(calculate_score=False)
        if self.chapter_id is not None:
            self.type.update_chapter_score(self.chapter, self.date)

    @property
    def is_upcoming(self):
        """True when the event has not yet passed (RSVP is allowed, WI-10)."""
        return self.date >= timezone.localdate()

    # ------------------------------------------------------------------
    # Sub-event / context helpers (WI-1)
    # ------------------------------------------------------------------
    def inherit_context_from_parent(self):
        """Fill in region/chapter context from the parent event when unset.

        A sub-event inherits its parent's chapter and region unless the value
        has been explicitly overridden on the sub-event itself.
        """
        if not self.parent_event_id:
            return
        parent = self.parent_event
        if self.chapter_id is None and parent.chapter_id is not None:
            self.chapter_id = parent.chapter_id
        if self.region_id is None:
            self.region_id = parent.region_id or (parent.chapter.region_id if parent.chapter_id else None)

    @property
    def effective_region(self):
        """The region context for this event, falling back to the chapter/parent."""
        if self.region_id:
            return self.region
        if self.parent_event_id:
            return self.parent_event.effective_region
        return self.chapter.region if self.chapter_id else None

    @property
    def is_sub_event(self):
        return self.parent_event_id is not None

    # ------------------------------------------------------------------
    # Approval helpers (WI-1 / WI-2)
    # ------------------------------------------------------------------
    @classmethod
    def default_approval_status(cls, *, is_public, created_by_national_officer, is_national=False, auto_approve=None):
        """Compute the approval status a new event should start with.

        - National events are always auto-approved (org-wide, National-Officer created).
        - Non-public events never require approval (``APPROVED``).
        - Public events created by a National Officer are auto-approved when the
          configurable ``EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC`` setting is on
          (default), otherwise they enter the pending queue.
        - Public events created by a chapter officer always start ``PENDING``.
        """
        if is_national:
            return cls.ApprovalStatus.APPROVED
        if not is_public:
            return cls.ApprovalStatus.APPROVED
        if created_by_national_officer:
            if auto_approve is None:
                auto_approve = getattr(settings, "EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC", True)
            return cls.ApprovalStatus.APPROVED if auto_approve else cls.ApprovalStatus.PENDING
        return cls.ApprovalStatus.PENDING

    @property
    def requires_approval(self):
        """Only public events participate in the approval workflow."""
        return bool(self.is_public)

    @property
    def is_pending(self):
        return self.requires_approval and self.approval_status == self.ApprovalStatus.PENDING

    @property
    def is_cross_chapter_visible(self):
        """Public + approved events are visible to every chapter."""
        return bool(self.is_public and self.approval_status == self.ApprovalStatus.APPROVED)

    def approve(self, reviewer, commit=True):
        """Mark a public event approved and record who/when reviewed it."""
        self.approval_status = self.ApprovalStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = ""
        if commit:
            self.save(calculate_score=False)
        return self

    def reject(self, reviewer, reason="", commit=True):
        """Mark a public event rejected, optionally storing a reason."""
        self.approval_status = self.ApprovalStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason or ""
        if commit:
            self.save(calculate_score=False)
        return self

    def clean(self):
        super().clean()
        errors = {}
        # Only National Officers may flag an event as national. The acting user
        # is preferred (set by the form/view); fall back to the recorded creator.
        acting_user = getattr(self, "_acting_user", None)
        if acting_user is None and self.created_by_id:
            acting_user = self.created_by
        if self.is_national and acting_user is not None and not user_is_national_officer(acting_user):
            errors["is_national"] = "Only National Officers can create national events."
        # An event cannot be its own parent.
        if self.parent_event_id and self.pk and self.parent_event_id == self.pk:
            errors["parent_event"] = "An event cannot be its own parent."
        if errors:
            raise ValidationError(errors)

    def save(self, calculate_score=True, **kwargs):
        self.slug = slugify(self.name)
        # National events are always public and are not tied to a chapter.
        if self.is_national:
            self.is_public = True
        self.inherit_context_from_parent()
        if calculate_score and self.chapter_id is not None:
            cal_score = self.type.calculate_score(self)
            self.score = cal_score
            super().save(**kwargs)
            self.type.update_chapter_score(self.chapter, self.date)
        else:
            super().save(**kwargs)

    @classmethod
    def chapter_events(cls, chapter):
        result = cls.objects.filter(chapter=chapter)
        return result

    @classmethod
    def calculate_meeting_attendance(cls, chapter, date):
        meeting_type = ScoreType.objects.get(name="Attendance at meetings")
        # Use the same half-open semester window as scoring (ScoreType.chapter_events)
        # so a meeting is grouped into the same term it is scored in.
        semester_start, semester_end = YearTermModel.date_range(date)
        events = cls.objects.filter(
            chapter=chapter,
            type=meeting_type,
            date__gte=semester_start,
            date__lt=semester_end,
        )
        total_percent = 0
        for event in events:
            actives = event.chapter.get_actives_for_date(event.date).count()
            percent_attendance = 0
            if actives:
                percent_attendance = min(event.members / actives, 1)
            total_percent += percent_attendance
        event_count = events.count()
        if not event_count:
            event_count = 1
        avg_attendance = total_percent / event_count
        formula_out = meeting_type.special
        formula_out = formula_out.replace("MEETINGS", str(avg_attendance))
        score = eval(formula_out)
        event_score = round(score / event_count, 2)
        for event in events:
            event.score = event_score
            event.save(calculate_score=False)
        return event_score

    @classmethod
    def count_events_biennium(cls, date=None, chapters=None):
        if date is None:
            query = cls.objects.filter(date__gte=BIENNIUM_START_DATE, date__lte=BIENNIUM_END_DATE)
        else:
            semester_start, semester_end = semester_encompass_start_end_date(date)
            cls.objects.filter(date__gte=semester_start, date__lte=semester_end)
        if chapters is None:
            chapters = Chapter.objects.exclude(active=False)
        events = (
            query.filter(chapter__in=chapters)
            .values("chapter", "type__section")
            .annotate(
                section_count=models.Count("name"),
                region=models.F("chapter__region__name"),
                chapter_name=models.F("chapter__name"),
            )
            .order_by("chapter_name")
        )
        grouped_events = {}
        for event in events:
            chapter = event["chapter"]
            event[f"{event.pop('type__section')}"] = event.pop("section_count")
            chapter_dict = grouped_events.get(chapter, {"Bro": 0, "Ops": 0, "Ser": 0, "Pro": 0})
            chapter_dict.update(event)
            grouped_events[chapter] = chapter_dict
        for chapter, score in grouped_events.items():
            grouped_events[chapter]["total"] = round(score["Bro"] + score["Ops"] + score["Ser"] + score["Pro"], 2)
        return grouped_events.values()


def get_event_picture_upload_path(instance, filename):  # instance refers to object road to data base
    chapter_slug = instance.event.chapter.slug if instance.event.chapter_id else "national"
    return os.path.join(
        "event-pictures",
        f"{chapter_slug}",  # name of chapter
        f"{filename}",  # name of file submitted
    )


class Picture(TimeStampedModel):
    description = models.TextField()
    image = models.ImageField(upload_to=get_event_picture_upload_path)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="pictures",
    )


# How far back the iCal feed reaches; keeps the .ics payload small (WI iCal).
ICAL_FEED_PAST_WEEKS = 4


class CalendarFeedSubscription(TimeStampedModel):
    """A member-configured, privately-tokenised iCalendar subscription.

    The feed only ever exposes **cross-chapter-visible** content — approved
    public events of the selected chapters/regions and national events — plus,
    optionally, the member's own chapter's outstanding to-dos. The random
    ``token`` makes the feed URL unguessable so it cannot be scraped.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_feeds",
    )
    name = models.CharField(max_length=100, default="My Theta Tau Calendar")
    include_national = models.BooleanField(
        default=True,
        help_text="Include national (organization-wide) events.",
    )
    include_todos = models.BooleanField(
        default=False,
        help_text="Include your chapter's outstanding to-dos (as calendar tasks).",
    )
    task_owner_roles = ArrayField(
        models.CharField(max_length=50, choices=CHAPTER_OFFICER_CHOICES),
        blank=True,
        default=list,
        help_text="Limit to-dos to these officer roles' tasks (empty = every role's tasks).",
    )
    chapters = models.ManyToManyField(
        Chapter,
        blank=True,
        related_name="calendar_feeds",
        help_text="Public events from these chapters.",
    )
    regions = models.ManyToManyField(
        "regions.Region",
        blank=True,
        related_name="calendar_feeds",
        help_text="Public events from every chapter in these regions.",
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.name} ({self.user})"

    def get_feed_path(self):
        return reverse("events:ical", kwargs={"token": self.token})

    def events_queryset(self, start_date=None):
        """Cross-chapter-visible events matching this subscription's scope.

        Reuses the WI-2 rule (public + approved) — pending / rejected public
        events are never exposed. National events are org-wide.
        """
        if start_date is None:
            start_date = timezone.localdate() - datetime.timedelta(weeks=ICAL_FEED_PAST_WEEKS)
        scope = models.Q(pk__in=[])  # start empty; OR in each enabled source
        if self.include_national:
            scope |= models.Q(is_national=True)
        chapter_ids = list(self.chapters.values_list("pk", flat=True))
        region_ids = list(self.regions.values_list("pk", flat=True))
        approved_public = models.Q(is_public=True, approval_status=Event.ApprovalStatus.APPROVED)
        if chapter_ids:
            scope |= models.Q(chapter_id__in=chapter_ids) & approved_public
        if region_ids:
            scope |= models.Q(chapter__region_id__in=region_ids) & approved_public
        return (
            Event.objects.filter(scope)
            .filter(date__gte=start_date)
            .select_related("chapter", "type")
            .order_by("date", "name")
            .distinct()
        )

    def todos_queryset(self, start_date=None):
        """The member's chapter's outstanding to-dos (empty unless opted in)."""
        if not self.include_todos:
            return None
        chapter = getattr(self.user, "current_chapter", None)
        if chapter is None:
            return None
        if start_date is None:
            start_date = timezone.localdate() - datetime.timedelta(weeks=ICAL_FEED_PAST_WEEKS)
        from thetatauCMT.tasks.models import TaskDate

        todos = (
            TaskDate.incomplete_dates_for_chapter(chapter)
            .filter(date__gte=start_date)
            .select_related("task")
            .order_by("date")
        )
        if self.task_owner_roles:
            todos = todos.filter(task__owner__in=self.task_owner_roles)
        return todos
