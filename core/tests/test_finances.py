"""Regression tests for core/finances.py."""

from unittest.mock import MagicMock, patch

from quickbooks.objects.base import CustomerMemo


def test_invoice_search_materializes_missing_customer_memo():
    """An existing QuickBooks invoice with ``CustomerMemo=None`` gets an empty
    memo so callers can read/write ``invoice.CustomerMemo.value`` safely.

    QuickBooks omits ``CustomerMemo`` on some invoices (it comes back ``None``),
    and ``sync_badge_shingle_invoice``/``sync_pledge_invoice`` then did
    ``invoice.CustomerMemo.value`` which raised
    ``AttributeError: 'NoneType' object has no attribute 'value'`` (issue #973).
    """
    from core import finances

    existing = MagicMock()
    existing.CustomerMemo = None
    existing.Line = [object(), object()]
    with patch.object(finances.Invoice, "query", return_value=[existing]):
        invoice, linenumber_count = finances.invoice_search("12345", MagicMock(Id="7"), client=MagicMock())

    assert invoice is existing
    assert isinstance(invoice.CustomerMemo, CustomerMemo)
    assert invoice.CustomerMemo.value == ""
    assert linenumber_count == 2


def test_invoice_search_preserves_existing_customer_memo():
    """A present ``CustomerMemo`` is left untouched."""
    from core import finances

    memo = CustomerMemo()
    memo.value = "existing memo"
    existing = MagicMock()
    existing.CustomerMemo = memo
    existing.Line = []
    with patch.object(finances.Invoice, "query", return_value=[existing]):
        invoice, _ = finances.invoice_search("555", MagicMock(Id="7"), client=MagicMock())

    assert invoice.CustomerMemo is memo
    assert invoice.CustomerMemo.value == "existing memo"
