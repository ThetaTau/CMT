from address.models import Address
from django.db.models import Count
from users.models import User
from chapters.models import Chapter
from forms.models import DisciplinaryProcess


def run(*args):
    """
    python manage.py runscript address_deduplicate
    """
    duplicates = (
        Address.objects.values("street_number", "route", "locality")
        .annotate(add_count=Count("street_number"))
        .filter(add_count__gt=1)
    )
    total = duplicates.count()
    for count, address in enumerate(duplicates):
        print(f"{count+1}/{total}")
        del address["add_count"]
        if (
            not address["street_number"]
            and not address["route"]
            and address["locality"] is None
        ):
            # These address have just not been parsed yet
            print("SKIPPING THE NONE!")
            continue
        addresses = Address.objects.filter(**address)
        addresses_list = list(addresses)
        main_address = addresses_list[0]
        address_ids = addresses.values("id")
        print("    Total to fix:", address_ids.count())
        update_objs = set()
        users = User.objects.filter(address__in=address_ids)
        update_objs.update(list(users))
        chapters = Chapter.objects.filter(address__in=address_ids)
        update_objs.update(list(chapters))
        disciplinary = DisciplinaryProcess.objects.filter(address__in=address_ids)
        update_objs.update(list(disciplinary))
        print("        objs found: ", update_objs)
        for update_obj in update_objs:
            update_obj.address = main_address
        if users:
            User.objects.bulk_update(users, ["address"])
        if chapters:
            Chapter.objects.bulk_update(chapters, ["address"])
        if disciplinary:
            DisciplinaryProcess.objects.bulk_update(disciplinary, ["address"])
        for old_address in addresses_list[1:]:
            old_address.delete()
