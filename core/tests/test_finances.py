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


def test_invoice_search_sentinel_accepts_int():
    """``999999999`` passed as an int still reuses the open unsent invoice.

    The sync views get ``invoice_number`` from a ``<int:invoice_number>`` URL
    converter, so it arrives as an int. The sentinel comparisons were against
    strings, so the "reuse the existing NeedToSend invoice" branch never ran and
    QuickBooks got a brand new invoice for every process.
    """
    from core import finances

    existing = MagicMock()
    existing.EmailStatus = "NeedToSend"
    existing.CustomerMemo = None
    existing.Line = [object()]
    with patch.object(finances.Invoice, "query", return_value=[existing]) as query:
        invoice, _ = finances.invoice_search(999999999, MagicMock(Id="7"), client=MagicMock())

    assert invoice is existing
    assert "balance > '0'" in query.call_args.kwargs["select"]


def test_invoice_search_force_new_accepts_int():
    """``1`` passed as an int forces a new invoice instead of a DocNumber query."""
    from core import finances

    with patch.object(finances.Invoice, "query") as query, patch.object(finances, "Term") as term:
        term.filter.return_value = [MagicMock()]
        invoice, linenumber_count = finances.invoice_search(1, MagicMock(Id="7"), client=MagicMock())

    query.assert_not_called()
    assert invoice.Id is None
    assert linenumber_count == 1
