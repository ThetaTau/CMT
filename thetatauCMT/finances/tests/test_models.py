import datetime
from decimal import Decimal

import pytest
from django.utils import timezone
from djmoney.money import Money

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.finances.models import Invoice, chapter_balance_overview
from thetatauCMT.finances.tests.factories import InvoiceFactory
from thetatauCMT.forms.tests.factories import AuditFactory
from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory


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
    chapter_a = ChapterFactory(name="alpha")
    chapter_b = ChapterFactory(name="beta")
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


# ─── chapter_balance_overview ────────────────────────────────────────────────


@pytest.mark.django_db
def test_chapter_balance_overview_excludes_inactive_chapters():
    """Only active chapters appear in the overview."""
    active = ChapterFactory(name="alpha", active=True)
    inactive = ChapterFactory(name="beta", active=False)
    pks = list(chapter_balance_overview().values_list("pk", flat=True))
    assert active.pk in pks
    assert inactive.pk not in pks


@pytest.mark.django_db
def test_chapter_balance_overview_membership_counts_match_helpers():
    """actives_count / pnm_count match Chapter.actives() / Chapter.pledges()."""
    chapter = ChapterFactory(name="delta")
    UserFactory(chapter=chapter, current_status="active")
    pnm = UserFactory(chapter=chapter, current_status="pnm")
    UserStatusChangeFactory(user=pnm, status="pnm", current=True)

    row = chapter_balance_overview().get(pk=chapter.pk)
    assert row.actives_count == chapter.actives().count()
    assert row.pnm_count == chapter.pledges().count()
    assert row.actives_count >= 1
    assert row.pnm_count >= 1


@pytest.mark.django_db
def test_chapter_balance_overview_open_balance_sums_invoices():
    """open_balance sums the chapter's invoice totals."""
    chapter = ChapterFactory(name="epsilon")
    InvoiceFactory(chapter=chapter, total=Money(Decimal("100.00"), "USD"))
    InvoiceFactory(chapter=chapter, total=Money(Decimal("50.50"), "USD"))
    row = chapter_balance_overview().get(pk=chapter.pk)
    assert float(row.open_balance) == pytest.approx(150.50, rel=1e-3)


@pytest.mark.django_db
def test_chapter_balance_overview_open_balance_zero_without_invoices():
    """open_balance is 0 (not None) when a chapter has no invoices."""
    chapter = ChapterFactory(name="eta")
    row = chapter_balance_overview().get(pk=chapter.pk)
    assert float(row.open_balance) == 0


@pytest.mark.django_db
def test_chapter_balance_overview_audit_fields_none_without_audit():
    """Audit annotations are None when a chapter has never filed an audit."""
    chapter = ChapterFactory(name="kappa")
    row = chapter_balance_overview().get(pk=chapter.pk)
    assert row.audit_dues_member is None
    assert row.audit_dues_pledge is None
    assert row.audit_year is None


@pytest.mark.django_db
def test_chapter_balance_overview_uses_latest_audit():
    """Dues come from the most recently reported audit, across officers."""
    from thetatauCMT.forms.models import Audit

    chapter = ChapterFactory(name="gamma beta")
    officer_old = UserFactory(chapter=chapter)
    officer_new = UserFactory(chapter=chapter)
    old_audit = AuditFactory(user=officer_old, dues_member=100.0, dues_pledge=25.0)
    new_audit = AuditFactory(user=officer_new, dues_member=200.0, dues_pledge=40.0)
    # `created` is an auto field; pin submission order deterministically.
    Audit.objects.filter(pk=old_audit.pk).update(created=timezone.now() - datetime.timedelta(days=10))
    Audit.objects.filter(pk=new_audit.pk).update(created=timezone.now())

    row = chapter_balance_overview().get(pk=chapter.pk)
    assert row.audit_dues_member == pytest.approx(200.0)
    assert row.audit_dues_pledge == pytest.approx(40.0)
