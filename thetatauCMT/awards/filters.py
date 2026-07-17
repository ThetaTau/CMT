import django_filters
from django.db.models import Q

from core.filters import DynamicScopeFilterSetMixin
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

from .models import AwardCycle, AwardGrant, AwardType


class AwardGrantFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    """Public award-winner directory filters (AWI-11).

    Narrows the (already status-scoped) grant queryset by award type, level,
    cycle, chapter, and region, plus a free-text recipient search. Chapter and
    region match the grant's *associated* entity: a chapter matches grants to
    that chapter and to members of it; a region matches grants to that region,
    to chapters in it, and to members whose chapter is in it. ``chapter`` and
    ``region`` choices are refreshed per request by
    :class:`~core.filters.DynamicScopeFilterSetMixin`.
    """

    recipient = django_filters.CharFilter(label="Recipient", method="filter_recipient")
    award_type = django_filters.ModelChoiceFilter(label="Award", queryset=AwardType.objects.all())
    level = django_filters.ChoiceFilter(
        label="Level",
        field_name="award_type__level",
        choices=AwardType.Level.choices,
    )
    cycle = django_filters.ModelChoiceFilter(label="Award Period", queryset=AwardCycle.objects.all())
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )
    region = django_filters.ChoiceFilter(
        label="Region",
        choices=Region.region_choices(),
        method="filter_region",
    )

    class Meta:
        model = AwardGrant
        fields = []

    def filter_recipient(self, queryset, name, value):
        return queryset.filter(
            Q(recipient_member__name__icontains=value)
            | Q(recipient_chapter__name__icontains=value)
            | Q(recipient_region__name__icontains=value)
        )

    def filter_chapter(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(recipient_chapter__slug=value) | Q(recipient_member__chapter__slug=value)
        )

    def filter_region(self, queryset, name, value):
        # "national" is a cross-region pseudo-choice: don't narrow (mirrors the
        # events directory convention).
        if not value or value == "national":
            return queryset
        if value == "candidate_chapter":
            return queryset.filter(
                Q(recipient_chapter__candidate_chapter=True)
                | Q(recipient_member__chapter__candidate_chapter=True)
            )
        return queryset.filter(
            Q(recipient_region__slug=value)
            | Q(recipient_chapter__region__slug=value)
            | Q(recipient_member__chapter__region__slug=value)
        )
