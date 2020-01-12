# filters.py
import django_filters
from .models import Chapter, Region


class ChapterListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region",
        choices=Region.region_choices(),
        method='filter_region'
    )

    class Meta:
        model = Chapter
        fields = {
            'name': ['icontains'],
            'region': ['exact'],
            'school': ['icontains'],
        }
        order_by = ['name']

    def filter_region(self, queryset, field_name, value):
        if value == 'national':
            return queryset
        elif value == 'colony':
            queryset = queryset.filter(colony=True)
        else:
            queryset = queryset.filter(region__slug=value)
        return queryset
