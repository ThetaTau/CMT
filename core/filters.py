from django.utils.timezone import now
from django_filters import DateRangeFilter
from .models import BIENNIUM_DATES


DateRangeFilter.filters['year_last'] = lambda qs, name:\
    qs.filter(**{'%s__year' % name: now().year - 1, })
DateRangeFilter.choices.append(('year_last', 'Last Year'))


if now().month == 1:
    month = 12
    year = now().year - 1
else:
    month = now().month - 1
    year = now().year


DateRangeFilter.filters['month_last'] = lambda qs, name:\
    qs.filter(**{'%s__year' % name: year, '%s__month' % name: month})
DateRangeFilter.choices.append(('month_last', 'Last Month'))


if now().month == 12:
    month = 1
    year = now().year + 1
else:
    month = now().month
    year = now().year

DateRangeFilter.filters['month_next'] = lambda qs, name:\
    qs.filter(**{'%s__year' % name: year, '%s__month' % name: month})
DateRangeFilter.choices.append(('month_next', 'Next Month'))


def filter_qs_dates(start, end):
    # Lambdas do not like being in a loop, so move to separate function
    return lambda qs, name: qs.filter(**{
            '%s__gte' % name: start,
            '%s__lt' % name: end
        })


BIENNIUM_FILTERS = {}


for date_name, date_info in BIENNIUM_DATES.items():
    date_name_slug = date_name.replace(' ', '_')
    DateRangeFilter.filters[date_name_slug] = filter_qs_dates(
        date_info['start'].date(), date_info['end'].date())
    choice = (date_name_slug, date_name)
    DateRangeFilter.choices.append(choice)
    BIENNIUM_FILTERS[choice] = (date_info['start'].date(), date_info['end'].date())
