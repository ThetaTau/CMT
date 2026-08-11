"""Chapter activity feed.

Collects records across all apps that represent something a chapter's members
did — forms submitted, events held, tasks completed, submissions filed,
ballots voted, and trainings finished — and yields a unified, chronologically
sortable stream of activity items for a single chapter within a date window.

Notes / sources deliberately excluded (per feature spec): notes, invoices, scores.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, List, Optional

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

CATEGORY_FORM = "Form"
CATEGORY_EVENT = "Event"
CATEGORY_TASK = "Task"
CATEGORY_SUBMISSION = "Submission"
CATEGORY_BALLOT = "Ballot"
CATEGORY_TRAINING = "Training"

CATEGORIES = (
    CATEGORY_FORM,
    CATEGORY_EVENT,
    CATEGORY_TASK,
    CATEGORY_SUBMISSION,
    CATEGORY_BALLOT,
    CATEGORY_TRAINING,
)


@dataclass(frozen=True)
class ActivityItem:
    when: datetime  # tz-aware datetime used for sorting
    display_date: date  # what the UI shows in the "when" column
    category: str  # one of CATEGORIES
    label: str  # sub-type, e.g. "Chapter Report", "Meeting"
    title: str  # short human description
    actor: str  # user who did it (name), or "" if not attributable
    url: str  # link out to detail / list page


def _make_aware(value):
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, date):
        return timezone.make_aware(
            datetime.combine(value, time.min),
            timezone.get_current_timezone(),
        )
    return timezone.now()


def _safe_reverse(name: str, **kwargs) -> Optional[str]:
    try:
        return reverse(name, kwargs=kwargs) if kwargs else reverse(name)
    except NoReverseMatch:
        return None


def _actor(user) -> str:
    if user is None:
        return ""
    return getattr(user, "name", None) or getattr(user, "username", "") or ""


def _event_url(event) -> str:
    url = _safe_reverse(
        "events:detail",
        year=event.date.year,
        month=event.date.strftime("%m"),
        day=event.date.strftime("%d"),
        slug=event.slug,
    )
    return url or reverse("events:list")


def _submission_url(sub) -> str:
    url = _safe_reverse(
        "submissions:detail",
        year=sub.date.year,
        month=sub.date.strftime("%m"),
        day=sub.date.strftime("%d"),
        slug=sub.slug,
    )
    return url or reverse("submissions:list")


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _collect_events(chapter, start_date, end_date) -> Iterable[ActivityItem]:
    from thetatauCMT.events.models import Event

    qs = Event.objects.filter(chapter=chapter, date__range=(start_date, end_date)).select_related("type", "created_by")
    for e in qs:
        yield ActivityItem(
            when=_make_aware(e.date),
            display_date=e.date,
            category=CATEGORY_EVENT,
            label=str(e.type) if e.type_id else "Event",
            title=e.name,
            actor=_actor(e.created_by),
            url=_event_url(e),
        )


def _collect_submissions(chapter, start_date, end_date) -> Iterable[ActivityItem]:
    from thetatauCMT.submissions.models import Submission

    qs = Submission.objects.filter(chapter=chapter, date__range=(start_date, end_date)).select_related("type", "user")
    for s in qs:
        yield ActivityItem(
            when=_make_aware(s.date),
            display_date=s.date,
            category=CATEGORY_SUBMISSION,
            label=str(s.type) if s.type_id else "Submission",
            title=s.name,
            actor=_actor(s.user),
            url=_submission_url(s),
        )


def _collect_tasks(chapter, start_date, end_date) -> Iterable[ActivityItem]:
    from thetatauCMT.tasks.models import TaskChapter

    qs = TaskChapter.objects.filter(chapter=chapter, date__range=(start_date, end_date)).select_related(
        "task__task", "created_by"
    )
    for tc in qs:
        task_date = tc.task
        task = task_date.task if task_date else None
        title = task.name if task else "Task"
        url = _safe_reverse("tasks:detail", pk=task.pk) if task else None
        yield ActivityItem(
            when=_make_aware(tc.date),
            display_date=tc.date,
            category=CATEGORY_TASK,
            label="Task Completed",
            title=title,
            actor=_actor(tc.created_by),
            url=url or reverse("tasks:list"),
        )


def _collect_ballots(chapter, start_dt, end_dt) -> Iterable[ActivityItem]:
    from thetatauCMT.ballots.models import BallotComplete

    qs = BallotComplete.objects.filter(user__chapter=chapter, created__range=(start_dt, end_dt)).select_related(
        "user", "ballot"
    )
    for bc in qs:
        ballot = bc.ballot
        url = None
        if ballot is not None:
            url = _safe_reverse("ballots:detail", slug=ballot.slug)
        yield ActivityItem(
            when=_make_aware(bc.created),
            display_date=bc.created.date(),
            category=CATEGORY_BALLOT,
            # Never the motion: only the Grand Regent and Grand Scribe see votes.
            label="Ballot returned",
            title=ballot.name if ballot else "Ballot",
            actor=_actor(bc.user),
            url=url or reverse("ballots:votelist"),
        )


def _collect_trainings(chapter, start_dt, end_dt) -> Iterable[ActivityItem]:
    from thetatauCMT.trainings.models import Training

    qs = Training.objects.filter(
        user__chapter=chapter,
        completed=True,
        completed_time__range=(start_dt, end_dt),
    ).select_related("user")
    for t in qs:
        when = t.completed_time
        yield ActivityItem(
            when=_make_aware(when),
            display_date=when.date(),
            category=CATEGORY_TRAINING,
            label="Training Completed",
            title=t.course_title,
            actor=_actor(t.user),
            url=reverse("trainings:list"),
        )


# ---- Forms: (model_path, chapter_filter, date_field, label, url_fn, actor_fn) ----
#
# url_fn(obj) may return None to fall back to forms:landing.
# actor_fn(obj) returns the user name attributed to the action.
def _form_sources() -> List[tuple]:
    from thetatauCMT.forms.models import (
        OSM,
        AlumniExclusion,
        Audit,
        Bylaws,
        ChapterReport,
        CollectionReferral,
        Convention,
        Depledge,
        DisciplinaryProcess,
        HSEducation,
        Initiation,
        Pledge,
        PledgeProgram,
        PrematureAlumnus,
        ResignationProcess,
        ReturnStudent,
        RiskManagement,
        RitualProficiency,
        StatusChange,
    )

    return [
        (Initiation, {"chapter": None}, "date", "Initiation", lambda o: None, lambda o: _actor(o.user)),
        (Depledge, {"user__chapter": None}, "date", "Depledge", lambda o: None, lambda o: _actor(o.user)),
        (
            StatusChange,
            {"user__chapter": None},
            "date_start",
            "Status Change",
            lambda o: None,
            lambda o: _actor(o.user),
        ),
        (ChapterReport, {"chapter": None}, "created", "Chapter Report", lambda o: None, lambda o: _actor(o.user)),
        (
            HSEducation,
            {"chapter": None},
            "program_date",
            "Health & Safety Education",
            lambda o: _safe_reverse("forms:education_list"),
            lambda o: _actor(o.created_by),
        ),
        (
            RiskManagement,
            {"user__chapter": None},
            "date",
            "Risk Management Form",
            lambda o: _safe_reverse("forms:rmp_complete", pk=o.pk),
            lambda o: _actor(o.user),
        ),
        (
            Audit,
            {"user__chapter": None},
            "modified",
            "Audit",
            lambda o: _safe_reverse("forms:audit_complete", pk=o.pk),
            lambda o: _actor(o.user),
        ),
        (Pledge, {"user__chapter": None}, "created", "Pledge Form", lambda o: None, lambda o: _actor(o.user)),
        (
            PledgeProgram,
            {"chapter": None},
            "created",
            "Pledge Program",
            lambda o: _safe_reverse("forms:pledge_program_list"),
            lambda o: "",
        ),
        (
            Convention,
            {"chapter": None},
            "meeting_date",
            "Convention",
            lambda o: _safe_reverse("forms:convention_list"),
            lambda o: _actor(getattr(o, "delegate", None)),
        ),
        (
            OSM,
            {"chapter": None},
            "meeting_date",
            "OSM Nomination",
            lambda o: _safe_reverse("forms:osm_list"),
            lambda o: _actor(getattr(o, "nominate", None)),
        ),
        (
            DisciplinaryProcess,
            {"chapter": None},
            "created",
            "Disciplinary Process",
            lambda o: None,
            lambda o: _actor(o.user),
        ),
        (
            CollectionReferral,
            {"user__chapter": None},
            "created",
            "Collection Referral",
            lambda o: None,
            lambda o: _actor(o.user),
        ),
        (
            Bylaws,
            {"chapter": None},
            "created",
            "Bylaws Update",
            lambda o: _safe_reverse("forms:bylaws_list"),
            lambda o: "",
        ),
        (
            AlumniExclusion,
            {"chapter": None},
            "meeting_date",
            "Alumni Exclusion",
            lambda o: _safe_reverse("forms:alumniexclusion_detail", pk=o.pk),
            lambda o: _actor(getattr(o, "created_by", None)),
        ),
        (
            RitualProficiency,
            {"user__chapter": None},
            "date",
            "Ritual Proficiency",
            lambda o: _safe_reverse("forms:ritual_proficiency_user_table"),
            lambda o: _actor(o.user),
        ),
        (
            ResignationProcess,
            {"chapter": None},
            "created",
            "Resignation",
            lambda o: _safe_reverse("forms:resign_list"),
            lambda o: _actor(o.user),
        ),
        (
            PrematureAlumnus,
            {"user__chapter": None},
            "created",
            "Premature Alumnus",
            lambda o: None,
            lambda o: _actor(o.user),
        ),
        (
            ReturnStudent,
            {"user__chapter": None},
            "created",
            "Return to Student Status",
            lambda o: None,
            lambda o: _actor(o.user),
        ),
    ]


def _collect_forms(chapter, start_dt, end_dt) -> Iterable[ActivityItem]:
    start_date = start_dt.date() if isinstance(start_dt, datetime) else start_dt
    end_date = end_dt.date() if isinstance(end_dt, datetime) else end_dt
    landing_url = reverse("forms:landing")

    for model, chapter_filter, date_field, label, url_fn, actor_fn in _form_sources():
        filter_kwargs = {}
        for key in chapter_filter:
            filter_kwargs[key] = chapter
        try:
            field = model._meta.get_field(date_field)
        except Exception:
            continue
        internal = field.get_internal_type()
        if internal == "DateField":
            filter_kwargs[f"{date_field}__range"] = (start_date, end_date)
        else:
            filter_kwargs[f"{date_field}__range"] = (start_dt, end_dt)
        try:
            qs = model.objects.filter(**filter_kwargs)
        except Exception:
            continue
        for obj in qs:
            value = getattr(obj, date_field)
            if value is None:
                continue
            url: Optional[str]
            try:
                url = url_fn(obj)
            except Exception:
                url = None
            try:
                actor = actor_fn(obj)
            except Exception:
                actor = ""
            yield ActivityItem(
                when=_make_aware(value),
                display_date=_to_date(value),
                category=CATEGORY_FORM,
                label=label,
                title=str(obj),
                actor=actor,
                url=url or landing_url,
            )


def iter_chapter_activity(chapter, start_dt, end_dt) -> List[ActivityItem]:
    """Collect all activity for `chapter` between `start_dt` and `end_dt`.

    `start_dt` / `end_dt` may be `datetime` or `date`; naive datetimes are
    made timezone-aware in the current timezone. Returns a list sorted by
    `when` descending (newest first).
    """
    start_dt = _make_aware(start_dt)
    end_dt = _make_aware(end_dt)
    start_date = start_dt.date()
    end_date = end_dt.date()

    items: List[ActivityItem] = []
    items.extend(_collect_events(chapter, start_date, end_date))
    items.extend(_collect_submissions(chapter, start_date, end_date))
    items.extend(_collect_tasks(chapter, start_date, end_date))
    items.extend(_collect_ballots(chapter, start_dt, end_dt))
    items.extend(_collect_trainings(chapter, start_dt, end_dt))
    items.extend(_collect_forms(chapter, start_dt, end_dt))
    items.sort(key=lambda x: x.when, reverse=True)
    return items
