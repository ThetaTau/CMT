# filters.py
import django_filters
from .models import Chapter


class ChapterListFilter(django_filters.FilterSet):
    class Meta:
        model = Chapter
        fields = {
            'name': ['icontains'],
            'region': ['exact'],
            'school': ['icontains'],
        }
        order_by = ['name']
