# filters.py
import django_filters
from watson import search as watson
from .models import Job, JobSearch


class JobListFilter(django_filters.FilterSet):
    text_search = django_filters.CharFilter(
        method="text_search_filter", label="Free Text Search"
    )

    contact = django_filters.ChoiceFilter(
        label="Contact Available",
        choices=(
            (True, "Contact Available"),
            (False, "No Contact Available"),
        ),
    )
    education_qualification = django_filters.MultipleChoiceFilter(
        choices=sorted(
            [x.value for x in Job.EDUCATION_QUALIFICATION], key=lambda x: x[1]
        ),
        method="filter_education_qualification",
    )
    experience = django_filters.MultipleChoiceFilter(
        choices=sorted([x.value for x in Job.EXPERIENCE], key=lambda x: x[1]),
    )

    class Meta:
        model = Job
        fields = [
            "text_search",
            "contact",
            "education_qualification",
            "experience",
            "job_type",
            "location_type",
        ]
        order_by = ["priority", "-publish_start"]

    def text_search_filter(self, queryset, name, value):
        """Performs a full text search on the Job model"""
        return watson.filter(queryset, value, ranking=False)

    def filter_education_qualification(self, queryset, name, value):
        return queryset.filter(education_qualification__overlap=value)


class JobSearchListFilter(django_filters.FilterSet):
    class Meta:
        model = JobSearch
        fields = [
            "search_title",
        ]
