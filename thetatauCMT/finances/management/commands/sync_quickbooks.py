import os
import environ
from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone
from quickbooks import QuickBooks
from intuitlib.client import AuthClient
from quickbooks.objects.customer import Customer
from chapters.models import Chapter


class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync Quickbooks"

    def add_arguments(self, parser):
        parser.add_argument("-live", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        live = options.get("live", False)
        print(f"This is LIVE: ", live)
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
        )
        customers = Customer.all(qb=client)
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
            emails = set(
                chapter.get_current_officers_council(False)[0].values_list(
                    "email", flat=True
                )
            ) | set(chapter.get_generic_chapter_emails())
            if not emails:
                print("    NO EMAILS")
            email_str = ", ".join(emails)
            print("    Current Email: ", customer.PrimaryEmailAddr.Address)
            if customer.PrimaryEmailAddr.Address != email_str:
                print("    New Email: ", email_str)
                if live:
                    customer.PrimaryEmailAddr.Address = email_str
                    customer.save(qb=client)
            else:
                print("    No new emails")
