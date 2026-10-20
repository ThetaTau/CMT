"""TRWI-12: seed realistic Transition Reports data for end-to-end QA.

Builds a small, dedicated, fully self-contained dataset covering every
TRWI-1..11 capability: templates (all 4 position types, plus one
position-specific override), obligations in every status (open, submitted,
missed, na_vacant), a multi-generation report chain, an attachment, mixed
acknowledgments, prompt-derived AND manual tags, and one named login account
per TRWI-6 access role (successor officer, Regent, RD, CCD, National Officer,
plus an unrelated member who must see nothing) -- see
``docs/specs/transition-reports-qa.md`` for the full walkthrough.

Deliberately NOT randomized (no ``--seed``/Faker): every name, chapter, and
answer is hand-written and identical on every run, which is more useful for a
QA script than Faker output would be, and the command is already fully
idempotent without needing a fixed RNG seed for reproducibility.

Reuses real service functions wherever one exists (``generate_obligations``,
``get_or_create_report``, ``submit_report``, ``close_as_na_vacant``,
``acknowledge_report``, ``set_manual_tags``) rather than hand-constructing
rows, so the seeded data is exactly what the real app would have produced --
including real watson search-index updates and real tag derivation.

Usage::

    docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo
    docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo --flush
    docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo --force
"""

import datetime

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import NAT_OFFICERS
from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.forms.models import RiskManagement
from thetatauCMT.regions.models import Region
from thetatauCMT.transitions import services
from thetatauCMT.transitions.models import ReportAttachment, ReportTemplate
from thetatauCMT.users.models import User, UserRoleChange, UserStatusChange

EMAIL_DOMAIN = "transitions-qa.thetatau.local"
DEFAULT_PASSWORD = "transitionsqa"

REGION_NAME = "[QA] Transitions Region"
REGION2_NAME = "[QA] Transitions Region 2"
CHAPTER_ALPHA = "[QA] Transitions Chapter Alpha"
CHAPTER_BETA = "[QA] Transitions Chapter Beta"
CHAPTER_GAMMA = "[QA] Transitions Chapter Gamma"
CHAPTER_DELTA = "[QA] Transitions Chapter Delta"

