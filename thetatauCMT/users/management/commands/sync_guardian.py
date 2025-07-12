import csv
import datetime
import io

import environ
import requests
from django.core.management import BaseCommand
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
        users = User.objects.all()
        total = users.count()
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

        print("Number of users", total)
        students = []
        user: User
        for i, user in enumerate(users):
            student_data = {
                "STUDENT_NUMBER": user.id,  # Student ID number
                "FIRST_NAME": user.first_name,
                "LAST_NAME": user.last_name,
                "CAMPUS_EMAIL": user.email_school,
                "PERSONAL_EMAIL": user.email,
                "PREFERRED_NAME": user.preferred_name,
                "STUDENT_STATUS": user.current_status,  # active alumni, etc
                "MOBILE_PHONE": user.phone_number,
                "CLASS_STATUS": user.class_year,  # Year in school at pledging
                "CLASS_YEAR": user.graduation_year,  # YEAR of graduation
                "GENDER": user.preferred_pronouns,  # pronouns
                "ADMIT_TERM": user.class_year,  # Initiation date use Fall 2023, etc
                "TEAM_SPORT1": user.chapter.name,  # chapter
                "TEAM_SPORT2": user.chapter.school,  # University
                "TEAM_SPORT3": ",".join(user.current_roles),  # role
            }
            students.append(student_data)

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
            with open(f"exports/{file_name}", "wb") as f:
                f.write(csv_bytes)
            return

        url = "https://thetatau.guardianconduct.com"
        api = f"{url}/api/auth/login/admin"

        env = environ.Env()
        email = env("GUARDIAN_EMAIL")
        password = env("GUARDIAN_PASSWORD")

        response = requests.post(
            api,
            data={"email": email, "password": password},
            headers={"Accept": "application/json"},
        )

        if response.status_code == 200:
            response_data = response.json()
            print(f"Login successful {response_data}")
        else:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            return
        access_token = response_data.get("access_token")
        upload_url = f"{url}/api/file/upload"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        files = {"file": (file_name, csv_buffer, "text/csv")}
        data = {
            "key": "data_import",
        }
        upload_response = requests.post(
            upload_url, headers=headers, data=data, files=files
        )

        if upload_response.status_code == 200:
            upload_result = upload_response.json()
            print(f"File upload successful {upload_result}")
        else:
            print(f"File upload failed: {upload_response.status_code}")
            print(upload_response.text)
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
