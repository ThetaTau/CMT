from django.core.management import BaseCommand
from django.utils import timezone
from quickbooks.objects.customer import Customer
from quickbooks.objects.invoice import Invoice as QBInvoice
from viewflow.models import Task
from viewflow.activation import STATUS
from forms.flows import InitiationProcessFlow, PledgeProcessFlow
from core.finances import get_quickbooks_client
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
        query = dict(
            process__flow_class=InitiationProcessFlow,
            status=STATUS.NEW,
            flow_task="forms/flows.InitiationProcessFlow.invoice_payment",
        )
        init_function_tasks = Task.objects.filter(**query)
        query = dict(
            process__flow_class=PledgeProcessFlow,
            status=STATUS.NEW,
            flow_task="forms/flows.PledgeProcessFlow.invoice_payment",
        )
        pledge_function_tasks = Task.objects.filter(**query)
        function_tasks = init_function_tasks | pledge_function_tasks
        outstanding_invoice_tasks = {
            str(task.flow_process.invoice): task
            for task in function_tasks
            if task.flow_process.invoice != "999999999"
        }
        print(f"Found {len(outstanding_invoice_tasks)} outstanding_invoice_tasks")
        client = get_quickbooks_client()
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
                # This is a candidate chapter
                # Candidate Chapter is normally in the name
                pass
            elif customer_type == "7300000000000220483":
                # This is a natoff
                continue
            elif customer_type == "7300000000000247061":
                # This is other
                continue
            else:
                # Maybe not chapter/candidate chapter, but other?
                continue
            print(f"Syncing: ", chapter_name)
            try:
                chapter = Chapter.objects.get(name=chapter_name)
            except Chapter.DoesNotExist:
                print(f"    Chapter matching {chapter_name} does not exist")
                continue
            if not chapter.active:
                print("    Chapter not active")
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
                if (len(email_str + email) + 1) < 100 and email not in email_str:
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
                select=f"select * from Invoice where "
                # f"balance > '0' AND "
                f"CustomerRef = '{customer.Id}' ORDER BY DueDate DESC",
                qb=client,
            )
            total = len(invoices)
            for count, invoice_res in enumerate(invoices):
                print(f"    Invoice {count+1}/{total}")
                invoice = QBInvoice.get(invoice_res.Id, qb=client)
                invoice_number = invoice.DocNumber
                invoice_balance = invoice.Balance
                Invoice(
                    link=invoice.InvoiceLink,
                    due_date=invoice.DueDate,
                    central_id=invoice_number,
                    description="<br>".join(
                        [
                            f"{line.Description}; Line Amount: {line.Amount} <br>"
                            for line in invoice.Line
                            if line.DetailType == "SalesItemLineDetail"
                        ]
                    ),
                    total=invoice_balance,
                    chapter=chapter,
                ).save()
                print(f"        {invoice_number=} {invoice_balance=}")
                if invoice_number in outstanding_invoice_tasks:
                    if invoice_balance == 0:
                        print(f"        Invoice {invoice_number} has been paid!")
                        function_task = outstanding_invoice_tasks[invoice_number]
                        activation = function_task.activate()
                        activation.prepare()
                        activation.done()


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
