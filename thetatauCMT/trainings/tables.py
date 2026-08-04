from core.tables import CMTTable

from .models import Training


class TrainingTable(CMTTable):
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
