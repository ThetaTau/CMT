import django_tables2 as tables
from django_tables2.utils import A
from .models import Job, JobSearch


class JobTable(tables.Table):
    title = tables.LinkColumn("jobs:detail", kwargs={"pk": A("pk"), "slug": A("slug")})

    class Meta:
        model = Job
        order_by = ["priority", "-publish_start"]
        fields = (
            "title",
            "company",
            "education_qualification",
            "experience",
            "job_type",
            "contact",
            "keywords",
            "location",
            "country",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no jobs matching the search criteria..."


class JobSearchTable(tables.Table):
    search_title = tables.LinkColumn("jobs:update", args=[A("pk")])

    class Meta:
        model = JobSearch
        order_by = ["-modified"]
        fields = (
            "search_title",
            # "search_description",
            "company",
            "education_qualification",
            "experience",
            "job_type",
            "location_type",
            "keywords",
            "location",
            "country",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no jobs matching the search criteria..."
