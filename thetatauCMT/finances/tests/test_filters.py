"""
Tests for thetatauCMT/finances/filters.py.

Covers:
- InvoiceListFilter basic construction
- ChapterBalanceListFilter.filter_region with all three branches:
    - "national" → returns full queryset
    - "candidate_chapter" → filters candidate chapters
    - any other slug → filters by chapter__region__slug
"""

import pytest

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.models import Invoice
from thetatauCMT.finances.tests.factories import InvoiceFactory


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

    chapter_a = ChapterFactory()
    chapter_b = ChapterFactory()
    inv_a = InvoiceFactory(chapter=chapter_a)
    inv_b = InvoiceFactory(chapter=chapter_b)
    qs = Invoice.objects.filter(pk__in=[inv_a.pk, inv_b.pk])
    f = ChapterBalanceListFilter(data={"region": "national"}, queryset=qs)
    result = f.qs
    assert result.count() == 2


@pytest.mark.django_db
def test_chapter_balance_filter_candidate_chapter():
    """filter_region('candidate_chapter') keeps only candidate-chapter invoices."""
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    candidate_chapter = ChapterFactory(candidate_chapter=True)
    regular_chapter = ChapterFactory(candidate_chapter=False)
    inv_candidate = InvoiceFactory(chapter=candidate_chapter)
    inv_regular = InvoiceFactory(chapter=regular_chapter)
    qs = Invoice.objects.filter(pk__in=[inv_candidate.pk, inv_regular.pk])
    f = ChapterBalanceListFilter(data={"region": "candidate_chapter"}, queryset=qs)
    result = f.qs
    pks = list(result.values_list("pk", flat=True))
    assert inv_candidate.pk in pks
    assert inv_regular.pk not in pks


@pytest.mark.django_db
def test_chapter_balance_filter_region_slug():
    """filter_region(slug) filters invoices whose chapter is in that region.

    Calls filter_region directly because ChoiceFilter validates against choices
    that were evaluated at import time (before test-created regions exist).
    """
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    chapter = ChapterFactory()
    other_chapter = ChapterFactory()
    inv_in_region = InvoiceFactory(chapter=chapter)
    inv_other = InvoiceFactory(chapter=other_chapter)
    qs = Invoice.objects.filter(pk__in=[inv_in_region.pk, inv_other.pk])
    region_slug = chapter.region.slug
    # Call filter_region directly to hit the else-branch (line 36) since the
    # slug may not appear in ChoiceFilter.choices (evaluated at import time).
    f = ChapterBalanceListFilter(data={}, queryset=qs)
    result = f.filter_region(qs, "region", region_slug)
    pks = list(result.values_list("pk", flat=True))
    assert inv_in_region.pk in pks
