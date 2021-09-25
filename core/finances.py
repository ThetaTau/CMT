import os
import environ
import datetime
from django.conf import settings
from quickbooks import QuickBooks
from intuitlib.client import AuthClient
from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail
from quickbooks.objects.base import CustomerMemo
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.item import Item
from quickbooks.objects.term import Term


def get_quickbooks_client():
    env = environ.Env()
    auth_client = AuthClient(
        client_id=env("QUICKBOOKS_CLIENT"),
        client_secret=env("QUICKBOOKS_SECRET"),
        environment="production",
        redirect_uri="http://localhost:8000/callback",
    )
    token_path = str(settings.ROOT_DIR / "secrets" / "QUICKBOOKS_REFRESH_TOKEN")
    if os.path.exists(token_path):
        with open(token_path, "r") as refresh_token_file:
            refresh_token = refresh_token_file.read()
    else:
        print("NEED TO GENERATE REFRESH TOKEN!")
        return
    auth_client.refresh(refresh_token=refresh_token)
    with open(token_path, "w") as refresh_token_file:
        refresh_token_file.write(auth_client.refresh_token)
    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=auth_client.refresh_token,
        company_id="9130348538823906",
        minorversion=62,
    )
    return client


def create_line(item_count, linenumber_count, name=None, client=None):
    today = datetime.datetime.today().strftime("%Y/%m/%d")
    if client is None:
        client = get_quickbooks_client()
    line = SalesItemLine()
    line.LineNum = linenumber_count
    item = Item.filter(name=name, qb=client)[0]
    line.Description = item.Description
    line.Amount = item_count * item.UnitPrice
    line.SalesItemLineDetail = SalesItemLineDetail()
    line.SalesItemLineDetail.ItemRef = item.to_ref()
    line.SalesItemLineDetail.Qty = item_count
    line.SalesItemLineDetail.ServiceDate = today
    line.SalesItemLineDetail.UnitPrice = item.UnitPrice
    return line


def invoice_search(invoice_number, customer, client=None):
    """
    invoice_number
        if == 1 then will force create a new one
        999999999 will search for any existing
        specific # will search for that invoice #
    """
    if client is None:
        client = get_quickbooks_client()
    invoice = None
    if invoice_number == 999999999:
        # search for any NeedToSend invoices for chapter
        #   however, can not filter on EmailStatus directly
        invoices = Invoice.query(
            select=f"select * from Invoice where balance > '0' AND CustomerRef = '{customer.Id}'",
            qb=client,
        )
        for invoice_test in invoices:
            if invoice_test.EmailStatus == "NeedToSend":
                invoice = invoice_test
                break
    elif invoice_number != 1 and invoice_number != "":
        # search for specific invoice number
        invoices = Invoice.query(
            select=f"select * from Invoice where DocNumber = '{invoice_number}' AND CustomerRef = '{customer.Id}'",
            qb=client,
        )
        if invoices:
            invoice = invoice[0]
    if invoice is None:
        invoice = Invoice()
        term = Term.filter(name="Two Weeks", qb=client)[0]
        linenumber_count = 1
        invoice.CustomerRef = customer.to_ref()
        invoice.AllowOnlineACHPayment = True
        invoice.BillEmail = customer.PrimaryEmailAddr
        invoice.EmailStatus = "NeedToSend"
        invoice.SalesTermRef = term.to_ref()
        invoice.CustomerMemo = CustomerMemo()
    else:
        linenumber_count = len(invoice.Line)
    return invoice, linenumber_count
