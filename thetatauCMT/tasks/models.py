import datetime
from datetime import timedelta

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.html import mark_safe
from django.utils.text import slugify
from django_userforeignkey.models.fields import UserForeignKey
from email_signals.models import EmailSignalMixin

from core.models import ALL_ROLES_CHOICES, TODAY_END, academic_encompass_start_end_date
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.scores.models import ScoreType


class Task(models.Model):
    class Meta:
        ordering = [
            "name",
        ]

    TYPES = [
        ("sub", "Submission"),
        ("form", "Forms"),
        ("task", "Task"),
        ("bal", "Balance"),
    ]
    OWNERS = ALL_ROLES_CHOICES
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    owner = models.CharField(max_length=50, choices=OWNERS)
    type = models.CharField(max_length=4, choices=TYPES)
    days_advance = models.PositiveIntegerField(default=90)
    resource = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=1000)
    submission_type = models.ForeignKey(ScoreType, on_delete=models.CASCADE, related_name="task", blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name + self.owner)
        super().save(*args, **kwargs)

    @property
    def render_task_link(self):
        value = ""
        resource = self.resource
        task_type = self.type
        if task_type == "sub" and self.submission_type:
            value = mark_safe(
                "<a href=" + reverse("submissions:add-direct", args=(self.submission_type.slug,)) + ">Submission</a>"
            )
        elif "http" in resource:
            value = mark_safe(f'<a href="{resource}">Form</a>')
        elif ":" in resource:
            if "ballot" in resource:
                value = mark_safe("<a href=" + reverse(resource, args=(slugify(self.name),)) + ">Ballot</a>")
            else:
                value = mark_safe("<a href=" + reverse(resource) + ">Form</a>")
        return value

    def all_dates_for_task_chapter(self, chapter):
        school_type = chapter.school_type
        dates = self.dates.filter(
            Q(school_type=school_type) | Q(school_type="all"),
            archived=False,
        ).all()
        return dates

    def incomplete_dates_for_task_chapter(self, chapter):
        school_type = chapter.school_type
        max_date = TODAY_END + timedelta(self.days_advance)
        # (Todays date + days_advance) > due date
        # Mar 16 + 30 days -> April 15,
        # if due date is April 15 then lte max_date and is a due date
        # You have this many days to submit the task
        min_date = TODAY_END - (timedelta(self.days_advance * 2))
        # ``archived`` dates are retired ("no longer needed") and must never be
        # surfaced as incomplete work nor auto-completed by ``mark_complete``.
        dates = self.dates.filter(
            Q(school_type=school_type) | Q(school_type="all"),
            ~Q(chapters__chapter=chapter),
            Q(date__lte=max_date),
            Q(date__gte=min_date),
            archived=False,
        ).all()
        return dates

    def completed_last(self, chapter):
        completed = (
            TaskChapter.objects.filter(
                id__in=self.dates.filter(chapters__chapter=chapter).values_list("chapters", flat=True)
            )
            .order_by("date")
            .last()
        )
        if completed:
            return completed.submission_object

    @classmethod
    def mark_complete(cls, name, chapter, current_roles=None, user=None, obj=None):
        extra = {}
        if current_roles:
            extra = {"owner__in": current_roles}
        task = Task.objects.filter(name=name, **extra).first()
        if not task:
            return
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if not next_date:
            return
        task_obj = TaskChapter(task=next_date, chapter=chapter, date=timezone.now())
        if obj:
            from thetatauCMT.submissions.models import Submission

            extra_info = None
            create_submission = True
            submit_obj = obj
            if name == "Audit":
                score_type = ScoreType.objects.filter(slug="audit").first()
                file = f"forms:audit_complete {obj.pk}"
                submit_name = f"Audit by {task.owner}"
            elif name == "Pledge Program":
                score_type = ScoreType.objects.filter(slug="pledge-program").first()
                file = "forms:pledge_program"
                submit_name = "Pledge program"
                extra_info = {"unmodified": obj.manual != "other"}
            elif name == "Outstanding Student Member":
                score_type = ScoreType.objects.filter(slug="osm").first()
                file = "osmform"
                submit_name = "Outstanding Student Member"
            else:
                # Chapter Report, Credentials, Premature Alumnus, Risk Management Form
                # Gear Article, Lock-in, Newsletter for Alumni, Initiation Report,
                # Member Updates
                create_submission = False
            if create_submission:
                submit_obj = Submission(
                    user=user,
                    file=file,
                    name=submit_name,
                    type=score_type,
                    chapter=chapter,
                )
                submit_obj.save(extra_info=extra_info)
            task_obj.submission_object = submit_obj
        task_obj.save()


