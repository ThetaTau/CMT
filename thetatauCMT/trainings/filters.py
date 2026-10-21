import django_filters

from core.filters import DateRangeFilter
from core.models import SEMESTER, semester_encompass_start_end_date, semester_label
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import UserStatusChange

from .models import Training


class TrainingListFilter(django_filters.FilterSet):
    # Candidate chapter statuses (e.g. "activeCC") share their base status's label.
    current_status = django_filters.ChoiceFilter(
        label="Current status",
        choices=[status.value for status in UserStatusChange.STATUS if not status.name.endswith("CC")],
        method="filter_current_status",
        empty_label="All statuses",
    )
    # Choices are set per instance; needs the ``pledge_date`` annotation from ``TrainingListView``.
    pledge_semester = django_filters.ChoiceFilter(
        label="Semester pledged",
        method="filter_pledge_semester",
        empty_label="Any semester pledged",
    )
    completed_time = DateRangeFilter(field_name="completed_time")

    class Meta:
        model = Training
        fields = [
            "current_status",
            "pledge_semester",
            "course_title",
            "completed",
            "completed_time",
        ]
        order_by = ["-completed_time"]

    def __init__(self, *args, **kwargs):
        natoff = kwargs.get("natoff", False)
        if natoff:
            kwargs.pop("natoff")
            self.base_filters["region"] = django_filters.ChoiceFilter(
                choices=Region.region_choices(), method="filter_region"
            )
            self.base_filters["chapter"] = django_filters.ChoiceFilter(
                label="Chapter",
                choices=Chapter.chapter_choices(),
                method="filter_chapter",
            )
        super().__init__(*args, **kwargs)
        pledge_dates = self.queryset.order_by().values_list("pledge_date", flat=True).distinct()
        starts = sorted({semester_encompass_start_end_date(day)[0] for day in pledge_dates if day}, reverse=True)
        self.filters["pledge_semester"].extra["choices"] = [
            (f"{SEMESTER[start.month]}-{start.year}", semester_label(start)) for start in starts
        ]

    def filter_current_status(self, queryset, field_name, value):
        return queryset.filter(user__current_status__in=[value, f"{value}CC"])

    def filter_pledge_semester(self, queryset, field_name, value):
        term, year = value.split("-")
        start, end = semester_encompass_start_end_date(term=term, year=int(year))
        return queryset.filter(pledge_date__gte=start.date(), pledge_date__lt=end.date())

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(user__chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(user__chapter__region__slug=value)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(user__chapter__slug=value)
        return queryset
