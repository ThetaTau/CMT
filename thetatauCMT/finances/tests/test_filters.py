"""
Tests for thetatauCMT/finances/filters.py.

Covers:
- InvoiceListFilter basic construction
- ChapterBalanceListFilter.filter_region with all three branches:
    - "national" → returns full queryset
    - "candidate_chapter" → filters candidate chapters
    - any other slug → filters by region__slug
"""

import pytest

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.models import Invoice
from thetatauCMT.regions.tests.factories import RegionFactory


@pytest.mark.django_db
def test_invoice_list_filter_instantiates():
    """InvoiceListFilter can be instantiated with an empty QuerySet."""
    from thetatauCMT.finances.filters import InvoiceListFilter

    f = InvoiceListFilter(data={}, queryset=Invoice.objects.none())
    assert f is not None


@pytest.mark.django_db
def test_chapter_balance_filter_national_returns_all():
    """filter_region('national') returns the full queryset unchanged."""
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    chapter_a = ChapterFactory(name="alpha")
    chapter_b = ChapterFactory(name="beta")
    qs = Chapter.objects.filter(pk__in=[chapter_a.pk, chapter_b.pk])
    f = ChapterBalanceListFilter(data={"region": "national"}, queryset=qs)
    result = f.qs
    assert result.count() == 2


@pytest.mark.django_db
def test_chapter_balance_filter_candidate_chapter():
    """filter_region('candidate_chapter') keeps only candidate chapters."""
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    candidate_chapter = ChapterFactory(name="delta", candidate_chapter=True)
    regular_chapter = ChapterFactory(name="epsilon", candidate_chapter=False)
    qs = Chapter.objects.filter(pk__in=[candidate_chapter.pk, regular_chapter.pk])
    f = ChapterBalanceListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    result = f.qs
    pks = list(result.values_list("pk", flat=True))
    assert candidate_chapter.pk in pks
    assert regular_chapter.pk not in pks


@pytest.mark.django_db
def test_chapter_balance_filter_region_slug():
    """filter_region(slug) filters chapters in that region.

    Calls filter_region directly because ChoiceFilter validates against choices
    that were evaluated at import time (before test-created regions exist).
    """
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    region_a = RegionFactory(name="Region A Test")
    region_b = RegionFactory(name="Region B Test")
    chapter = ChapterFactory(name="eta", region=region_a)
    other_chapter = ChapterFactory(name="kappa", region=region_b)
    qs = Chapter.objects.filter(pk__in=[chapter.pk, other_chapter.pk])
    region_slug = chapter.region.slug
    # Call filter_region directly to hit the else-branch since the slug may not
    # appear in ChoiceFilter.choices (evaluated at import time).
    f = ChapterBalanceListFilter(data={}, queryset=qs)
    result = f.filter_region(qs, "region", region_slug)
    pks = list(result.values_list("pk", flat=True))
    assert chapter.pk in pks
    assert other_chapter.pk not in pks
