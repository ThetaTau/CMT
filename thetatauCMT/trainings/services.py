"""Per-chapter Vector/CommunityEdu (health & safety) completion percentages.

`Chapter.health_safety_surcharge` (see `thetatauCMT.chapters.models.Chapter.SURCHARGE`)
is assessed against the percentage of a chapter's prior-year new members
(`forms.Initiation` rows) who completed the required CommunityEdu training in
Vector. That percentage was previously computed and entered by hand; this
module calculates it from the `Training` rows the daily `sync_trainings`
management command already keeps up to date.
"""

import datetime
from dataclasses import dataclass

from django.utils import timezone

from .models import COMMUNITY_EDU_COURSE_ID, Training


@dataclass
class ChapterCompletionStats:
    chapter: object
    total: int
    completed: int

    @property
    def percentage(self):
        """Percent of `total` who completed the training, or `None` if `total` is 0."""
        if not self.total:
            return None
        return round(self.completed / self.total * 100, 1)

    @property
    def surcharge_bracket(self):
        """The `Chapter.SURCHARGE` choice value matching `percentage`, or `None`."""
        pct = self.percentage
        if pct is None:
            return None
        if pct > 75:
            return "none"
        if pct >= 51:
            return "L1a"
        if pct >= 26:
            return "L1b"
        return "L1c"


def default_window(today=None):
    """(start, end) date range for the trailing 12 months, ending today."""
    end = today or timezone.now().date()
    start = end - datetime.timedelta(days=365)
    return start, end


def chapter_completion_stats(start_date=None, end_date=None, chapters=None):
    """`ChapterCompletionStats` for every chapter in `chapters` (default: active chapters).

    A chapter's "new members" are the `forms.Initiation` rows recording that
    chapter with a date within `[start_date, end_date]` (default: the trailing
    12 months). "Completed" counts those new members with a completed
    `Training` row for the CommunityEdu course.
    """
    # Imported here (rather than at module scope) to avoid a hard import-time
    # dependency between the trainings and chapters/forms apps.
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.forms.models import Initiation

    if start_date is None or end_date is None:
        default_start, default_end = default_window()
        start_date = start_date or default_start
        end_date = end_date or default_end
    if chapters is None:
        chapters = Chapter.objects.filter(active=True).order_by("name")

    completed_user_ids = set(
        Training.objects.filter(
            course_id=COMMUNITY_EDU_COURSE_ID,
            completed=True,
        ).values_list("user_id", flat=True)
    )

    stats = []
    for chapter in chapters:
        new_member_user_ids = Initiation.objects.filter(
            chapter=chapter,
            date__gte=start_date,
            date__lte=end_date,
        ).values_list("user_id", flat=True)
        new_member_user_ids = list(new_member_user_ids)
        total = len(new_member_user_ids)
        completed = sum(1 for user_id in new_member_user_ids if user_id in completed_user_ids)
        stats.append(ChapterCompletionStats(chapter=chapter, total=total, completed=completed))
    return stats
