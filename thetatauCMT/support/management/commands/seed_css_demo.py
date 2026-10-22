"""Seed a Chapter Support Specialist to try the CSS pages locally (CSSWI-9).

Creates, or reuses, the inactive Central Office home chapter and one CSS staff account with
three current assignments and one ended one. It never deletes anything, so it is safe to
re-run. Locally ``DEBUG`` is on, so two-factor setup is not required for the demo account.

    docker exec thetataucmt_local_django python manage.py seed_css_demo
"""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import CSS_ROLE
from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.support.services import (
    assign_chapter,
    clear_css_state,
    create_css_account,
    css_home_chapter_slug,
    grant_css_role,
    holds_css_role,
)
from thetatauCMT.users.models import User

DEMO_EMAIL = "css.demo@css-seed.thetatau.local"
DEMO_PASSWORD = "css-demo-password"
NOTE = "Demo assignment from seed_css_demo."


class Command(BaseCommand):
    help = "Seed a demo Chapter Support Specialist with assigned chapters (local QA only)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Required to run when settings.DEBUG is off.")

    def handle(self, *args, **options):
        ensure_seeding_allowed(options["force"])
        today = timezone.localdate()
        with transaction.atomic():
            home = self._home_chapter()
            css = self._css(today)
            current, ended = self._assign(css, home, today)
        self.stdout.write(self.style.SUCCESS(f"Chapter Support Specialist: {css} <{css.email}>"))
        self.stdout.write(f"  Home chapter: {home} (inactive)")
        self.stdout.write(f"  Current chapters: {', '.join(str(chapter) for chapter in current)}")
        if ended:
            self.stdout.write(f"  Ended chapter: {', '.join(str(chapter) for chapter in ended)}")
        self.stdout.write(f"  Sign in as {css.email} with the password {DEMO_PASSWORD!r}.")

    def _home_chapter(self):
        slug = css_home_chapter_slug()
        chapter = Chapter.objects.filter(slug=slug).first()
        if chapter is None:
            region = Region.objects.order_by("pk").first()
            if region is None:
                raise CommandError("There is no region to put the Central Office chapter in. Seed regions first.")
            chapter = Chapter.objects.create(
                name="Central Office",
                greek="CO",
                region=region,
                active=False,
                address_contact="Central Office",
                address_phone_number="",
            )
            self.stdout.write(f"Created the inactive {chapter} chapter (slug {chapter.slug}).")
        if chapter.active:
            raise CommandError(f"The CSS home chapter {chapter} is active; it must be inactive.")
        return chapter

    def _css(self, today):
        year_ago = today - datetime.timedelta(days=365)
        user = User.objects.filter(email__iexact=DEMO_EMAIL).first()
        if user is None:
            user, _ = create_css_account(first_name="Casey", last_name="Specialist", email=DEMO_EMAIL)
            user.set_password(DEMO_PASSWORD)
            user.save()
            # The ended demo assignment started months ago, so the role must have too.
            user.roles.filter(role=CSS_ROLE).update(start=year_ago)
        elif not holds_css_role(user):
            # Removed since the last run: bring the demo account back.
            user.is_active = True
            user.save(update_fields=["is_active"])
            grant_css_role(user, start=year_ago)
        clear_css_state(user)
        return User.objects.get(pk=user.pk)

    def _assign(self, css, home, today):
        chapters = list(Chapter.objects.filter(active=True).exclude(pk=home.pk).order_by("name")[:4])
        if len(chapters) < 2:
            raise CommandError("At least two active chapters are needed to assign.")
        current, ended = chapters[:3], chapters[3:]
        for chapter in current:
            if not css.support_assignments.current().filter(chapter=chapter).exists():
                # A chapter covered before (the demo was removed since) restarts today.
                covered_before = css.support_assignments.filter(chapter=chapter).exists()
                start = today if covered_before else today - datetime.timedelta(days=60)
                assign_chapter(css, chapter, start=start, notes=NOTE)
        for chapter in ended:
            if not css.support_assignments.filter(chapter=chapter).exists():
                assign_chapter(
                    css,
                    chapter,
                    start=today - datetime.timedelta(days=120),
                    end=today - datetime.timedelta(days=30),
                    notes=NOTE,
                )
        return current, ended
