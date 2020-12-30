from users.models import User
from core.address import fix_address


def run():
    """
    python manage.py runscript address_fixes
    """
    # addresses = Address.objects.filter(locality__isnull=True).all()
    # Not all addresses are needed only care about addresses connected to user
    users = User.objects.all()
    total = users.count()
    for count, user in enumerate(users):
        address = user.address
        print(f"{count + 1}/{total} for address: {address}")
        if address is None or address.locality is not None:
            continue
        if address.raw == "None":
            user.address = None
            user.save()
            continue
        fix_address(address)
