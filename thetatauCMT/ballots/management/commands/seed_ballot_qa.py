"""
Provision the accounts and an open ballot needed to QA the officer vote flow.

Creates a Regent and a Scribe in the same chapter (so the one-vote-per-chapter
rule and the shared confirmation email can both be exercised) plus a Grand
Regent and a Grand Scribe (so the tallies and the vote removal can be), then
opens a ballot they can all vote on. Re-running is safe: everything is matched
on a stable username and refreshed.

No password is set or printed. Set one yourself, interactively, with:

    docker exec -it thetataucmt_local_django python manage.py changepassword <username>

    To run
        docker exec thetataucmt_local_django python manage.py seed_ballot_qa
"""

import datetime

from django.contrib.auth.models import Group
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.ballots.models import Ballot
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.forms.models import RiskManagement
from thetatauCMT.users.models import User, UserRoleChange

QA_BALLOT_NAME = "[QA] Officer Vote Walkthrough"

# username -> (display name, role, extra group)
QA_ACCOUNTS = {
    "qa.regent@thetatau.local": ("QA Regent", "regent", "officer"),
    "qa.scribe@thetatau.local": ("QA Scribe", "scribe", "officer"),
    "qa.grand.regent@thetatau.local": ("QA Grand Regent", "grand regent", "natoff"),
    "qa.grand.scribe@thetatau.local": ("QA Grand Scribe", "grand scribe", "natoff"),
}

RMP_DEFAULTS = dict(
    submission=None,
    alcohol=True,
    hosting=True,
    monitoring=True,
    member=True,
    officer=True,
    abusive=True,
    hazing=True,
    substances=True,
    high_risk=True,
    transportation=True,
    property_management=True,
    guns=True,
    trademark=True,
    social=True,
    indemnification=True,
    agreement=True,
    electronic_agreement=True,
    terms_agreement=True,
)


class Command(BaseCommand):
    help = "Create QA officer accounts and an open ballot for walking through the vote flow."

    def add_arguments(self, parser):
        parser.add_argument("--chapter", type=str, help="Slug of the chapter to attach the QA officers to.")
        parser.add_argument("--days", type=int, default=14, help="Days until the QA ballot closes. Default 14.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required when DEBUG is off. Without it the command refuses to run.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_seeding_allowed(options["force"])
        chapter = self._chapter(options.get("chapter"))
        users = {username: self._account(username, chapter, *details) for username, details in QA_ACCOUNTS.items()}
        ballot = self._ballot(options["days"])
        self._report(chapter, users, ballot)

    def _chapter(self, slug):
        chapters = Chapter.objects.filter(active=True, candidate_chapter=False)
        chapter = chapters.filter(slug=slug).first() if slug else chapters.order_by("name").first()
        if chapter is None:
            raise SystemExit("No active chartered chapter to attach the QA officers to.")
        # The reminder and receipt emails read these, so give them somewhere to go.
        chapter.email_regent = chapter.email_regent or "qa.regent@thetatau.local"
        chapter.email_scribe = chapter.email_scribe or "qa.scribe@thetatau.local"
        chapter.save()
        return chapter

    def _account(self, username, chapter, name, role, group_name):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults=dict(email=username, name=name, chapter=chapter),
        )
        user.email = username
        user.name = name
        user.chapter = chapter
        user.save()
        user.set_current_status("active")
        # One current term for the role, replacing any left over from a re-run.
        today = timezone.localdate()
        user.roles.filter(role=role).delete()
        UserRoleChange(
            user=user,
            role=role,
            start=today - datetime.timedelta(days=30),
            end=today + datetime.timedelta(days=180),
        ).save()
        group, _ = Group.objects.get_or_create(name=group_name)
        group.user_set.add(user)
        self._sign_rmp(user, role)
        user.refresh_from_db()
        return user

    @staticmethod
    def _sign_rmp(user, role):
        """RMPSignMiddleware bounces anyone who has not signed this semester."""
        if RiskManagement.user_signed_this_semester(user):
            return
        RiskManagement(user=user, role=role, date=timezone.localdate(), typed_name=user.name, **RMP_DEFAULTS).save()

    def _ballot(self, days):
        ballot = Ballot.objects.filter(name=QA_BALLOT_NAME).order_by("-due_date").first()
        due_date = timezone.localdate() + datetime.timedelta(days=days)
        if ballot is None:
            ballot = Ballot(
                sender="Grand Scribe",
                name=QA_BALLOT_NAME,
                type="chapter",
                description=(
                    "QA walkthrough ballot. Vote as the QA Regent or QA Scribe to exercise the "
                    "four-fifths attestation and the confirmation email, then sign in as the QA "
                    "Grand Scribe to see the tallies and remove the submission."
                ),
                due_date=due_date,
                voters=["all_chapters", "grand regent", "grand scribe"],
            )
        else:
            ballot.due_date = due_date
        ballot.save()
        return ballot

    def _report(self, chapter, users, ballot):
        self.stdout.write(self.style.SUCCESS(f"QA chapter: {chapter.name} ({chapter.slug})"))
        self.stdout.write(f"QA ballot:  {ballot.name}, closes {ballot.closes_display}")
        self.stdout.write("")
        self.stdout.write("Accounts (set each password yourself, nothing is stored or printed here):")
        for username, user in users.items():
            self.stdout.write(f"  {user.current_roles[0]:<14} {username}")
        self.stdout.write("")
        self.stdout.write("  docker exec -it thetataucmt_local_django python manage.py changepassword <username>")
        self.stdout.write("")
        self.stdout.write("Walkthrough:")
        self.stdout.write("  1. Sign in as the Regent or Scribe. The ballot badge sits left of the calendar icon.")
        self.stdout.write(f"  2. Vote at /ballots/vote/{ballot.slug}/ and check the attestation and receipt email.")
        self.stdout.write("  3. The other officer should now see the chapter has voted and be unable to vote again.")
        self.stdout.write(f"  4. Sign in as the Grand Scribe and open /ballots/details/{ballot.slug}/ for tallies.")
        self.stdout.write("  5. Use Remove on the submitted row, then confirm the chapter can vote again.")
