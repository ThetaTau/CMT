# filters.py
import django_filters
from django.forms.widgets import NumberInput
from .models import ScoreType
from chapters.filters import ChapterListFilter
from core.filters import BIENNIUM_FILTERS


class ScoreListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    start_year = django_filters.NumberFilter(
        min_value=1990,
        max_value=2050,
        max_digits=4,
        decimal_places=0,
        method="filter_start_year",
        widget=NumberInput(attrs={"placeholder": "Start Year"}),
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
    date = django_filters.ChoiceFilter(
        label="Complete", choices=list(BIENNIUM_FILTERS.keys())
    )

    class Meta:
        fields = {
            "region",
            "date",
        }
