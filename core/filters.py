from django.utils.timezone import now
from django_filters import DateRangeFilter

from .models import BIENNIUM_DATES

DateRangeFilter.filters["year_last"] = lambda qs, name: qs.filter(
    **{
        "%s__year" % name: now().year - 1,
    }
)
DateRangeFilter.choices.append(("year_last", "Last Year"))


if now().month == 1:
    month = 12
    year = now().year - 1
else:
    month = now().month - 1
    year = now().year


DateRangeFilter.filters["month_last"] = lambda qs, name: qs.filter(
    **{"%s__year" % name: year, "%s__month" % name: month}
)
DateRangeFilter.choices.append(("month_last", "Last Month"))


if now().month == 12:
    month = 1
    year = now().year + 1
else:
    month = now().month
    year = now().year

DateRangeFilter.filters["month_next"] = lambda qs, name: qs.filter(
    **{"%s__year" % name: year, "%s__month" % name: month}
)
DateRangeFilter.choices.append(("month_next", "Next Month"))


def filter_qs_dates(start, end):
    # Lambdas do not like being in a loop, so move to separate function
    return lambda qs, name: qs.filter(**{"%s__gte" % name: start, "%s__lt" % name: end})


BIENNIUM_FILTERS = {}


for date_name, date_info in BIENNIUM_DATES.items():
    date_name_slug = date_name.replace(" ", "_")
    DateRangeFilter.filters[date_name_slug] = filter_qs_dates(date_info["start"].date(), date_info["end"].date())
    choice = (date_name_slug, date_name)
    DateRangeFilter.choices.append(choice)
    BIENNIUM_FILTERS[choice] = (date_info["start"].date(), date_info["end"].date())


class DynamicScopeFilterSetMixin:
    """Rebuild `chapter` and `region` filter choices on every FilterSet
    instantiation.

    `django_filters.ChoiceFilter(choices=Chapter.chapter_choices())` evaluates
    the choices at class-definition time (i.e. Django worker startup). Any
    chapter or region added later — through the admin, a management command
    like `seed_dashboard_data`, or a fixture load — is invisible in the filter
    UI until the worker restarts. This mixin re-queries the DB per request.

    Add as the first parent on any `FilterSet` that has a `chapter` or
    `region` ChoiceFilter. Safe when either filter is absent OR when the
    filter isn't a ChoiceFilter (e.g. an auto-generated `ModelChoiceFilter`
    from `Meta.fields = ["chapter"]`) — it silently skips those cases.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Local imports so the mixin doesn't force the chapters/regions apps
        # to be importable at core module load time.
        import django_filters

        from thetatauCMT.chapters.models import Chapter
        from thetatauCMT.regions.models import Region

        refreshers = (("chapter", Chapter.chapter_choices), ("region", Region.region_choices))
        for name, factory in refreshers:
            filt = self.filters.get(name)
            # Only touch pure ChoiceFilters. `ModelChoiceFilter` subclasses
            # `ChoiceFilter` in django-filter but its underlying form field
            # (`ModelChoiceField`) rejects a `choices=` kwarg — it takes
            # `queryset=` instead — so passing choices to it raises
            # `TypeError: Field.__init__() got an unexpected keyword
            # argument 'choices'` when the field is rebuilt.
            if (
                filt is None
                or not isinstance(filt, django_filters.ChoiceFilter)
                or isinstance(filt, django_filters.ModelChoiceFilter)
            ):
                continue
            filt.extra["choices"] = factory()
            # `django_filters.Filter.field` caches the built field. Drop the
            # cache so the next access rebuilds it with the refreshed
            # choices. django-filter has used both `_field` and the
            # `functools.cached_property` (stored in `__dict__["field"]`)
            # patterns across versions, so clear both.
            try:
                del filt._field
            except AttributeError:
                pass
            filt.__dict__.pop("field", None)
