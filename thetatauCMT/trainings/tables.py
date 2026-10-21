import django_tables2 as tables

from core.models import semester_label
from core.tables import CMTTable
from thetatauCMT.users.models import UserStatusChange

from .models import Training


class TrainingTable(CMTTable):
    current_status = tables.Column(accessor="user__current_status", verbose_name="Current status")
    # ``pledge_date`` is annotated onto the queryset by ``TrainingListView``.
    pledge_semester = tables.Column(accessor="pledge_date", verbose_name="Semester pledged")

    class Meta:
        model = Training
        fields = (
            "user",
            "current_status",
            "pledge_semester",
            "course_title",
            "completed",
            "completed_time",
            "max_quiz_score",
        )
        order_by = "-completed_time"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no trainings"

    def render_current_status(self, value):
        return UserStatusChange.STATUS.get_value(value)

    def render_pledge_semester(self, value):
        return semester_label(value)
