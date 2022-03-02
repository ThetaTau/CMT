# Generated by Django 2.0.3 on 2018-06-15 18:31
import os
import csv
import datetime
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.core.management import BaseCommand
from forms.models import Initiation, StatusChange, Depledge, PrematureAlumnus
from users.models import UserRoleChange


TODAY_DATE = datetime.date.isoformat(datetime.date.today()).replace("-", "")


OER = [
    "Submitted by",
    "Date Submitted",
    "Chapter Name",
    "Office",
    "Term Begins (M/D/YYYY)",
    "Term Ends (M/D/YYYY)",
    "*ChapRoll",
    "First Name",
    "Last Name",
    "Mobile Phone",
    "Personal Email",
    "Campus Email",
]


INIT = [
    "Submitted by",
    "Date Submitted",
    "Initiation Date",
    "Chapter Name",
    "Graduation Year",
    "Roll Number",
    "First Name",
    "Middle Name",
    "Last Name",
    "Overall GPA",
    "A Pledge Test Scores",
    "B Pledge Test Scores",
    "Initiation Fee",
    "Late Fee",
    "Badge Style",
    "Sum for member",
]


COOP = [
    "Submitted by",
    "Date Submitted",
    "*ChapRoll",
    "First Name",
    "Last Name",
    "Reason Away",
    "Start Date (M/D/YYYY)",
    "End Date (M/D/YYYY)",
    "Miles from Campus**",
]


DEPLEDGE = [
    "Submitted by",
    "Date Submitted",
    "Chapter Name",
    "First Name",
    "Last Name",
    "*ChapRoll",
    "EmailAddress",
    "Reason Depledged",
    "Date Depledged (M/D/YYYY)",
]


MSCR = [
    "Submitted by",
    "Date Submitted",
    "School Name",
    "*ChapRoll",
    "First Name",
    "Last Name",
    "Mobile Phone",
    "EmailAddress",
    "Reason for Status Change",
    "Degree Received",
    "Graduation Date (M/D/YYYY)",
    "Employer",
    "Work Email",
    "Attending Graduate School where ?",
    "Withdrawing from school?",
    "Date withdrawn (M/D/YYYY)",
    "Transferring to what school ?",
    "Date of transfer (M/D/YYYY)",
]


