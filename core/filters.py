from django.utils.timezone import now
from django_filters import DateRangeFilter
from .models import BIENNIUM_DATES

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


def filter_qs_dates(start, end):
    # Lambdas do not like being in a loop, so move to separate function
    return lambda qs, name: qs.filter(**{
            '%s__gte' % name: start,
            '%s__lt' % name: end
        })


ind = 9
for date_name, date_info in BIENNIUM_DATES.items():
    DateRangeFilter.options[ind] = (
        date_name, filter_qs_dates(date_info['start'].date(),
                                   date_info['end'].date()))
    ind += 1
