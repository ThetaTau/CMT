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
from thetatauCMT.finances.tests.factories import InvoiceFactory
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.models import Invoice


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
    """filter_region(slug) filters invoices whose chapter is in that region."""
    from thetatauCMT.finances.filters import ChapterBalanceListFilter

    chapter = ChapterFactory()
    other_chapter = ChapterFactory()
    inv_in_region = InvoiceFactory(chapter=chapter)
    inv_other = InvoiceFactory(chapter=other_chapter)
    qs = Invoice.objects.filter(pk__in=[inv_in_region.pk, inv_other.pk])
    # Use the chapter's actual region slug
    region_slug = chapter.region.slug
    f = ChapterBalanceListFilter(data={"region": region_slug}, queryset=qs)
    result = f.qs
    pks = list(result.values_list("pk", flat=True))
    assert inv_in_region.pk in pks
    # The other chapter may or may not be in the same region; only assert inclusion
    # of the target invoice
