import django_tables2 as tables
from .models import Training


class TrainingTable(tables.Table):
    class Meta:
        model = Training
        fields = (
            "user",
            "course_title",
            "completed",
            "completed_time",
            "max_quiz_score",
        )
        order_by = "-completed_time"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no trainings"
