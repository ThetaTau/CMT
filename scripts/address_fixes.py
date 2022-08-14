from users.models import User
from core.address import fix_address
from core.models import TODAY_END


def run(*args):
    """
    python manage.py runscript address_fixes --script-args active pnm
    """
    # addresses = Address.objects.filter(locality__isnull=True).all()
    # Not all addresses are needed only care about addresses connected to user
    if not args:
        args = ["active", "activepend", "alumnipend", "pnm"]
    users = User.objects.filter(
        current_status__in=args,
    )
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
