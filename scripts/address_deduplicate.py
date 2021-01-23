from address.models import Address
from django.db.models import Count
from core.address import deduplicate


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
        deduplicate(addresses)
