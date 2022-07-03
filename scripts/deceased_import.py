import re
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from django.db.models import Q
from chapters.models import Chapter
from users.models import User, UserStatusChange
from notes.models import UserNote


def run(*args):
    """
    :param args:
    :return: None
    python manage.py runscript deceased_import --script-args "database_backups/Deceased for CMT 012221.accdb"
    """
    path = args[0]
    conn_str = r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};" f"DBQ={path};"
    conn = pyodbc.connect(conn_str)
    # Table name Deceased_Export_092420
    df = pd.read_sql("select * from Deceased_Export_092420", conn)
    # ConstID                                 A###
    # Chapter Name                           Alpha
    # Chapter Abbrev                             A
    # Roll Number                              ###
    # Primary Addressee    first name MI last name
    # First Name                        first name
    # Middle Name                               MI
    # Last Name                          last name
    # Suffix                                  None
    # Previous Name                           None
    # Constituent Code                        Alum
    # Mailing Code             Postal Mail Opt Out
    # Calling Code                     Do Not Call
    # Deceased?                                Yes
    # Transfer Chapter                        None
    # Date Last Change         2015-05-26 00:00:00
    # School Name                             Minn
    # Preferred Class Year                    YYYY
    total = len(df)
    for count, member in df.iterrows():
        print(f"Processing {count + 1}/{total} {member['ConstID']}")
        chapter_name = member["Chapter Name"]
        if chapter_name == "Theta Beta":
            chapter_name = "UW Candidate Chapter"
            continue
        chapter = Chapter.objects.get(Q(name__iexact=chapter_name))
        user_id = member["ConstID"]
        badge_number = re.findall(r"\d+", user_id)[0]
        user_id_combined = member["Chapter Abbrev"] + member["Roll Number"]
        if user_id != user_id_combined:
            # Sometimes the roll number is wrong
            # Sometimes the ConstID does not match the rest
            # We assume the ConstID is correct in most cases
            fixes = {
                "G832": "GB832",
                "D778": "D778",
                "Phi139a": "Phi139",
                "S325a": "S325",
            }
            if user_id in fixes:
                user_id = fixes[user_id]
            elif user_id in ["Phi139b", "S325b"]:
                # A duplicate user?
                continue
            else:
                print(f"    There was an error with \n{member}")
                return
        grad_date_year = member["Preferred Class Year"]
        suffix = member["Suffix"][:10] if member["Suffix"] else " "
        maiden_name = member["Previous Name"] if member["Previous Name"] else " "
        middle_name = member["Middle Name"] if member["Middle Name"] else " "
        if grad_date_year:
            grad_date_year = int(grad_date_year)
        else:
            grad_date_year = 1904
        try:
            user = User.objects.get(user_id=user_id)
            created = False
        except User.DoesNotExist:
            user = User(
                chapter=chapter,
                badge_number=badge_number,
                first_name=member["First Name"],
                middle_name=middle_name,
                last_name=member["Last Name"],
                maiden_name=maiden_name,
                suffix=suffix,
                username=user_id,
                graduation_year=grad_date_year,
                deceased=True,
                no_contact=True,
                deceased_changed=member["Date Last Change"],
                deceased_date=member["Date Last Change"],
            )
            user.save()
            user = User.objects.get(id=user.id)
            created = True
        if created:
            print(f"    create user {user}")
        else:
            print(f"    found user: {user}")
        if not UserStatusChange.objects.filter(user=user):
            print("    Making Status")
            grad_date_year = int(grad_date_year)
            start = datetime(grad_date_year, 1, 1)
            user.set_current_status(
                "pnm",
                start=start - timedelta(365 * 3.5),
                end=start - timedelta(365 * 3),
            )
            user.set_current_status(
                "active", start=start - timedelta(365 * 3), end=start
            )
            user.set_current_status("alumni", start=start)
        else:
            print(f"    Status already exist for {user}")
        transfer_chapter = member["Transfer Chapter"]
        if transfer_chapter:
            print(f"    Adding note of chapter transfer")
            UserNote(
                user=user,
                created_by=User.objects.get(username="venturafranklin@gmail.com"),
                title="Transfer Chapter",
                note=f"The user transferred from chapter: {transfer_chapter}",
            ).save()
