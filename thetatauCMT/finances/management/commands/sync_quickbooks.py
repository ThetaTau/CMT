import os
import environ
from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone
from quickbooks import QuickBooks
from intuitlib.client import AuthClient
from quickbooks.objects.customer import Customer
from quickbooks.objects.invoice import Invoice as QBInvoice
from chapters.models import Chapter
from finances.models import Invoice


# python manage.py sync_quickbooks
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync Quickbooks"

    def add_arguments(self, parser):
        parser.add_argument("-live", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        live = options.get("live", False)
        print(f"This is LIVE: ", live)
        Invoice.objects.all().delete()
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
        customers = Customer.all(qb=client, max_results=1000)
        for customer in customers:
            chapter_name = customer.CompanyName
            if not chapter_name or not hasattr(customer, "CustomerTypeRef"):
                continue
            customer_type = customer.CustomerTypeRef["value"]
            if customer_type == "7300000000000214210":
                # This is a chapter
                if "Chapter" in chapter_name:
                    chapter_name = customer.CompanyName.split(" Chapter")[0]
            elif customer_type == "7300000000000214211":
                # This is a colony
                # Colony is normally in the name
                pass
            elif customer_type == "7300000000000220483":
                # This is a natoff
                continue
            elif customer_type == "7300000000000247061":
                # This is other
                continue
            else:
                # Maybe not chapter/colony, but other?
                continue
            print(f"Syncing: ", chapter_name)
            try:
                chapter = Chapter.objects.get(name=chapter_name)
            except Chapter.DoesNotExist:
                print(f"    Chapter matching {chapter_name} does not exist")
                continue
            balance = customer.Balance
            print("    New balance: ", balance)
            if live:
                chapter.balance = balance
                chapter.balance_date = timezone.now()
                chapter.save()
            # Total emails are limited to 100 characters, need to be strategic
            # [regent, scribe, vice, treasurer]
            council_emails = chapter.get_current_officers_council_specific()
            # [email_regent, email_scribe, email_vice_regent, email_treasurer, email_corresponding_secretary, email,
            generic_emails = chapter.get_generic_chapter_emails()
            emails = [
                # Tresurer
                council_emails[3],
                generic_emails[3],
                # Generic
                generic_emails[5],
                # Regent
                council_emails[0],
                generic_emails[0],
                # Vice
                council_emails[2],
                generic_emails[2],
                # Scribe
                council_emails[1],
                generic_emails[1],
                # Corsec
                generic_emails[4],
            ]
            emails = [email for email in emails if email]
            if not emails:
                print("    NO EMAILS")
            email_str = ""
            for email in emails:
                if not isinstance(email, str):
                    email = email.email
                if not email:
                    continue
                if (len(email_str + email) + 1) < 100:
                    email_str = email_str + email + ","
                else:
                    break
            email_str = email_str[:-1]
            print("    Current Email: ", customer.PrimaryEmailAddr.Address)
            if customer.PrimaryEmailAddr.Address != email_str:
                print("    New Email: ", email_str)
                if live:
                    customer.PrimaryEmailAddr.Address = email_str
                    customer.save(qb=client)
            else:
                print("    No new emails")
            if not balance > 0:
                continue
            invoices = QBInvoice.query(
                select=f"select * from Invoice where balance > '0' AND CustomerRef = '{customer.Id}'",
                qb=client,
            )
            for invoice_res in invoices:
                invoice = QBInvoice.get(invoice_res.Id, qb=client)
                Invoice(
                    link=invoice.InvoiceLink,
                    due_date=invoice.DueDate,
                    central_id=invoice.DocNumber,
                    description="<br>".join(
                        [
                            f"{line.Description}; Line Amount: {line.Amount} <br>"
                            for line in invoice.Line
                            if line.DetailType == "SalesItemLineDetail"
                        ]
                    ),
                    total=invoice.Balance,
                    chapter=chapter,
                ).save()


"""
{'Id': '28122', # ID in Quickbooks
 'Balance': 559.0,
 'DocNumber': '23337', # ID used by central office
 'DueDate': '2021-04-11',
 'TotalAmt': 559.0,
 'TxnDate': '2021-02-01',
 'EmailStatus': 'EmailSent',
 'InvoiceLink': ''
 'BillEmail': invoice.BillEmail.Address
 'CustomerMemo': None,
 'Line': [<quickbooks.objects.detailline.SalesItemLine at 0x12581a50>,
  <quickbooks.objects.detailline.SalesItemLine at 0x12581b70>,
  <quickbooks.objects.detailline.SalesItemLine at 0x12581a70>,
  <quickbooks.objects.detailline.SubtotalLine at 0x149aea90>],
 """
