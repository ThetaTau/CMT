# filters.py
import django_filters
from django.forms.widgets import NumberInput

from thetatauCMT.chapters.filters import ChapterListFilter

from .models import ScoreType


class ScoreListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    start_year = django_filters.NumberFilter(
        min_value=1990,
        max_value=2050,
        max_digits=4,
        decimal_places=0,
        method="filter_start_year",
        widget=NumberInput(attrs={"placeholder": "Start Year"}),
        label="",
    )

    class Meta:
        model = ScoreType
        fields = [
            "name",
            "section",
            "type",
            "start_year",
        ]
        order_by = ["name"]

    def filter_start_year(self, queryset, *args, **kwargs):
        return queryset


class ChapterScoreListFilter(ChapterListFilter):
    year = django_filters.NumberFilter(
        min_value=1990,
        max_value=2050,
        max_digits=4,
        decimal_places=0,
        widget=NumberInput(attrs={"placeholder": "Year"}),
        method="filter_pass",
        label="",
    )
    term = django_filters.ChoiceFilter(
        choices=(("fa", "Fall"), ("sp", "Spring")),
        method="filter_pass",
    )
    score_min = django_filters.NumberFilter(
        min_value=0,
        widget=NumberInput(attrs={"placeholder": "Min Total Score"}),
        method="filter_pass",
        label="",
    )
    score_max = django_filters.NumberFilter(
        min_value=0,
        widget=NumberInput(attrs={"placeholder": "Max Total Score"}),
        method="filter_pass",
        label="",
    )

    class Meta:
        fields = {
            "region",
            "year",
            "term",
            "score_min",
            "score_max",
        }

    def filter_pass(self, queryset, *args, **kwargs):
        return queryset
