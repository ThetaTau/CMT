# filters.py
from functools import reduce
from operator import or_

import django_filters
from django.db.models import Q
from watson import search as watson

from .models import Job, JobSearch


def get_filter_expression(name, value):
    return reduce(
        or_,
        (Q(**{f"{name}__icontains": v}) for v in value),
        Q(),
    )


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
        method="filter_expression",
    )
    experience = django_filters.MultipleChoiceFilter(
        choices=sorted([x.value for x in Job.EXPERIENCE], key=lambda x: x[1]),
        method="filter_expression",
    )
    job_type = django_filters.MultipleChoiceFilter(
        choices=sorted([x.value for x in Job.JOB_TYPE], key=lambda x: x[1]),
        method="filter_expression",
    )
    location_type = django_filters.MultipleChoiceFilter(
        choices=sorted([x.value for x in Job.LOCATION_TYPE], key=lambda x: x[1]),
        method="filter_expression",
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
        return watson.filter(queryset, value, ranking=True)

    def filter_expression(self, queryset, name, value):
        return queryset.filter(get_filter_expression(name, value))


class JobSearchListFilter(django_filters.FilterSet):
    class Meta:
        model = JobSearch
        fields = [
            "search_title",
        ]
