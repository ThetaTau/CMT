import re
import csv
from datetime import datetime
from django.db.models import Q
from chapters.models import Chapter, ChapterCurricula, Region
from users.models import User

inactive_chapters = [
    ["Gamma", "G", "Colorado School of Mines", "Central",],
    ["Theta", "Th", "Columbia University", "Mid-Atlantic",],
    ["Iota", "I", "Missouri University of Science and Technology", "Midwest",],
    ["Lambda", "L", "University of Utah", "Northwest",],
    ["Nu", "N", "Carnegie-Mellon University", "Great Lakes",],
    ["Psi", "Psi", "Montana College of Mineral Science & Technology", "Northwest",],
    ["Delta Beta", "DB", "University of Louisville", "Midwest",],
    ["Zeta Beta", "ZB", "Utah State University", "Northwest",],
    ["Eta Beta", "HB", "University of Houston", "Central",],
    # ["Theta Beta", "ThB", "University of Washington", "Northwest",], Currently colony
    ["Iota Beta", "IB", "University of Detroit", "Great Lakes",],
    ["Mu Beta", "MB", "GMI Engineering & Management Institute", "Great Lakes",],
    ["Nu Beta", "NB", "University of Wisconsin–Platteville", "Midwest",],
    ["Pi Beta", "PiB", "Western Michigan University", "Great Lakes",],
    ["Sigma Beta", "SB", "University of Wisconsin–Milwaukee", "Midwest",],
    ["Phi Beta", "PhB", "Oakland University", "Great Lakes",],
    ["Epsilon Gamma", "EG", "Northwestern University", "Midwest",],
    ["SLO Colony", "SLO", "California Polytechnic State University, SLO", "Southwest"],
]

for name, abbr, school, region in inactive_chapters:
    break
    region = Region.objects.get(name=region)
    chapter, created = Chapter.objects.update_or_create(
        name=name,
        school=school,
        defaults=dict(
            name=name, region=region, school=school, greek=abbr, active=False
        ),
    )
    print(chapter, created)


def phone_email(member_row):
    """
    "Email Address"
    "Other Email"
    "Email"
    "Email 2"
    "Mobile Phone"
    "Home Phone"
    "Alternate Phone"
    "Phone"
    "Account Phone"
    "Primary Phone"
    """
    phone_number = ""
    email = None
    email_school = None
    for val_type_col, value_col in [
        ("CnPh_1_01_Phone_type", "CnPh_1_01_Phone_number"),
        ("CnPh_1_02_Phone_type", "CnPh_1_02_Phone_number"),
        ("CnPh_1_03_Phone_type", "CnPh_1_03_Phone_number"),
        ("CnPh_1_04_Phone_type", "CnPh_1_04_Phone_number"),
    ]:
        val_type = member_row[val_type_col].lower()
        value = member_row[value_col].lower()
        if not value:
            continue
        if "phone" in val_type and phone_number == "":
            # We will only keep one phone
            phone_number = value
        elif "email" in val_type:
            if len(value) < 6:
                continue
            if ".edu" in value and email_school is None:
                email_school = value
            elif email is None:
                email = value
            else:
                # There is second email, but not edu
                email_school = value
    if email_school and email is None:
        email = email_school
    if email and email_school is None:
        email_school = email
    return phone_number, email, email_school


def get_first_from_list(list_items):
    """given a list of items find the first that exists or return None"""
    return next((s for s in list_items if s), None)


