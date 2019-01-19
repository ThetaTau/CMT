from django.utils.timezone import now
from django_filters import DateRangeFilter

DateRangeFilter.options[6] = (
    'Last Year', lambda qs, name: qs.filter(**{
        '%s__year' % name: now().year - 1,
    }))

if now().month == 1:
    month = 12
    year = now().year - 1
else:
    month = now().month - 1
    year = now().year


DateRangeFilter.options[7] = (
    'Last month', lambda qs, name: qs.filter(**{
        '%s__year' % name: year,
        '%s__month' % name: month
    }))

if now().month == 12:
    month = 1
    year = now().year + 1
else:
    month = now().month
    year = now().year

DateRangeFilter.options[8] = (
    'Next month', lambda qs, name: qs.filter(**{
        '%s__year' % name: year,
        '%s__month' % name: month
    }))
