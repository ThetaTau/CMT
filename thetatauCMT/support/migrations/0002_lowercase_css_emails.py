"""Lowercase the emails of Chapter Support Specialist accounts made before the fix.

allauth stores every email lowercased and finds accounts by an exact match on the lowercased
address, for password resets and email sign-in alike. Staff accounts added on the "Add a
Chapter Support Specialist" page kept the capitals typed there ("First.Last@..."), so their
password reset said no account existed. New accounts are stored lowercased; this repairs the
accounts made before that.
"""

from django.db import migrations


def lowercase_css_emails(apps, schema_editor):
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    UserStatusChange = apps.get_model("users", "UserStatusChange")

    css_ids = UserStatusChange.objects.filter(status="css").values_list("user_id", flat=True)
    for user in User.objects.filter(pk__in=list(css_ids)).order_by("pk"):
        _lowercase_user(User, user)
        _lowercase_addresses(EmailAddress, user)


def _lowercase_user(User, user):
    lower = (user.email or "").lower()
    fields = []
    if user.email != lower:
        user.email = lower
        fields.append("email")
    # The username is the address the account was made with; keep it in step unless the
    # lowercased name already belongs to someone else (usernames are unique).
    if lower and user.username != lower and user.username.lower() == lower:
        if User.objects.filter(username=lower).exclude(pk=user.pk).exists():
            print(f"\n  Chapter Support Specialist {user.pk}: username {lower!r} is taken; kept {user.username!r}.")
        else:
            user.username = lower
            fields.append("username")
    if fields:
        user.save(update_fields=fields)


def _lowercase_addresses(EmailAddress, user):
    for address in EmailAddress.objects.filter(user=user).order_by("pk"):
        lower = address.email.lower()
        if address.email == lower:
            continue
        # Only one account may hold a verified address.
        verified_elsewhere = EmailAddress.objects.filter(email=lower, verified=True).exclude(user=user).exists()
        twin = EmailAddress.objects.filter(user=user, email=lower).exclude(pk=address.pk).first()
        if twin is not None:
            # The lowercase row already exists: keep it, with this row's verified and primary flags.
            was_verified, was_primary = address.verified, address.primary
            address.delete()
            twin.verified = twin.verified or (was_verified and not verified_elsewhere)
            twin.primary = twin.primary or was_primary
            twin.save(update_fields=["verified", "primary"])
            continue
        if address.verified and verified_elsewhere:
            # Another account has verified this address; an Admin decides which account keeps it.
            print(f"\n  Chapter Support Specialist {user.pk}: {lower!r} is verified on another account; not changed.")
            continue
        address.email = lower
        address.save(update_fields=["email"])


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0001_initial"),
        ("users", "0048_css_contact_visibility_text"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [migrations.RunPython(lowercase_css_emails, migrations.RunPython.noop)]
