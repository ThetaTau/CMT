# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Submission, GearArticle
from chapters.models import Chapter
from regions.models import Region
from scores.models import ScoreType


class SubmissionListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    date = DateRangeFilter(field_name="date")
    type = django_filters.ModelChoiceFilter(
        queryset=ScoreType.objects.filter(type="Sub").all()
    )

    class Meta:
        model = Submission
        fields = [
            "name",
            "date",
            "type",
        ]
        order_by = ["date"]


class GearArticleListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )
    chapter = django_filters.ChoiceFilter(
        label="Chapter", choices=Chapter.chapter_choices(), method="filter_chapter"
    )
    date = DateRangeFilter(label="Submit Date")

    class Meta:
        fields = ["region", "chapter", "reviewed", "date"]
        model = GearArticle
        order_by = ["-date"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(candidate_chapter=True)
        else:
            queryset = queryset.filter(region_slug=value)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(chapter_slug=value)
        return queryset
