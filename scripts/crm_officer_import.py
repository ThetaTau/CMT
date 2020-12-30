import re
import csv
from datetime import datetime
from django.db.models import Q
from users.models import User, UserRoleChange, forever


def get_first_from_list(list_items):
    """given a list of items find the first that exists or return None"""
    return next((s for s in list_items if s), None)


role_map = {
    "chapter officer": "",
    "president": "regent",
    "vice president": "vice regent",
    "secretary": "scribe",
    "other adviser": "adviser",
    "alumni adviser": "adviser",
    "rush chair": "recruitment chair",
    "build chair": "project chair",
}


def run(*args):
    """
    Constituent ID
    Constituent Specific Attributes Chapter Name Description
    Organization Relation Relationship
    Organization Relation From Date
    Organization Relation To Date
    Contact Greeting Salutation Text
    First Name
    Last Name
    Constituency Code
    Mobile Phone Number
    Primary Phone Number
    Email Address Number
    Other Email Number

    :param args:
    :return: None
    python manage.py runscript crm_officer_import --script-args database_backups/AllOfficers12Nov2020_GOOD.csv
    """
    path = args[0]
    with open(path) as f:
        reader = csv.DictReader(f)
        for count, member in enumerate(reader):
            user_id = member["Constituent ID"]
            print(f"Processing {count + 1}/13151 {user_id}")
            try:
                user = User.objects.get(Q(user_id__iexact=user_id))
            except User.DoesNotExist:
                print("     !!!! User does not exist", member)
            # I don't care about email here...
            # email = member["Email Address Number"]
            # email_school = member["Other Email Number"]
            # phone_number = get_first_from_list(
            #     [member["Primary Phone Number"], member["Mobile Phone Number"]]
            # )
            # phone_number = "".join(re.findall(r"\d+", phone_number))
            # phone_number = phone_number[:17]
            # if email or email_school:
            #     if user.email != email and user.email != email_school:
            #         print("    User email does not equal")
            # if user.phone_number != phone_number:
            #     print("    User phone_number does not equal")
            role = member["Organization Relation Relationship"].lower()
            if role in role_map:
                role = role_map[role]
            start = member["Organization Relation From Date"]
            end = member["Organization Relation To Date"]
            start = datetime.strptime(start, "%m/%d/%Y").date()
            if end:
                end = datetime.strptime(end, "%m/%d/%Y").date()
            else:
                end = forever()
            try:
                UserRoleChange.objects.update_or_create(
                    user=user,
                    role=role,
                    defaults=dict(user=user, role=role, start=start, end=end,),
                )
            except UserRoleChange.MultipleObjectsReturned:
                # We could go down the route of finding the right start/end and update?
                #   but already more than one role for the user that is enough
                pass
