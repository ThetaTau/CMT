"""
Send "Happy Chapter Founding Day" emails to initiated members (actives and
alumni) of any active chapter whose founding anniversary
(``Chapter.founding_date``) falls today. Inactive chapters and colonies
(``candidate_chapter=True``) are skipped since they have not been chartered.

The email body HTML is pulled from the ``Config`` table under the key
``ChapterFoundingDay`` and rendered by ``MemberEmail.from_config``, which
handles CKEditor sanitization, ``{ALL_CAPS_KEY}`` Config substitution, and
the per-recipient unsubscribe footer.

Run examples:
    python manage.py chapter_founding_day_email --list-vars
    python manage.py chapter_founding_day_email --override --dry-run
    python manage.py chapter_founding_day_email --test-user someuser
"""

import datetime

from django.core.management import BaseCommand

from core.models import ACTIVE_STATUSES, ALUMNI_STATUSES
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import User
from thetatauCMT.users.notifications import MemberEmail
from thetatauCMT.users.unsubscribe import is_unsubscribed

CONFIG_KEY = "ChapterFoundingDay"
CATEGORY_SLUG = "chapter_founding_day"
DEFAULT_SUBJECT = "Happy Chapter Founding Day!"

# Initiated members = active + alumni statuses (excludes pledges, advisors,
# and anyone who never completed initiation).
INITIATED_STATUSES = ACTIVE_STATUSES + ALUMNI_STATUSES

TEMPLATE_VARS = [
    ("user", "The member User instance. Common attrs: user.name, " "user.first_name, user.get_full_name, user.email"),
    ("chapter", "The member's chapter. Common attrs: chapter.name, chapter.school"),
    ("founding_date", "The chapter's founding date (Chapter.founding_date)."),
    ("years", "Number of years since the chapter was chartered, e.g. 42."),
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
            "  Happy Chapter Founding Day, {{ chapter.name }} Brothers!",
            "  Today marks {{ years }} years since your chapter was chartered.",
            "",
            "Single-brace ALL_CAPS tokens (e.g. {EC_CONTACT}) are looked up in the",
            "Config table by that exact key at send time.",
        ]
    )
    return "\n".join(lines)


def _founding_day_chapters(today, *, override=False):
    chapters = Chapter.objects.filter(active=True, candidate_chapter=False, founding_date__isnull=False)
    if override:
        return chapters
    return chapters.filter(founding_date__month=today.month, founding_date__day=today.day)


def _member_queryset(chapter):
    return (
        chapter.members.filter(current_status__in=INITIATED_STATUSES)
        .exclude(unsubscribe_email=True)
        .exclude(no_contact=True)
        .exclude(unsubscribe_categories__contains=[CATEGORY_SLUG])
        .distinct()
    )


def _context_for(user, chapter, founding_date, years):
    return {
        "user": user,
        "chapter": chapter,
        "founding_date": founding_date,
        "years": years,
    }


class Command(BaseCommand):
    help = (
        "Send 'Happy Chapter Founding Day' emails using the 'ChapterFoundingDay' "
        "Config template to initiated members (including alumni) of any active, "
        "non-candidate chapter whose founding_date anniversary is today."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-vars",
            action="store_true",
            help="Print the template variables available to the ChapterFoundingDay " "Config value and exit.",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Send to every active, non-candidate chapter with a founding_date, " "regardless of today's date.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log the recipients that would be emailed without sending.",
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
            "their chapter's founding_date. Ignores the date gate and the "
            "chapter's active/candidate_chapter status.",
        )

    def handle(self, *args, **options):
        if options["list_vars"]:
            self.stdout.write(_describe_vars())
            return

        today = datetime.date.today()
        override = options["override"]
        dry_run = options["dry_run"]
        subject = options["subject"]
        test_user = options["test_user"]

        if test_user:
            self._send_preview(test_user, subject, dry_run)
            return

        chapters = _founding_day_chapters(today, override=override)
        total_chapters = chapters.count()
        self.stdout.write(f"Found {total_chapters} chapter(s) with a founding day today ({today}).")

        sent = 0
        total_members = 0
        for chapter in chapters:
            years = today.year - chapter.founding_date.year
            members = _member_queryset(chapter)
            total_members += members.count()
            for user in members:
                if dry_run:
                    self.stdout.write(f"  [dry-run] would email {user} ({user.email}) -- {chapter.name}")
                    continue
                try:
                    notif = MemberEmail.from_config(
                        user,
                        CONFIG_KEY,
                        subject,
                        _context_for(user, chapter, chapter.founding_date, years),
                        unsubscribe=True,
                        category=CATEGORY_SLUG,
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
            self.stdout.write(
                f"Sent {sent}/{total_members} chapter founding day emails across {total_chapters} chapter(s)."
            )

    def _send_preview(self, identifier, subject, dry_run):
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
        if is_unsubscribed(user, CATEGORY_SLUG):
            self.stderr.write(
                f"{user} is opted out of the '{CATEGORY_SLUG}' category; refusing to send preview. "
                f"Remove it from user.unsubscribe_categories or choose a different --test-user."
            )
            return

        chapter = user.chapter
        today = datetime.date.today()
        founding_date = chapter.founding_date or today
        years = today.year - founding_date.year

        if dry_run:
            self.stdout.write(
                f"[dry-run] would send preview to {user} ({user.email}); "
                f"chapter={chapter}, founding_date={founding_date}"
            )
            return
        try:
            notif = MemberEmail.from_config(
                user,
                CONFIG_KEY,
                subject,
                _context_for(user, chapter, founding_date, years),
                unsubscribe=True,
                category=CATEGORY_SLUG,
            )
            if notif is None:
                self.stderr.write(f"Config key '{CONFIG_KEY}' is empty or missing; nothing sent.")
                return
            notif.send()
            self.stdout.write(
                f"Sent preview to {user} ({user.email}); chapter={chapter}, founding_date={founding_date}"
            )
        except Exception as exc:  # noqa: BLE001 - surface failure to operator
            self.stderr.write(f"FAILED sending preview to {user}: {exc}")
