"""
Notes:
    To test run command
        docker-compose -f local.yml run --rm django python manage.py chapter_pledges_check
"""

from django.conf import settings
from django.core.management import BaseCommand
import gspread

from chapters.models import Chapter


# python manage.py update_shingle_contacts
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync the current chapter contact information with Shingle Order form"

    # A command must define handle()
    def handle(self, *args, **options):
        service_path = (
            settings.ROOT_DIR / "secrets" / "ChapterManagementTool-b239bceff1a7.json"
        )
        gc = gspread.service_account(filename=service_path)
        sh = gc.open_by_key("1Tt8VdIkmcSq-mC6rXPWsHfFqXGVYn7LA5UzLKsfMhM8")
        worksheet = sh.worksheet("Chapters")
        header = worksheet.row_values(1)
        header_align = {
            "Chapter Code": "id",
            "Chapter Designation": "name",
            "University": "school",
            "Address 1": "address",
            "City": "address__locality__name",
            "State": "address__locality__state__name",
            "Postal Code": "address__locality__postal_code",
            "Country": "address__locality__state__country__name",
            "Status": "active",
            "Contact Name": "address_contact",
            "Contact E-Mail": "email",
            "Contact Phone": "address_phone_number",
            "Last Updated": "modified",
        }
        chapter_values = Chapter.objects.values(
            "id",
            "name",
            "school",
            "address__locality__name",
            "address__locality__state__name",
            "address__locality__postal_code",
            "address__locality__state__country__name",
            "address__street_number",
            "address__route",
            "active",
            "address_contact",
            "address_phone_number",
            "email",
            "modified",
        )
        rows = [header]
        for chapter_value in chapter_values:
            row = []
            chapter_obj = Chapter.objects.get(id=chapter_value["id"])
            for header_name in header:
                value = ""
                if header_name == "Address 1":
                    street_num = chapter_value["address__street_number"]
                    street_name = chapter_value["address__route"]
                    if street_name and street_num:
                        value = f"{street_num} {street_name}"
                elif header_name == "Notify":
                    value = ", ".join(chapter_obj.council_emails())
                elif header_name == "Shopify Customer ID":
                    value = chapter_obj.get_misc_data("shopify", "Not Set")
                elif header_name in header_align:
                    chapter_name = header_align[header_name]
                    value = chapter_value[chapter_name]
                    if chapter_name == "modified":
                        value = value.strftime("%Y%m%d")
                    elif chapter_name == "id":
                        value = f"{value:03d}"
                    elif chapter_name == "address_contact":
                        if value == "Not Set":
                            value = "Chapter Officer"
                row.append(value)
            rows.append(row)
        first_letter = worksheet.find(header[-1]).address.split("1")[0]
        worksheet.update(f"A1:{first_letter}{len(rows)}", rows)
