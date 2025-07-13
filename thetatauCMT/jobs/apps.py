from django.apps import AppConfig
from watson import search as watson
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Job


class JobsConfig(AppConfig):
    name = "jobs"
    verbose_name = "Jobs"

    def ready(self):
        """Override this to put in:
        Users system checks
        Users signal registration
        """
        model: Job = self.get_model("Job")
        # When this is updated need to run: python manage.py buildwatson
        watson.register(
            model.get_live_jobs(),
            fields=[
                "title",
                "company",
                "description",
                "keywords",
            ],
        )