class Command(BaseCommand):
    # Show this when the user types help
    help = "Send forms to central officer"

    def add_arguments(self, parser):
        parser.add_argument("password", nargs=1, type=str)
        parser.add_argument("date_start", nargs=1, type=str)
        parser.add_argument("-date_end", nargs=1, type=str)
        parser.add_argument("-chapter", nargs=1, type=str)
        parser.add_argument(
            "-exclude",
            nargs=1,
            type=str,
            help="mscr, init, depledge, coop, oer, prealumn",
        )
        parser.add_argument("-no-email", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        password = options["password"][0]
        date_start = datetime.datetime.strptime(options["date_start"][0], "%Y%m%d")
        date_end_str = options.get("date_end", None)
        chapter_only = options.get("chapter", None)
        no_email = options.get("no_email", False)
        if date_end_str:
            date_end_str = date_end_str[0]
            date_end = datetime.datetime.strptime(
                date_end_str, "%Y%m%d"
            ) + datetime.timedelta(days=1)
        else:
            date_end = datetime.datetime.today() + datetime.timedelta(days=1)
        exclude = options.get("exclude", "")
        if exclude:
            exclude = exclude[0]
        else:
            exclude = ""
        print("Exluding", exclude)
        query = {"created__gte": date_start, "created__lte": date_end}
        pre_alumn_query = {
            "finished__gte": date_start,
            "finished__lte": date_end,
            "approved_exec": True,
        }
        file_path = f"exports//{TODAY_DATE}"
        if chapter_only is not None:
            chapter_only = chapter_only[0]
            print(f"Only for chapter {chapter_only}")
            query.update({"user__chapter__name": chapter_only})
            pre_alumn_query.update({"user__chapter__name": chapter_only})
            file_path += f"_{chapter_only.upper().replace(' ', '_')}"
        initiations = Initiation.objects.filter(**query)
        depledges = Depledge.objects.filter(**query)
        officers = UserRoleChange.objects.filter(**query)
        statuses = StatusChange.objects.filter(**query)
        prealumns = PrematureAlumnus.objects.filter(**pre_alumn_query)
        file_paths_out = []
        if initiations and "init" not in exclude:
            file_paths_out.append(f"{file_path}_init.csv")
            with open(f"{file_path}_init.csv", "w", newline="") as init_file:
                writer = csv.DictWriter(init_file, fieldnames=INIT)
                writer.writeheader()
                for initiation in initiations:
                    badge = initiation.badge
                    badge_code = ""
                    badge_cost = 0
                    if badge:
                        badge_code = badge.code
                    chapter = initiation.user.chapter
                    init_fee = 75
                    if chapter.candidate_chapter:
                        init_fee = 30
                    late_fee = 0
                    init_date = initiation.date
                    init_submit = initiation.created.date()
                    delta = init_submit - init_date
                    if delta.days > 28:
                        if not chapter.candidate_chapter:
                            late_fee = 25
                    total = init_fee + late_fee
                    row = {
                        "Submitted by": "",
                        "Date Submitted": init_submit,
                        "Initiation Date": init_date,
                        "Chapter Name": chapter.name,
                        "Graduation Year": initiation.user.graduation_year,
                        "Roll Number": initiation.roll,
                        "First Name": initiation.user.first_name,
                        "Middle Name": "",
                        "Last Name": initiation.user.last_name,
                        "Overall GPA": initiation.gpa,
                        "A Pledge Test Scores": initiation.test_a,
                        "B Pledge Test Scores": initiation.test_b,
                        "Initiation Fee": init_fee,
                        "Late Fee": late_fee,
                        "Badge Style": badge_code,
                        "Sum for member": total,
                    }
                    writer.writerow(row)
        if depledges and "depledge" not in exclude:
            file_paths_out.append(f"{file_path}_depledge.csv")
            with open(f"{file_path}_depledge.csv", "w", newline="") as depledge_file:
                writer = csv.DictWriter(depledge_file, fieldnames=DEPLEDGE)
                writer.writeheader()
                for depledge in depledges:
                    row = {
                        "Submitted by": "",
                        "Date Submitted": depledge.created,
                        "Chapter Name": depledge.user.chapter.name,
                        "First Name": depledge.user.first_name,
                        "Last Name": depledge.user.last_name,
                        "*ChapRoll": depledge.user.clean_user_id,
                        "EmailAddress": depledge.user.email,
                        "Reason Depledged": depledge.REASONS.get_value(depledge.reason),
                        "Date Depledged (M/D/YYYY)": depledge.date.strftime("%m/%d/%Y"),
                    }
                    writer.writerow(row)
        if officers and "oer" not in exclude:
            file_paths_out.append(f"{file_path}_oer.csv")
            with open(f"{file_path}_oer.csv", "w", newline="") as oer_file:
                writer = csv.DictWriter(oer_file, fieldnames=OER)
                writer.writeheader()
                for officer in officers:
                    if "pd" in officer.role:
                        role = "PD Chair"
                    else:
                        role = officer.role.title()
                    row = {
                        "Submitted by": "",
                        "Date Submitted": officer.created,
                        "Chapter Name": officer.user.chapter.name,
                        "Office": role,
                        "Term Begins (M/D/YYYY)": officer.start.strftime("%m/%d/%Y"),
                        "Term Ends (M/D/YYYY)": officer.end.strftime("%m/%d/%Y"),
                        "*ChapRoll": officer.user.clean_user_id,
                        "First Name": officer.user.first_name,
                        "Last Name": officer.user.last_name,
                        "Mobile Phone": "",
                        "Personal Email": "",
                        "Campus Email": "",
                    }
                    writer.writerow(row)
        mscr_true = False
        coop_true = False
        if statuses or prealumns:
            with open(f"{file_path}_mscr.csv", "w", newline="") as mscr_file:
                mscr_writer = csv.DictWriter(mscr_file, fieldnames=MSCR)
                mscr_writer.writeheader()
                with open(f"{file_path}_coop.csv", "w", newline="") as coop_file:
                    coop_writer = csv.DictWriter(coop_file, fieldnames=COOP)
                    coop_writer.writeheader()
                    for status in statuses:
                        if "test" in status.user.chapter.school.lower():
                            continue
                        main_row = {
                            "Submitted by": "",
                            "Date Submitted": status.created,
                            "*ChapRoll": status.user.clean_user_id,
                            "First Name": status.user.first_name,
                            "Last Name": status.user.last_name,
                        }
                        reason = status.reason
                        if reason not in ["coop", "military"]:
                            if "mscr" in exclude:
                                continue
                            mscr_true = True
                            new_school = ""
                            if status.new_school:
                                new_school = status.new_school.school
                            transfer_date = ""
                            withdraw_date = ""
                            withdraw = ""
                            grad_date = ""
                            if reason == "withdraw":
                                withdraw_date = status.date_start.strftime("%m/%d/%Y")
                                withdraw = "Yes"
                            elif reason == "transfer":
                                transfer_date = status.date_start.strftime("%m/%d/%Y")
                            elif reason == "graduate":
                                grad_date = status.date_start.strftime("%m/%d/%Y")
                            degree = status.degree
                            if degree:
                                if degree == "phd":
                                    degree = "PhD"
                                else:
                                    degree = degree.upper()
                            row = {
                                "School Name": status.user.chapter.school,
                                "Mobile Phone": status.user.phone_number,
                                "EmailAddress": status.user.email,
                                "Reason for Status Change": status.REASONS.get_value(
                                    reason
                                ),
                                "Degree Received": degree,
                                "Graduation Date (M/D/YYYY)": grad_date,
                                "Employer": status.employer,
                                "Work Email": status.email_work,
                                "Attending Graduate School where ?": "",
                                "Withdrawing from school?": withdraw,
                                "Date withdrawn (M/D/YYYY)": withdraw_date,
                                "Transferring to what school ?": new_school,
                                "Date of transfer (M/D/YYYY)": transfer_date,
                            }
                            row.update(main_row)
                            mscr_writer.writerow(row)
                        else:
                            if "coop" in exclude:
                                continue
                            coop_true = True
                            row = {
                                "Reason Away": status.REASONS.get_value(status.reason),
                                "Start Date (M/D/YYYY)": status.date_start.strftime(
                                    "%m/%d/%Y"
                                ),
                                "End Date (M/D/YYYY)": status.date_end.strftime(
                                    "%m/%d/%Y"
                                ),
                                "Miles from Campus**": status.miles,
                            }
                            row.update(main_row)
                            coop_writer.writerow(row)
                for prealumn in prealumns:
                    if "prealumn" in exclude:
                        continue
                    row = {
                        "Submitted by": "",
                        "Date Submitted": prealumn.created,
                        "*ChapRoll": prealumn.user.clean_user_id,
                        "First Name": prealumn.user.first_name,
                        "Last Name": prealumn.user.last_name,
                        "School Name": prealumn.user.chapter.school,
                        "Mobile Phone": prealumn.user.phone_number,
                        "EmailAddress": prealumn.user.email,
                        "Reason for Status Change": "Prealumn",
                        "Degree Received": "",
                        "Graduation Date (M/D/YYYY)": "",
                        "Employer": "",
                        "Work Email": "",
                        "Attending Graduate School where ?": "",
                        "Withdrawing from school?": "",
                        "Date withdrawn (M/D/YYYY)": "",
                        "Transferring to what school ?": "",
                        "Date of transfer (M/D/YYYY)": "",
                    }
                    mscr_writer.writerow(row)
            if mscr_true:
                file_paths_out.append(f"{file_path}_mscr.csv")
            if coop_true:
                file_paths_out.append(f"{file_path}_coop.csv")
        if not no_email:
            self.send_email(file_paths_out, password, chapter=chapter_only)

    def send_email(self, attachments, password, chapter=None):
        sender = "Frank.Ventura@ThetaTau.org"
        gmail_password = password
        recipients = [
            "central.office@thetatau.org",
            sender,
        ]
        outer = MIMEMultipart()
        outer["To"] = ", ".join(recipients)
        outer["From"] = sender
        outer.preamble = "You will not see this in a MIME-aware mail reader.\n"
        text = f"Attached are the form submission up to {TODAY_DATE}"
        if chapter is not None:
            outer["Subject"] = f"Form Submissions to {TODAY_DATE} {chapter} Chapter"
            text += f" for {chapter} Chapter"
        else:
            outer["Subject"] = f"Form Submissions to {TODAY_DATE}"
        outer.attach(MIMEText(text, "plain"))
        for file in attachments:
            with open(file, "rb") as fp:
                msg = MIMEBase("application", "octet-stream")
                msg.set_payload(fp.read())
            encoders.encode_base64(msg)
            msg.add_header(
                "Content-Disposition", "attachment", filename=os.path.basename(file)
            )
            outer.attach(msg)
        composed = outer.as_string()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.ehlo()
            server.login(sender, gmail_password)
            server.sendmail(sender, recipients, composed)
