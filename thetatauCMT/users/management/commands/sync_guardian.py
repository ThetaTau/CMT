import csv
import datetime
import io

import environ
import requests
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Cast, Coalesce
from users.models import User


# python manage.py sync_guardian -override -debug
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync member data with Guardian Conduct System"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")
        parser.add_argument("-debug", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        today = datetime.date.today().strftime("%A")
        override = options.get("override", False)
        if today != "Tuesday" and not override:
            print(f"Not today {today}")
            return
        guardian_fields = [
            "STUDENT_NUMBER",
            "FIRST_NAME",
            "MIDDLE_NAME",
            "LAST_NAME",
            "DATE_OF_BIRTH",
            "GENDER",
            "IDENTIFIED_GENDER",
            "PREFERRED_NAME",
            "PERSON_TYPE",
            "PRIVACY_INDICATOR",
            "ADDITIONAL_ID1",
            "ADDITIONAL_ID2",
            "CLASS_STATUS",
            "STUDENT_STATUS",
            "CLASS_YEAR",
            "MAJOR",
            "CREDITS_SEMESTER",
            "CREDITS_CUMULATIVE",
            "GPA",
            "MOBILE_PHONE",
            "MOBILE_PHONE_CARRIER",
            "OPT_OUT_OF_TEXT",
            "CAMPUS_EMAIL",
            "PERSONAL_EMAIL",
            "PHOTO_FILE_NAME",
            "PERM_PO_BOX",
            "PERM_PO_BOX_COMBO",
            "ADMIT_TERM",
            "STUDENT_ATHLETE",
            "TEAM_SPORT1",
            "TEAM_SPORT2",
            "TEAM_SPORT3",
            "HOLD1",
            "HOLD2",
            "HOLD3",
            "HOLD4",
            "HOLD5",
            "HOLD6",
            "HOLD7",
            "ETHNICITY",
            "ADDRESS1_TYPE",
            "ADDRESS1_STREET_LINE_1",
            "ADDRESS1_STREET_LINE_2",
            "ADDRESS1_STREET_LINE_3",
            "ADDRESS1_STREET_LINE_4",
            "ADDRESS1_CITY",
            "ADDRESS1_STATE_NAME",
            "ADDRESS1_ZIP",
            "ADDRESS1_COUNTRY",
            "ADDRESS1_PHONE",
            "ADDRESS2_TYPE",
            "ADDRESS2_STREET_LINE_1",
            "ADDRESS2_STREET_LINE_2",
            "ADDRESS2_STREET_LINE_3",
            "ADDRESS2_STREET_LINE_4",
            "ADDRESS2_CITY",
            "ADDRESS2_STATE_NAME",
            "ADDRESS2_ZIP",
            "ADDRESS2_COUNTRY",
            "ADDRESS2_PHONE",
            "ADDRESS3_TYPE",
            "ADDRESS3_STREET_LINE_1",
            "ADDRESS3_STREET_LINE_2",
            "ADDRESS3_STREET_LINE_3",
            "ADDRESS3_STREET_LINE_4",
            "ADDRESS3_CITY",
            "ADDRESS3_STATE_NAME",
            "ADDRESS3_ZIP",
            "ADDRESS3_COUNTRY",
            "ADDRESS3_PHONE",
            "CONTACT1_TYPE",
            "CONTACT1_NAME",
            "CONTACT1_RELATIONSHIP",
            "CONTACT1_HOME_PHONE",
            "CONTACT1_WORK_PHONE",
            "CONTACT1_MOBILE_PHONE",
            "CONTACT1_EMAIL",
            "CONTACT1_STREET",
            "CONTACT1_STREET2",
            "CONTACT1_CITY",
            "CONTACT1_STATE",
            "CONTACT1_ZIP",
            "CONTACT1_COUNTRY",
            "CONTACT2_TYPE",
            "CONTACT2_NAME",
            "CONTACT2_RELATIONSHIP",
            "CONTACT2_HOME_PHONE",
            "CONTACT2_WORK_PHONE",
            "CONTACT2_MOBILE_PHONE",
            "CONTACT2_EMAIL",
            "CONTACT2_STREET",
            "CONTACT2_STREET2",
            "CONTACT2_CITY",
            "CONTACT2_STATE",
            "CONTACT2_ZIP",
            "CONTACT2_COUNTRY",
            "CONTACT3_TYPE",
            "CONTACT3_NAME",
            "CONTACT3_RELATIONSHIP",
            "CONTACT3_HOME_PHONE",
            "CONTACT3_WORK_PHONE",
            "CONTACT3_MOBILE_PHONE",
            "CONTACT3_EMAIL",
            "CONTACT3_STREET",
            "CONTACT3_STREET2",
            "CONTACT3_CITY",
            "CONTACT3_STATE",
            "CONTACT3_ZIP",
            "CONTACT3_COUNTRY",
            "TERM",
        ]
        users = User.objects.all()
        total = users.count()
        print("Number of users", total)
        students = users.values(
            STUDENT_NUMBER=Coalesce(Cast("id", CharField()), Value("")),
            FIRST_NAME=Coalesce(F("first_name"), Value("")),
            LAST_NAME=Coalesce(F("last_name"), Value("")),
            CAMPUS_EMAIL=Coalesce(F("email_school"), Value("")),
            PERSONAL_EMAIL=Coalesce(F("email"), Value("")),
            PREFERRED_NAME=Coalesce(F("preferred_name"), Value("")),
            STUDENT_STATUS=Coalesce(F("current_status"), Value("")),
            MOBILE_PHONE=Coalesce(Cast("phone_number", CharField()), Value("")),
            CLASS_STATUS=Coalesce(F("class_year"), Value("")),
            CLASS_YEAR=Coalesce(Cast("graduation_year", CharField()), Value("")),
            GENDER=Coalesce(F("preferred_pronouns"), Value("")),
            ADMIT_TERM=Coalesce(Cast("initiation__date", CharField()), Value("")),
            TEAM_SPORT1=Coalesce(F("chapter__name"), Value("")),
            TEAM_SPORT2=Coalesce(F("chapter__school"), Value("")),
            TEAM_SPORT3=Coalesce(
                Func(
                    F("current_roles"),
                    Value(", "),
                    function="array_to_string",
                    output_field=CharField(),  # tell Django it comes back as text
                ),
                Value(""),
            ),
        ).exclude(
            Q(STUDENT_NUMBER="")
            | Q(FIRST_NAME="")
            | Q(LAST_NAME="")
            | Q(CAMPUS_EMAIL="")
        )
        file_name = f"students-{datetime.date.today().strftime('%Y-%m-%d')}.csv"
        # Write CSV to a binary buffer instead of a file
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=guardian_fields,
            restval="",
        )
        writer.writeheader()
        writer.writerows(students)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        csv_buffer.close()

        debug = options.get("debug", False)
        if debug:
            # Save binary CSV to file (optional, for debugging)
            print("Debug mode: saving CSV to file")
            with open(f"exports/{file_name}", "wb") as f:
                f.write(csv_bytes)
            return

        url = "https://thetatau.guardianconduct.com"
        api = f"{url}/api/auth/login/admin"

        env = environ.Env()
        env.read_env(str(settings.ROOT_DIR / ".env"))
        email = env("GUARDIAN_EMAIL")
        password = env("GUARDIAN_PASSWORD")

        response = requests.post(
            api,
            data={"email": email, "password": password},
            headers={"Accept": "application/json"},
        )

        if response.status_code == 200:
            response_data = response.json()
            print(f"Login successful {response_data}\n\n")
        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            return
        access_token = response_data.get("access_token")
        upload_url = f"{url}/api/file/upload"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        files = [("file", (file_name, csv_bytes, "text/csv"))]
        data = {
            "key": "data_import",
        }
        upload_response = requests.post(
            upload_url, headers=headers, data=data, files=files
        )

        if upload_response.status_code == 200:
            upload_result = upload_response.json()
            print(f"File upload successful {upload_result}\n\n")
        else:
            print(f"File upload failed: {upload_response.status_code}")
            print(upload_response.text, upload_response.reason)
            return

        data_import_url = f"{url}/api/data-import"
        data_import_payload = {
            # upload_result is the response from file upload
            "files": [upload_result],
            "type": "studentImport",
        }
        import_response = requests.post(
            data_import_url, headers=headers, json=data_import_payload
        )

        if import_response.status_code == 200:
            print("Data import successful")
            print(import_response.json())
        else:
            print(f"Data import failed: {import_response.status_code}")
            print(import_response.text)