# Answer content reused across whichever template a position resolves to --
# looked up by prompt_key, so the same bank works for the CHAPTER_OFFICER
# default, the COMMITTEE_CHAIR/COUNCIL/NATIONAL_OFFICER defaults, and the
# treasurer-specific override alike. Anything not listed here (an optional
# prompt this command doesn't bother personalizing) gets left blank.
RICH_ANSWERS = {
    "successes": (
        "We moved our weekly chapter meeting from Wednesday night to Sunday evening and attendance jumped from "
        "roughly half the chapter to nearly everyone, because Sunday didn't conflict with weeknight labs. We also "
        "switched dues collection to a single Venmo request sent the first week of the semester instead of chasing "
        "individual e-transfers all term, which cut collection time from six weeks down to about ten days."
    ),
    "failures": (
        "We waited too long to replace our broken card reader on the chapter house door. It took a maintenance "
        "request, two follow-up emails, and almost a month before facilities finally swapped it, and in the "
        "meantime people were propping the door open, which is a security problem. Next time: call facilities "
        "directly instead of only emailing, and escalate to the RD after a week of silence."
    ),
    "campus_contacts": (
        "Maria Gonzalez in the Student Activities Office (activities@example.edu) approves all our room bookings "
        "and is fastest by email, not phone. Facilities requests go through the online ticket portal, not a person, "
        "so CC the department chair on anything urgent or it sits for weeks."
    ),
    "key_dates": (
        "IFC dues are due October 1st; start collecting September 1st.\n"
        "Room reservations for spring semester open November 15th; submit within the first week or good slots "
        "are gone.\n"
        "Annual chapter audit paperwork is due April 15th; start pulling receipts in March."
    ),
    "systems_access": (
        "Our shared documents live in a chapter Google Drive folder (chapter admins have edit access, everyone "
        "else has view access). The Venmo business account for dues is under the Treasurer's login, and "
        "credentials are stored in the shared password manager vault, not written down anywhere. Do not paste "
        "actual passwords into this report."
    ),
    "unfinished": (
        "We started, but did not finish, moving our recruitment tracking spreadsheet into the shared Drive folder. "
        "It is still sitting on the outgoing recruitment chair's personal laptop. Also still pending: a "
        "decision from the landlord on next year's lease renewal terms, expected sometime next month."
    ),
    "first_30_days": (
        "First, get access to the shared Drive folder and the Venmo account, since nothing else works without "
        "those. Second, introduce yourself to Maria in Student Activities before you need something from her. "
        "Third, review the last two terms' worth of this report so you already know what's coming."
    ),
    "financial_handoff": (
        "Checking account balance as of handoff: roughly two months of operating expenses. Two reimbursements "
        "are still outstanding from the spring formal (waiting on receipts from the social chair). The full "
        "ledger is a shared spreadsheet in the Drive folder, not on paper. Reconcile it monthly, not just at "
        "year end, or discrepancies pile up fast."
    ),
    "committee_roster": (
        "Three members served on the committee this term. Two were reliable and should be asked back; one missed "
        "most meetings and would probably do better in a smaller, lower-commitment role next time."
    ),
    "program_logistics": (
        "The venue for our fall social books up fast, so reserve it at least two months ahead, not the usual "
        "three weeks. Our regular caterer requires a deposit at booking time, not at the event, which caught us "
        "off guard the first time."
    ),
    "experts": (
        "Reach out to our chapter's founding advisor for anything historical or bylaws-related. She has been "
        "answering these questions for over a decade and responds quickly to email."
    ),
    "pitfalls": (
        "Nobody warned me how much of this role is just following up on emails nobody else answers. Budget more "
        "time for that than you'd expect."
    ),
    "anything_else": "Say yes to the regional conference if you can swing it. It's where most of this advice actually came from.",
}
MINIMAL_ANSWERS = {
    "successes": "Recruitment went okay this term. We tabled a few times and got some new members interested.",
    "failures": "A few events were not well attended. Not sure exactly why, maybe bad timing.",
    "campus_contacts": "Student Activities Office handles room bookings, email is best.",
    "key_dates": "Dues due each October. Audit paperwork due each spring.",
    "systems_access": "Documents are in the shared Drive folder. Venmo is under the Treasurer login.",
    "unfinished": "Recruitment spreadsheet still needs to move to the shared Drive folder.",
    "first_30_days": "Get access to the Drive folder and Venmo account first.",
    "financial_handoff": "Balance is healthy. No outstanding reimbursements that I know of.",
    "committee_roster": "Three members served this term, all were fine.",
    "program_logistics": "Book the venue early, it goes fast.",
}
_DEFAULT_ANSWER = ""


def _answer_for(prompt, rich):
    bank = RICH_ANSWERS if rich else MINIMAL_ANSWERS
    text = bank.get(prompt.prompt_key, _DEFAULT_ANSWER)
    if text and prompt.min_chars and len(text) < prompt.min_chars:
        text = (text + " Additional detail included so this answer clears the minimum length for QA seed data.")[
            : max(prompt.min_chars, len(text)) + 40
        ]
    if prompt.max_chars and len(text) > prompt.max_chars:
        text = text[: prompt.max_chars - 3] + "..."
    return text