def run(*args):
    """
    :param args:
    :return: None
    python manage.py runscript crm_import --script-args database_backups/Allmember_export_12Nov2020.csv
    """
    path = args[0]
    with open(path) as f:
        reader = csv.DictReader(f)
        for count, member in enumerate(reader):  # 39245
            print(f"Processing {count + 1}/39245 {member['CnBio_ID']}")
            if member["CnBio_Org_Name"]:
                # This is a chapter record
                continue
            try:
                chapter = Chapter.objects.get(
                    Q(school__iexact=member["CnPrAl_School_name"])
                    | Q(name__iexact=member["CnAttrCat_2_01_Description"])
                    | Q(name__iexact=member["CnRelEdu_1_01_Campus"])
                    | Q(school__iexact=member["CnRelEdu_1_01_School_name"])
                )
            except Chapter.MultipleObjectsReturned:
                try:
                    chapter = Chapter.objects.get(
                        Q(name__iexact=member["CnAttrCat_2_01_Description"])
                    )
                except Chapter.DoesNotExist:
                    try:
                        chapter = Chapter.objects.get(
                            Q(name__iexact=member["CnRelEdu_1_01_Campus"])
                        )
                    except Chapter.DoesNotExist:
                        chapter = Chapter.objects.get(
                            Q(school__iexact=member["CnRelEdu_1_01_School_name"])
                        )
            badge_number = re.findall(r"\d+", member["CnBio_ID"])[0]
            employer_position = get_first_from_list(
                [
                    member["CnPrBs_Position"],
                    member["CnPrBsAdr_Position"],
                    member["CnPrBs_Profession"],
                ]
            )
            if employer_position is None:
                employer_position = ""
            major = get_first_from_list(
                [
                    member["CnPrAlMaj_1_01_Tableentriesid"],
                    member["CnPrAlMaj_1_02_Tableentriesid"],
                    member["CnPrAlMaj_1_03_Tableentriesid"],
                    member["CnRelEdu_1_01_Degree"],
                ]
            )
            if major:
                major = major.lower()
                try:
                    major, created_major = chapter.curricula.filter(
                        major__iexact=major
                    ).get_or_create(
                        defaults=dict(major=major, chapter=chapter, approved=False)
                    )
                except ChapterCurricula.MultipleObjectsReturned:
                    major = chapter.curricula.filter(major__iexact=major).first()
            grad_date_year = get_first_from_list(
                [
                    member["CnPrAl_Class_of"],
                    member["CnPrAl_Date_graduated"],
                    member["CnRelEdu_1_01_Class_of"],
                    member["CnRelEdu_1_02_Class_of"],  # previous degree
                ]
            )
            if grad_date_year:
                grad_date_year = grad_date_year[
                    -4:
                ]  # could be grad date, only want year
                grad_date_year = int(grad_date_year)
            else:
                grad_date_year = 1900
            emergency_first_name = None
            emergency_middle_name = None
            emergency_last_name = None
            emergency_nickname = None
            emergency_relation = None
            if member["CnSpSpBio_First_Name"]:
                emergency_first_name = member["CnSpSpBio_First_Name"]
                emergency_middle_name = member["CnSpSpBio_Middle_Name"]
                emergency_last_name = member["CnSpSpBio_Last_Name"]
                emergency_nickname = member["CnSpSpBio_Nickname"]
                if member["CnRelInd_1_01_Is_Spouse"] == "Yes":
                    emergency_relation = "partner"
                else:
                    emergency_relation = "other"
            elif member["CnRelInd_1_01_First_Name"]:
                emergency_first_name = member["CnRelInd_1_01_First_Name"]
                emergency_middle_name = member["CnRelInd_1_01_Middle_Name"]
                emergency_last_name = member["CnRelInd_1_01_Last_Name"]
                emergency_relation = "other"
            phone_number, email, email_school = phone_email(member)
            if phone_number:
                phone_number = "".join(re.findall(r"\d+", phone_number))
                phone_number = phone_number[:17]
            title = member["CnBio_Title_1"].lower().replace(".", "")
            if title not in ["mr", "miss", "ms", "mrs", "mx", "none"]:
                title = "none"
            created = False
            try:
                user_id = f"{chapter.greek}{badge_number}"
                if email == "" or email is None:
                    print(f"    !!! User missing email")
                    email = email_school = f"{user_id}@FAKE.org"
                user, created = User.objects.filter(
                    Q(email__iexact=email)
                    | Q(username__iexact=email)
                    | Q(email_school__iexact=email_school)
                    | Q(user_id__iexact=user_id)
                ).update_or_create(
                    defaults=dict(
                        chapter=chapter,
                        user_id=user_id,
                        badge_number=badge_number,
                        major=major,
                        degree=member["CnPrAl_Degree"].lower(),
                        first_name=member["CnBio_First_Name"],
                        middle_name=member["CnBio_Middle_Name"],
                        last_name=member["CnBio_Last_Name"],
                        maiden_name=member["CnBio_Maiden_name"],
                        title=title,
                        suffix=member["CnBio_Suffix_1"][:10],
                        nickname=member["CnBio_Nickname"],
                        email_school=email_school,
                        email=email,
                        username=email,
                        phone_number=phone_number,
                        graduation_year=grad_date_year,
                        deceased={"Yes": True, "No": False}[member["CnBio_Deceased"]],
                        emergency_first_name=emergency_first_name,
                        emergency_middle_name=emergency_middle_name,
                        emergency_last_name=emergency_last_name,
                        emergency_nickname=emergency_nickname,
                        emergency_relation=emergency_relation,
                        employer=member["CnPrBsAdr_OrgName"],
                        employer_position=employer_position,
                    )
                )
            except User.MultipleObjectsReturned:
                try:
                    # most cases the id would match
                    user = User.objects.get(user_id__iexact=member["CnBio_ID"])
                except User.DoesNotExist:
                    users = User.objects.filter(
                        Q(email__iexact=email)
                        | Q(email_school__iexact=email_school)
                        | Q(user_id__iexact=member["CnBio_ID"])
                    )
                    if len(users) == 1:
                        user = users[0]
                    else:
                        print(f"    !!! Multiple users {users}")
                        print(
                            f"        should be: ",
                            [
                                f"{inf.split('_')[-1]}: {val}"
                                for inf, val in member.items()
                                if val
                            ],
                        )
                        for num, user in enumerate(users):
                            print(
                                "        ",
                                num,
                                user,
                                user.email,
                                user.email_school,
                                user.user_id,
                                user.graduation_year,
                            )
                        pick = int(input("Pick user: "))
                        user = users[pick]
                        print(f"Picked user: ", user)
            if created:
                print(f"    creat user {user}")
            else:
                print(f"    found user: {user}")
            address_first_raw = member["CnAdrPrf_Addrline1"]
            if address_first_raw:
                number, address_first = "", ""
                if " " in address_first_raw:
                    number, *address_first = address_first_raw.split(" ")
                    address_first = " ".join(address_first)
                    try:
                        int(number)
                    except ValueError:
                        number, address_first = "", address_first_raw
                address_second = member["CnAdrPrf_Addrline2"]
                locality = member["CnAdrPrf_City"]
                postal_code = member["CnAdrPrf_ZIP"]
                state_code = member["CnAdrPrf_State"]
                country = member["CnAdrPrf_ContryLongDscription"]
                user.address = {
                    "raw": f"{address_first_raw} {address_second}, "
                    f"{locality}, {state_code} {postal_code}, {country}",
                    "street_number": number,
                    "route": f"{address_first} {address_second}",
                    "locality": locality,
                    "postal_code": postal_code,
                    "state_code": state_code,
                    "country": country,
                }
                date_changed = member["CnAdrPrf_DateLastChanged"]
                if date_changed:
                    date_changed = datetime.strptime(date_changed, "%m/%d/%Y")
                user.address_changed = date_changed
            address_first_raw = member["CnPrBsAdr_Addrline1"]
            if address_first_raw:
                number, address_first = "", ""
                if " " in address_first_raw:
                    number, *address_first = address_first_raw.split(" ")
                    address_first = " ".join(address_first)
                    try:
                        int(number)
                    except ValueError:
                        number, address_first = "", address_first_raw
                address_second = member["CnPrBsAdr_Addrline2"]
                locality = member["CnPrBsAdr_City"]
                postal_code = member["CnPrBsAdr_ZIP"]
                state_code = member["CnPrBsAdr_State"]
                user.employer_address = {
                    "raw": f"{address_first_raw} {address_second}, "
                    f"{locality}, {state_code} {postal_code}",
                    "street_number": number,
                    "route": f"{address_first} {address_second}",
                    "locality": locality,
                    "postal_code": postal_code,
                    "state_code": state_code,
                }
            status = member["CnCnstncy_1_01_CodeLong"]
            status_trans = {
                "Alum": "alumni",
                "Student": "active",
                "Expelled": "expelled",
                "Friend": "friend",
                "Prospective Pledge": "pnm",
            }
            if status in status_trans:
                user.set_current_status(status_trans[status])
            if (
                status == "Off Mailing List"
                or member["CnBio_Requests_no_e-mail"] == "Yes"
                or user.deceased
            ):
                user.no_contact = True
            user.save()
