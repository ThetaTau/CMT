# filters.py
import django_filters
from .models import ScoreType
from chapters.filters import ChapterListFilter
from core.filters import BIENNIUM_FILTERS


class ScoreListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ScoreType
        fields = [
            "name",
            "section",
            "type",
        ]
        order_by = ["name"]


class ChapterScoreListFilter(ChapterListFilter):
    date = django_filters.ChoiceFilter(
        label="Complete", choices=list(BIENNIUM_FILTERS.keys())
    )

    class Meta:
        fields = {
            "region",
            "date",
        }