class Command(BaseCommand):
    help = "Seed realistic Transition Reports demo/QA data end-to-end (TRWI-12)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for every seeded login account (default '{DEFAULT_PASSWORD}').",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing [QA] Transitions demo data (only this command's own rows) before seeding.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required to run when settings.DEBUG is off (production-like).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Computed fresh per invocation (never at module-import time) so a
        # long-lived process re-importing this module doesn't act on a stale
        # date, and so tests can freeze_time() across repeated calls.
        self.today = datetime.date.today()
        ensure_seeding_allowed(options["force"])
        password = options["password"]
        if options["flush"]:
            self._flush()

        # The 4 position-type default templates (TRWI-2) -- this command only
        # adds the ONE treasurer-specific override on top of them, so they
        # must exist first or every other seeded position has no template to
        # resolve to.
        call_command("seed_transition_prompt_set", verbosity=0)
        self._ensure_treasurer_override_template()

        region = self._ensure_region(REGION_NAME)
        region2 = self._ensure_region(REGION2_NAME)
        alpha = self._ensure_chapter(CHAPTER_ALPHA, region, "QAA")
        beta = self._ensure_chapter(CHAPTER_BETA, region, "QAB")
        gamma = self._ensure_chapter(CHAPTER_GAMMA, region, "QAC")
        delta = self._ensure_chapter(CHAPTER_DELTA, region2, "QAD")

        users = self._seed_users(password, alpha, beta, gamma, delta)
        region.directors.add(users["rd"])

        services.generate_obligations()

        reports = self._seed_reports(users)
        self._seed_attachment(reports["pred2"])
        services.acknowledge_report(reports["pred3"], users["treasurer"])
        services.set_manual_tags(reports["pred3"], ["expertise"])

        obligation = users["vacant_pred"].transition_report_obligations.get(position_key="vice regent")
        services.close_as_na_vacant(obligation)

        self._report(users, password)

    # ------------------------------------------------------------------ setup
    def _flush(self):
        self.stdout.write(self.style.WARNING("Flushing existing Transitions QA seed data..."))
        seed_user_count = User.objects.filter(email__endswith=f"@{EMAIL_DOMAIN}").count()
        _total_deleted, _ = User.objects.filter(email__endswith=f"@{EMAIL_DOMAIN}").delete()
        self.stdout.write(f"  removed {seed_user_count} seed user(s) and everything cascaded from them")
        Chapter.objects.filter(name__in=[CHAPTER_ALPHA, CHAPTER_BETA, CHAPTER_GAMMA, CHAPTER_DELTA]).delete()
        for name in (REGION_NAME, REGION2_NAME):
            region = Region.objects.filter(name=name).first()
            if region and not region.chapters.exists():
                region.delete()

    def _ensure_treasurer_override_template(self):
        """The one position-specific override required by TRWI-12 -- distinct
        from the CHAPTER_OFFICER type default seeded by
        ``seed_transition_prompt_set``, demonstrating exact-match resolution.
        """
        template, _created = ReportTemplate.objects.update_or_create(
            position_type="CHAPTER_OFFICER",
            position_key="treasurer",
            defaults={
                "name": "Treasurer Transition Report",
                "description": "Treasurer-specific version of the chapter officer report, with an added financial handoff prompt.",
                "is_active": True,
            },
        )
        prompts = [
            (
                "successes",
                "What went well this term that your successor should keep doing?",
                "long_text",
                "success",
                True,
                150,
                2000,
            ),
            (
                "failures",
                "What didn't go well, and what would you do differently?",
                "long_text",
                "failure",
                True,
                150,
                2000,
            ),
            (
                "financial_handoff",
                "Financial handoff: account balances, outstanding invoices/reimbursements, and where the ledger lives",
                "long_text",
                "systems",
                True,
                100,
                2000,
            ),
            (
                "key_dates",
                "Recurring dates and deadlines, and how far ahead to start each",
                "list",
                "calendar",
                True,
                80,
                2000,
            ),
            (
                "unfinished",
                "What's unfinished or in-flight that lands on your successor's desk on day one?",
                "long_text",
                "continuity",
                True,
                100,
                2000,
            ),
            (
                "first_30_days",
                "If your successor does only three things in their first 30 days, what should they be?",
                "long_text",
                "advice",
                True,
                120,
                1500,
            ),
        ]
        for order, (prompt_key, label, field_type, tag, is_required, min_chars, max_chars) in enumerate(
            prompts, start=1
        ):
            template.prompts.update_or_create(
                prompt_key=prompt_key,
                defaults={
                    "order": order,
                    "label": label,
                    "field_type": field_type,
                    "tag": tag,
                    "is_required": is_required,
                    "min_chars": min_chars,
                    "max_chars": max_chars,
                },
            )
        return template

    def _ensure_region(self, name):
        region, _ = Region.objects.get_or_create(
            name=name, defaults={"website": "https://thetatau.org", "facebook": "https://thetatau.org"}
        )
        return region

    def _ensure_chapter(self, name, region, greek):
        chapter, _created = Chapter.objects.get_or_create(
            name=name,
            defaults={
                "region": region,
                "school": f"{name} School",
                "candidate_chapter": False,
                "greek": greek,
                "active": True,
            },
        )
        if chapter.region_id != region.pk or not chapter.active:
            chapter.region = region
            chapter.active = True
            chapter.save(update_fields=["region", "active"])
        return chapter

    # ------------------------------------------------------------------ users
    def _seed_users(self, password, alpha, beta, gamma, delta):
        # canonical key -> (email local-part, display name, chapter, role_or_None,
        # end_offset_days, badge offset). A positive end_offset keeps the role
        # CURRENT (open obligation); a negative one is far enough in the past to
        # be picked up by generate_obligations' scan window (LOOKBACK_GRACE_DAYS
        # = 365) but already past its due date, so it becomes submitted/missed.
        # "early" is the exception to "current means open obligation": its term
        # ends past the lookahead window, so it has NO obligation yet and shows
        # a "Start report" row instead.
        specs = {
            "treasurer": ("treasurer", "QA Treasurer Successor", alpha, "treasurer", 30, 1),
            "regent": ("regent", "QA Regent", alpha, "regent", 35, 2),
            "early": ("early", "QA Early Starter Scribe", alpha, "scribe", 120, 18),
            "rd": ("rd", "QA Regional Director", beta, None, None, 3),
            "ccd": ("ccd", "QA Candidate Chapter Director", beta, "candidate chapter director", 38, 4),
            "natoff": ("natoff", "QA National Officer", beta, "national director", 42, 5),
            "council": ("council", "QA Grand Scribe", beta, "grand scribe", 44, 17),
            "outsider": ("outsider", "QA Outsider Member", gamma, None, None, 6),
            "pred1": ("pred.treasurer.1", "QA Predecessor Treasurer One", alpha, "treasurer", -300, 7),
            "pred2": ("pred.treasurer.2", "QA Predecessor Treasurer Two", alpha, "treasurer", -150, 8),
            "pred3": ("pred.treasurer.3", "QA Predecessor Treasurer Three", alpha, "treasurer", -40, 9),
            "missed_pred": ("pred.scribe.missed", "QA Predecessor Scribe Missed", alpha, "scribe", -60, 10),
            "vacant_pred": (
                "pred.vice-regent.vacant",
                "QA Predecessor Vice Regent",
                beta,
                "vice regent",
                -70,
                11,
            ),
            "council_pred": ("pred.grand-regent", "QA Predecessor Grand Regent", beta, "grand regent", -100, 12),
            "committee_pred": ("pred.events-chair", "QA Predecessor Events Chair", beta, "events chair", -80, 13),
            "outside_region_pred": (
                "pred.regent.outside-region",
                "QA Predecessor Outside Region Regent",
                delta,
                "regent",
                -110,
                14,
            ),
            "national_pred": (
                "pred.national-officer",
                "QA Predecessor National Officer",
                delta,
                "national director",
                -90,
                15,
            ),
            "ccd_pred": (
                "pred.ccd",
                "QA Predecessor Candidate Chapter Director",
                delta,
                "candidate chapter director",
                -95,
                16,
            ),
        }

        users = {}
        for key, (local_part, name, chapter, role, end_offset_days, badge_offset) in specs.items():
            user = self._ensure_user(local_part, name, chapter, password, badge_offset)
            if role:
                end = self.today + datetime.timedelta(days=end_offset_days)
                start = end - datetime.timedelta(days=180)
                self._ensure_role(user, role, start, end)
            users[key] = user
        return users

    def _ensure_user(self, local_part, name, chapter, password, badge_offset):
        email = f"{local_part}@{EMAIL_DOMAIN}"
        first_name, _, last_name = name.partition(" ")
        user, _created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "name": name,
                "chapter": chapter,
                "badge_number": 970_000_000 + badge_offset,
                "graduation_year": self.today.year + 2,
            },
        )
        if user.chapter_id != chapter.pk:
            user.chapter = chapter
            user.save(update_fields=["chapter"])
        user.set_password(password)
        user.save(update_fields=["password"])
        self._ensure_active_status(user)
        self._ensure_rmp(user)
        return user

    def _ensure_active_status(self, user):
        if UserStatusChange.objects.filter(user=user, status="active", end__gte=self.today).exists():
            return
        UserStatusChange.objects.create(
            user=user, status="active", start=self.today - datetime.timedelta(days=180), end=datetime.date(2100, 1, 1)
        )

    def _ensure_rmp(self, user):
        if RiskManagement.user_signed_this_semester(user):
            return
        boolean_fields = [
            "alcohol",
            "hosting",
            "monitoring",
            "member",
            "officer",
            "abusive",
            "hazing",
            "substances",
            "high_risk",
            "transportation",
            "property_management",
            "guns",
            "trademark",
            "social",
            "indemnification",
            "agreement",
            "electronic_agreement",
            "terms_agreement",
        ]
        RiskManagement.objects.create(
            user=user,
            role="regent",
            submission=None,
            date=self.today,
            typed_name=user.name,
            **{field: True for field in boolean_fields},
        )

    def _ensure_role(self, user, role, start, end):
        """Creates the role change ONLY the first time, then leaves its
        ``start``/``end`` untouched on every later run.

        ``generate_obligations`` keys each ``ReportObligation`` by
        ``(chapter, position_key, term_start, term_end)`` -- i.e. by this
        role change's own dates. Re-deriving ``start``/``end`` from ``TODAY``
        on every run (the previous behavior) shifted those dates forward
        each time the command was run on a new day, so re-running without
        ``--flush`` after even one day had passed silently created a SECOND
        ``ReportObligation`` for the same user/position instead of reusing
        the first one -- ``_submit``'s ``.get(position_key=...)`` then raised
        ``MultipleObjectsReturned``. Keeping the first run's dates makes the
        whole command idempotent regardless of how much time has passed
        since the last run; use ``--flush`` to get a fresh "as of today"
        dataset instead.
        """
        existing = UserRoleChange.objects.filter(user=user, role=role).first()
        if existing is None:
            UserRoleChange.objects.create(user=user, role=role, start=start, end=end)
        else:
            start, end = existing.start, existing.end
        user.refresh_from_db()
        is_current = start <= self.today <= end
        current = list(user.current_roles or [])
        changed = False
        if is_current and role not in current:
            current.append(role)
            changed = True
        elif not is_current and role in current:
            current.remove(role)
            changed = True
        if changed:
            user.current_roles = current
            user.save(update_fields=["current_roles"])
        group_name = "natoff" if role in NAT_OFFICERS else "officer"
        Group.objects.get_or_create(name=group_name)[0].user_set.add(user)

    # ---------------------------------------------------------------- reports
    def _seed_reports(self, users):
        reports = {}
        reports["pred1"] = self._submit(users["pred1"], "treasurer", rich=True)
        reports["pred2"] = self._submit(users["pred2"], "treasurer", rich=False)
        reports["pred3"] = self._submit(users["pred3"], "treasurer", rich=True)
        self._submit(users["council_pred"], "grand regent", rich=True)
        self._submit(users["committee_pred"], "events chair", rich=True)
        self._submit(users["outside_region_pred"], "regent", rich=True)
        self._submit(users["national_pred"], "national director", rich=True)
        self._submit(users["ccd_pred"], "candidate chapter director", rich=True)
        # missed_pred and vacant_pred are deliberately NEVER submitted -- their
        # obligations stay "missed"/become "na_vacant" (handled in handle()).
        return reports

    def _submit(self, user, position_key, rich):
        obligation = user.transition_report_obligations.get(position_key=position_key)
        report = services.get_or_create_report(obligation)
        answers_data = [(prompt, _answer_for(prompt, rich)) for prompt in report.template.prompts.all()]
        return services.submit_report(report, answers_data)

    def _seed_attachment(self, report):
        if report.attachments.exists():
            return
        content = ContentFile(b"category,amount\nvenue,500\ncatering,300\nsupplies,75\n", name="budget.csv")
        ReportAttachment.objects.create(
            report=report, file=content, description="Sample term budget (QA seed data)", uploaded_by=report.author
        )

    # ------------------------------------------------------------------ report
    def _report(self, users, password):
        self.stdout.write(self.style.SUCCESS("\nTransition Reports QA seed complete."))
        self.stdout.write(f"Password for every account below: {password}\n")
        self.stdout.write("Log in as each to exercise the matching TRWI-6 access role:")
        rows = [
            (users["treasurer"].username, "Successor officer (treasurer, Chapter Alpha)"),
            (users["regent"].username, "Regent (Chapter Alpha, all positions)"),
            (users["early"].username, "Scribe, Chapter Alpha, report not assigned yet (use Start report)"),
            (users["rd"].username, "Regional Director ([QA] Transitions Region: Alpha/Beta/Gamma)"),
            (users["ccd"].username, "Candidate Chapter Director (own position only, any chapter)"),
            (users["natoff"].username, "National Officer (own position only, any chapter)"),
            (users["council"].username, "Council / Grand Officer (national-wide, sees everything)"),
            (users["outsider"].username, "Unrelated member (must see nothing)"),
        ]
        for username, description in rows:
            self.stdout.write(f"  {username:<55} {description}")
        self.stdout.write("\nSee docs/specs/transition-reports-qa.md for the full walkthrough.")
