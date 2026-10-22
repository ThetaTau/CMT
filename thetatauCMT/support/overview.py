"""The "My Chapters" table on the CSS landing page (CSSWI-8, Q12).

Each figure mirrors what the chapter's own pages show, in a fixed number of queries
however many chapters a CSS covers.
"""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.models import TODAY_END

# The same statuses as ``Chapter.actives()``.
ACTIVE_STATUSES = ["active", "activepend", "alumnipend", "pendexpul", "activeCC"]
EXECUTIVE_OFFICERS = [
    ("regent", "Regent"),
    ("scribe", "Scribe"),
    ("vice regent", "Vice Regent"),
    ("treasurer", "Treasurer"),
    ("corresponding secretary", "Corresponding Secretary"),
]


def chapter_overview(chapters, today=None):
    """One row per chapter: actives, PNMs, overdue tasks, balance and missing officers."""
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.tasks.models import TaskChapter, TaskDate
    from thetatauCMT.users.models import User

    today = today or timezone.localdate()
    chapters = list(
        Chapter.objects.filter(pk__in=[chapter.pk for chapter in chapters])
        .annotate(
            active_count=Count("members", filter=Q(members__current_status__in=ACTIVE_STATUSES), distinct=True),
            # As ``Chapter.pledges()``: a PNM status covering today.
            pnm_count=Count(
                "members",
                filter=Q(
                    members__status__status="pnm",
                    members__status__start__lte=TODAY_END,
                    members__status__end__gte=TODAY_END,
                ),
                distinct=True,
            ),
        )
        .order_by("name")
    )
    if not chapters:
        return []

    # As ``TaskDate.incomplete_dates_for_chapter()``, limited to dates already past.
    school_types = {chapter.school_type for chapter in chapters} | {"all"}
    task_dates = list(
        TaskDate.objects.filter(
            school_type__in=school_types, date__gte=TODAY_END - timedelta(90), date__lt=today, archived=False
        ).values_list("pk", "school_type")
    )
    done = set(
        TaskChapter.objects.filter(chapter__in=chapters, task_id__in=[pk for pk, _ in task_dates]).values_list(
            "chapter_id", "task_id"
        )
    )

    roles = [role for role, _ in EXECUTIVE_OFFICERS]
    filled = defaultdict(set)
    holders = User.objects.filter(chapter__in=chapters, current_roles__overlap=roles).values_list(
        "chapter_id", "current_roles"
    )
    for chapter_id, current_roles in holders:
        filled[chapter_id].update(current_roles or [])

    return [
        {
            "chapter": chapter,
            "actives": chapter.active_count,
            "pnms": chapter.pnm_count,
            "overdue": sum(
                1
                for pk, school_type in task_dates
                if school_type in (chapter.school_type, "all") and (chapter.pk, pk) not in done
            ),
            "missing": [title for role, title in EXECUTIVE_OFFICERS if role not in filled[chapter.pk]],
        }
        for chapter in chapters
    ]
