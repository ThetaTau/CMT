"""
Send graduation-anniversary emails to alumni whose graduation StatusChange
falls N years ago in the current grad season.

The email body HTML is pulled from the ``Config`` table under the key
``GradAnniversary`` and rendered by ``MemberEmail.from_config``, which
handles CKEditor sanitization, ``{ALL_CAPS_KEY}`` Config substitution, and
the per-recipient unsubscribe footer. This command owns only the schedule,
recipient query, and per-user context — swap ``CONFIG_KEY`` / query and the
same pipeline drives any other Config-authored blast.

Run examples:
    python manage.py grad_anniversary_email --list-vars
    python manage.py grad_anniversary_email --override --dry-run
    python manage.py grad_anniversary_email --override --years 5
    python manage.py grad_anniversary_email --test-user someuser
"""

import datetime

from django.core.management import BaseCommand

from thetatauCMT.forms.models import StatusChange
from thetatauCMT.users.models import User
from thetatauCMT.users.notifications import MemberEmail

CONFIG_KEY = "GradAnniversary"
DEFAULT_YEARS = 5
DEFAULT_SUBJECT = "Theta Tau Graduation Anniversary"

# Months in which the command actually sends (unless --override is used).
# May => spring grads, December => fall grads.
SPRING_SEND_MONTH = 5
FALL_SEND_MONTH = 12

# Grad-season windows on the graduation date itself.
SPRING_GRAD_MONTHS = range(1, 8)  # Jan-Jul
FALL_GRAD_MONTHS = range(8, 13)  # Aug-Dec


def _grad_queryset(target_year, grad_months):
    return (
        StatusChange.objects.filter(
            reason="graduate",
            date_start__year=target_year,
            date_start__month__in=list(grad_months),
        )
        .exclude(user__unsubscribe_email=True)
        .exclude(user__no_contact=True)
        .select_related("user", "user__chapter")
    )


TEMPLATE_VARS = [
    (
        "user",
        "The graduating User instance. Common attrs: user.name, " "user.first_name, user.get_full_name, user.email",
    ),
    ("chapter", "The user's chapter. Common attrs: chapter.school, chapter.name"),
    ("graduation_date", "The graduation date (StatusChange.date_start)."),
    ("graduation_year", "The year the member graduated (int)."),
    ("years", "Number of years since graduation, e.g. 5."),
]


def _describe_vars():
    lines = [
        f"Available template variables for Config key '{CONFIG_KEY}':",
        "",
    ]
    for name, desc in TEMPLATE_VARS:
        lines.append(f"  {{{{ {name} }}}} -- {desc}")
    lines.extend(
        [
            "",
            "Example snippet:",
            "  Dear {{ user.first_name }},",
            "  It's been {{ years }} years since you graduated from {{ chapter.school }}...",
            "",
            "Single-brace ALL_CAPS tokens (e.g. {EC_CONTACT}) are looked up in the",
            "Config table by that exact key at send time.",
        ]
    )
    return "\n".join(lines)


def _context_for(user, graduation_date, years):
    return {
        "user": user,
        "chapter": getattr(user, "chapter", None),
        "graduation_date": graduation_date,
        "graduation_year": graduation_date.year,
        "years": years,
    }