class TaskDate(models.Model):
    class Meta:
        unique_together = ("task", "date", "school_type")
        ordering = [
            "date",
        ]

    TYPES = [
        ("semester", "Semester"),
        ("quarter", "Quarter"),
        ("all", "All"),
        ("na", "N/A"),
    ]
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="dates")
    school_type = models.CharField(max_length=10, choices=TYPES)
    date = models.DateField("Due Date")
    archived = models.BooleanField(
        "No Longer Needed",
        default=False,
        db_index=True,
        help_text="Archived (retired) dates are hidden from chapters and cannot be completed.",
    )
    archived_on = models.DateTimeField(blank=True, null=True)
    archived_reason = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.task.name} for {self.task.owner} due on {self.date}"

    def archive(self, reason=""):
        """Retire this due date so it is no longer surfaced or completable."""
        self.archived = True
        self.archived_on = timezone.now()
        if reason:
            self.archived_reason = reason
        self.save(update_fields=["archived", "archived_on", "archived_reason"])

    def unarchive(self):
        """Restore a previously retired due date."""
        self.archived = False
        self.archived_on = None
        self.archived_reason = ""
        self.save(update_fields=["archived", "archived_on", "archived_reason"])

    def complete(self, chapter):
        tasks = self.chapters.filter(chapter=chapter).all()
        return tasks

    @classmethod
    def incomplete_dates_for_chapter(cls, chapter):
        school_type = chapter.school_type
        min_date = TODAY_END - (timedelta(90))
        tasks = cls.objects.filter(
            Q(school_type=school_type) | Q(school_type="all"),
            ~Q(chapters__chapter=chapter),
            Q(date__gte=min_date),
            archived=False,
        ).all()
        return tasks

    @classmethod
    def incomplete_dates_for_chapter_next_month(cls, chapter):
        school_type = chapter.school_type
        tasks = cls.objects.filter(
            Q(school_type=school_type) | Q(school_type="all"),
            ~Q(chapters__chapter=chapter),
            Q(date__gte=TODAY_END),
            Q(date__lte=TODAY_END + timedelta(60)),
            archived=False,
        ).all()
        return tasks

    @classmethod
    def dates_for_next_month(cls):
        tasks = cls.objects.filter(
            Q(date__gte=TODAY_END),
            Q(date__lte=TODAY_END + timedelta(30)),
            archived=False,
        ).all()
        return tasks

    @classmethod
    def incomplete_dates_for_chapter_past(cls, chapter):
        school_type = chapter.school_type
        academic_start, _ = academic_encompass_start_end_date()
        tasks = cls.objects.filter(
            Q(school_type=school_type) | Q(school_type="all"),
            ~Q(chapters__chapter=chapter),
            Q(date__lte=TODAY_END),
            Q(date__gte=academic_start),
            archived=False,
        ).all()
        return tasks

    @classmethod
    def dates_for_chapter(cls, chapter, include_archived=False):
        school_type = chapter.school_type
        tasks = cls.objects.filter(Q(school_type=school_type) | Q(school_type="all"))
        if not include_archived:
            tasks = tasks.filter(archived=False)
        return tasks.all()


class TaskChapter(models.Model, EmailSignalMixin):
    class Meta:
        unique_together = ("task", "date", "chapter")
        """Dates increase as time advances, so 1293861600 (Jan. 1st 2011) is greater than 946706400 (Jan 1st. 2000).
        Thus, a descending ordering puts the most recent dates first."""
        ordering = ["chapter", "-date"]

    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="tasks_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="tasks_modified",
    )
    task = models.ForeignKey(TaskDate, on_delete=models.CASCADE, related_name="chapters")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="tasks")
    date = models.DateField("Task Completed Date", default=datetime.date.today)
    # This can only be used for a submission or form
    # Whatever results in the completion of the task
    submission_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, blank=True, null=True)
    submission_id = models.PositiveIntegerField(blank=True, null=True)
    submission_object = GenericForeignKey("submission_type", "submission_id")

    @classmethod
    def check_previous(cls, task, chapter, date=None):
        if date is None:
            date = datetime.datetime.today()
        return cls.objects.filter(
            task=task,
            chapter=chapter,
            date=date,
        ).exists()
