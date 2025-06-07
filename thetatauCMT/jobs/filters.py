# filters.py
import django_filters
from core.forms import ListSelect2Multiple
from .models import Job, JobSearch


class JobListFilter(django_filters.FilterSet):
    keywords = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=ListSelect2Multiple(
            url="jobs:keyword-autocomplete-ro",
        ),
    )
    contact = django_filters.ChoiceFilter(
        label="Contact Available",
        choices=(
            (True, "True"),
            (False, "False"),
        ),
    )
    majors_specific = django_filters.ChoiceFilter(
        choices=(
            (True, "True"),
            (False, "False"),
        ),
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "company",
            "contact",
            "education_qualification",
            "experience",
            "job_type",
            "majors_specific",
            "majors",
            "location_type",
            # "location",
            "country",
            "sponsored",
            "description",
            "keywords",
        ]
        order_by = ["priority", "-publish_start"]


class JobSearchListFilter(django_filters.FilterSet):
    class Meta:
        model = JobSearch
        fields = [
            "search_title",
        ]
