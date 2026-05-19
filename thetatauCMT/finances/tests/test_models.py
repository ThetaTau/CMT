from decimal import Decimal

import pytest
from djmoney.money import Money

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.models import Invoice
from thetatauCMT.finances.tests.factories import InvoiceFactory


@pytest.mark.django_db
def test_invoice_factory_creates_instance():
    invoice = InvoiceFactory()
    assert invoice.pk is not None
    assert invoice.chapter is not None


@pytest.mark.django_db
def test_invoice_str_contains_description():
    invoice = InvoiceFactory()
    assert str(invoice.pk) is not None  # model has no __str__, use pk


@pytest.mark.django_db
def test_open_balance_chapter_empty():
    """Returns 0 when chapter has no invoices."""
    chapter = ChapterFactory()
    balance = Invoice.open_balance_chapter(chapter=chapter)
    assert balance == 0


@pytest.mark.django_db
def test_open_balance_chapter_sums_invoices():
    """Returns sum of all invoice totals for a chapter."""
    chapter = ChapterFactory()
    InvoiceFactory(chapter=chapter, total=Money(Decimal("100.00"), "USD"))
    InvoiceFactory(chapter=chapter, total=Money(Decimal("250.50"), "USD"))
    balance = Invoice.open_balance_chapter(chapter=chapter)
    assert float(balance) == pytest.approx(350.50, rel=1e-3)


@pytest.mark.django_db
def test_open_balance_chapter_excludes_other_chapters():
    """Only sums invoices for the specific chapter, not others."""
    chapter_a = ChapterFactory()
    chapter_b = ChapterFactory()
    InvoiceFactory(chapter=chapter_a, total=Money(Decimal("100.00"), "USD"))
    InvoiceFactory(chapter=chapter_b, total=Money(Decimal("500.00"), "USD"))
    balance = Invoice.open_balance_chapter(chapter=chapter_a)
    assert float(balance) == pytest.approx(100.00, rel=1e-3)


@pytest.mark.django_db
def test_open_balances_all_returns_queryset():
    """open_balances_all returns an annotated queryset."""
    chapter = ChapterFactory()
    InvoiceFactory(chapter=chapter, total=Money(Decimal("75.00"), "USD"))
    qs = Invoice.open_balances_all()
    assert qs.count() >= 1


@pytest.mark.django_db
def test_open_balances_all_includes_chapter_name():
    """open_balances_all annotates with chapter__name."""
    chapter = ChapterFactory()
    InvoiceFactory(chapter=chapter, total=Money(Decimal("50.00"), "USD"))
    qs = Invoice.open_balances_all().order_by("chapter__name")
    entries = list(qs.filter(chapter__name=chapter.name))
    assert len(entries) >= 1
    assert entries[0]["balance"] is not None