class Command(BaseCommand):
    help = (
        "Send graduation-anniversary emails using the 'GradAnniversary' Config "
        "template. Sends on the 1st of May (spring grads) and 1st of December "
        "(fall grads) unless --override is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-vars",
            action="store_true",
            help="Print the template variables available to the GradAnniversary " "Config value and exit.",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Send regardless of today's date.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log the recipients that would be emailed without sending.",
        )
        parser.add_argument(
            "--years",
            type=int,
            default=DEFAULT_YEARS,
            help=f"Anniversary milestone in years (default {DEFAULT_YEARS}).",
        )
        parser.add_argument(
            "--subject",
            type=str,
            default=DEFAULT_SUBJECT,
            help="Subject line for the email.",
        )
        parser.add_argument(
            "--test-user",
            type=str,
            default=None,
            help="Send a single preview email to this username (or email) using "
            "their most recent graduate StatusChange if any, else a "
            "synthetic graduation date years ago from today. Ignores the "
            "May/December date gate and the graduate query.",
        )

    def handle(self, *args, **options):
        if options["list_vars"]:
            self.stdout.write(_describe_vars())
            return

        today = datetime.date.today()
        override = options["override"]
        dry_run = options["dry_run"]
        years = options["years"]
        subject = options["subject"]
        test_user = options["test_user"]

        if test_user:
            self._send_preview(test_user, subject, years, dry_run)
            return

        if not override and not (today.day == 1 and today.month in (SPRING_SEND_MONTH, FALL_SEND_MONTH)):
            self.stdout.write(
                f"Skipping: today is {today}. Command sends on the 1st of "
                f"May and December (use --override to force)."
            )
            return

        season_month = today.month if today.month in (SPRING_SEND_MONTH, FALL_SEND_MONTH) else SPRING_SEND_MONTH
        target_year = today.year - years
        if season_month == SPRING_SEND_MONTH:
            grad_months = SPRING_GRAD_MONTHS
            season_label = "spring"
        else:
            grad_months = FALL_GRAD_MONTHS
            season_label = "fall"

        grads = _grad_queryset(target_year, grad_months)
        total = grads.count()
        self.stdout.write(
            f"Found {total} {season_label} {target_year} graduate(s) for a "
            f"{years}-year anniversary email (unsubscribed / no-contact users "
            f"already excluded)."
        )

        sent = 0
        for grad in grads:
            user = grad.user
            if dry_run:
                self.stdout.write(f"  [dry-run] would email {user} ({user.email})")
                continue
            try:
                notif = MemberEmail.from_config(
                    user,
                    CONFIG_KEY,
                    subject,
                    _context_for(user, grad.date_start, years),
                    unsubscribe=True,
                )
                if notif is None:
                    self.stderr.write(f"Config key '{CONFIG_KEY}' is empty or missing; aborting.")
                    return
                notif.send()
                sent += 1
                self.stdout.write(f"  sent to {user} ({user.email})")
            except Exception as exc:  # noqa: BLE001 - surface per-recipient failures, keep going
                self.stderr.write(f"  FAILED for {user}: {exc}")

        if not dry_run:
            self.stdout.write(f"Sent {sent}/{total} anniversary emails.")

    def _send_preview(self, identifier, subject, years, dry_run):
        try:
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            user = User.objects.filter(email=identifier).first()
            if user is None:
                self.stderr.write(f"No user found with username or email '{identifier}'.")
                return

        if user.unsubscribe_email or user.no_contact:
            self.stderr.write(
                f"{user} has unsubscribe_email or no_contact set; refusing to send preview. "
                f"Choose a different --test-user or clear the flag on this user first."
            )
            return

        today = datetime.date.today()
        grad = StatusChange.objects.filter(user=user, reason="graduate").order_by("-date_start").first()
        graduation_date = grad.date_start if grad is not None else today.replace(year=today.year - years)

        if dry_run:
            self.stdout.write(
                f"[dry-run] would send preview to {user} ({user.email}); " f"graduation_date={graduation_date}"
            )
            return
        try:
            notif = MemberEmail.from_config(
                user,
                CONFIG_KEY,
                subject,
                _context_for(user, graduation_date, years),
                unsubscribe=True,
            )
            if notif is None:
                self.stderr.write(f"Config key '{CONFIG_KEY}' is empty or missing; nothing sent.")
                return
            notif.send()
            self.stdout.write(f"Sent preview to {user} ({user.email}); graduation_date={graduation_date}")
        except Exception as exc:  # noqa: BLE001 - surface failure to operator
            self.stderr.write(f"FAILED sending preview to {user}: {exc}")
