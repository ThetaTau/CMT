"""Seed the database with realistic Awards demo data for end-to-end QA (AWI-14).

Generates a coherent, cross-referenced dataset that exercises every AWI-1..13
feature: the award catalog across all levels + grant methods, cycles of each
period type, eligibility rules, grants of every source / recipient kind
(including backdated, revoked, and a group grant), nominations in pending /
approved / rejected states, certificates, officer badges, and a config-driven
approver so the reviewer queue is populated.

Guardrails
----------
* Demo data is tagged with a ``[DEMO] `` prefix (award / cycle names, demo
  member / chapter / region records) so it is easy to spot and clean up.
* ``--flush-awards`` deletes ONLY the awards-domain demo rows (never members,
  chapters, or regions, and never non-demo awards data).
* Catalog objects are ``get_or_create``d and grants are existence-checked, so
  re-running without ``--flush-awards`` never duplicates.
* Refuses to run outside ``DEBUG`` unless ``--force`` is passed.

Usage::

    docker exec thetataucmt_local_django python manage.py seed_awards_demo --force
    docker exec thetataucmt_local_django python manage.py seed_awards_demo \\
        --flush-awards --seed 42 --scale medium --force
"""

import datetime
import random
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone
from faker import Faker

from thetatauCMT.awards.certificates import store_uploaded_artifact
from thetatauCMT.awards.flows import AwardNominationFlow
from thetatauCMT.awards.importer import import_grant
from thetatauCMT.awards.models import (
    AwardCycle,
    AwardGrant,
    AwardImportMatchQueueItem,
    AwardNominationProcess,
    AwardType,
    EligibilityRule,
    GrantArtifact,
    OfficerBadge,
)
from thetatauCMT.awards.services import _recipient_kwargs, direct_grant, grant_award, revoke_grant
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.configs.models import Config
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import User, UserStatusChange

DEMO = "[DEMO] "
DEMO_EMAIL_DOMAIN = "demo.thetatau.local"
APPROVER_USERNAME = f"demo-awards-approver@{DEMO_EMAIL_DOMAIN}"

SCALE_PRESETS = {
    "small": {"members": 6, "member_grants": 5, "group_size": 3, "import_grants": 2, "nominations": 3},
    "medium": {"members": 16, "member_grants": 12, "group_size": 5, "import_grants": 4, "nominations": 6},
    "large": {"members": 40, "member_grants": 26, "group_size": 8, "import_grants": 8, "nominations": 12},
}

# name, level, grant_method, recurrence, single_winner, allow_multiple_winners,
# allow_multiple_nominations, is_active, auto_generate_certificate, nominator_scope
AWARD_TYPE_SPECS = [
    ("Distinguished Service Award", "member", "nomination_workflow", "recurring", False, True, True, True, True, ["officer", "national"]),
    ("Outstanding Alumni Award", "alumni", "nomination_workflow", "recurring", False, True, True, True, False, ["officer", "national"]),
    ("Active of the Year", "active", "direct", "recurring", False, True, False, True, False, []),
    ("PNM Scholarship", "pnm", "direct", "one_time", False, True, True, True, False, ["officer"]),
    ("Chapter of the Year", "chapter", "nomination_workflow", "recurring", True, False, False, True, False, ["national"]),
    ("Region of the Year", "region", "direct", "recurring", True, False, False, True, False, []),
    ("National Merit Award", "national", "nomination_workflow", "recurring", False, True, False, True, True, ["national"]),
    ("Legacy Founders Medal (Retired)", "member", "direct", "one_time", True, False, False, False, False, []),
]


class Command(BaseCommand):
    help = "Seed the DB with realistic Awards demo data for end-to-end QA (AWI-14)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-awards",
            action="store_true",
            help="Delete existing [DEMO] awards data (only) before seeding.",
        )
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output.")
        parser.add_argument(
            "--scale",
            choices=sorted(SCALE_PRESETS),
            default="small",
            help="Volume of generated data (default: small).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required to run when settings.DEBUG is off (i.e. production-like).",
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError(
                "Refusing to run outside DEBUG without --force "
                "(this seeds demo data and must not run automatically in production)."
            )
        if opts["seed"] is not None:
            random.seed(opts["seed"])
            self._faker = Faker()
            self._faker.seed_instance(opts["seed"])
        else:
            self._faker = Faker()
        scale = SCALE_PRESETS[opts["scale"]]
        self.counts = defaultdict(int)
        self._year = timezone.now().year

        with transaction.atomic():
            if opts["flush_awards"]:
                self._flush()
            regions = self._ensure_regions()
            chapters = self._ensure_chapters(regions)
            members = self._ensure_members(chapters, scale["members"])
            officer = self._ensure_officer(chapters[0])
            Config.objects.update_or_create(
                key="AwardApprover",
                defaults={"value": officer.email, "description": f"{DEMO}award nomination approver"},
            )
            awards = self._ensure_award_types()
            cycles = self._ensure_cycles()
            self._ensure_eligibility(awards, chapters, regions)
            self._ensure_officer_badges(officer)
            self._seed_grants(awards, cycles, members, chapters, regions, officer, scale)
            self._seed_nominations(awards, cycles, members, officer, scale)
            self._seed_artifacts(officer)

        self.stdout.write(self.style.SUCCESS("Awards demo data seeded:"))
        for key, value in sorted(self.counts.items()):
            self.stdout.write(f"  {key}: {value}")

    # ------------------------------------------------------------------
    # Flush (demo awards data only)
    # ------------------------------------------------------------------
    def _flush(self):
        from viewflow.models import Task

        demo_types = AwardType.objects.filter(name__startswith=DEMO)
        demo_cycles = AwardCycle.objects.filter(name__startswith=DEMO)
        AwardGrant.objects.filter(models.Q(award_type__in=demo_types) | models.Q(cycle__in=demo_cycles)).delete()
        AwardImportMatchQueueItem.objects.filter(award_type__in=demo_types).delete()
        demo_nom_ids = list(AwardNominationProcess.objects.filter(award_type__in=demo_types).values_list("pk", flat=True))
        if demo_nom_ids:
            Task.objects.filter(process_id__in=demo_nom_ids).delete()
            AwardNominationProcess.objects.filter(pk__in=demo_nom_ids).delete()
        EligibilityRule.objects.filter(award_type__in=demo_types).delete()
        demo_cycles.delete()
        demo_types.delete()
        OfficerBadge.objects.filter(short_label__startswith=DEMO).delete()

    # ------------------------------------------------------------------
    # Supporting data (reuse existing; create minimal demo records if empty)
    # ------------------------------------------------------------------
    def _ensure_regions(self):
        regions = list(Region.objects.all()[:3])
        if regions:
            return regions
        created = []
        for i in range(2):
            created.append(Region.objects.create(name=f"{DEMO}Region {i + 1}", email=f"demo-region-{i}@{DEMO_EMAIL_DOMAIN}"))
            self.counts["regions_created"] += 1
        return created

    def _ensure_chapters(self, regions):
        chapters = list(Chapter.objects.filter(active=True)[:5])
        if chapters:
            return chapters
        created = []
        for i in range(2):
            created.append(
                Chapter.objects.create(
                    name=f"{DEMO}Chapter {i + 1}",
                    region=regions[i % len(regions)],
                    greek=f"D{i + 1}",
                    school=f"{DEMO}Demo University {i + 1}",
                    address_contact="Demo Contact",
                    address_phone_number="5555550100",
                )
            )
            self.counts["chapters_created"] += 1
        return created

    def _make_active_status(self, user):
        today = timezone.now().date()
        UserStatusChange.objects.get_or_create(
            user=user,
            status="active",
            defaults={
                "start": today - datetime.timedelta(days=400),
                "end": today + datetime.timedelta(days=400),
            },
        )

    def _make_demo_member(self, chapter, index):
        username = f"demo-awards-member-{index}@{DEMO_EMAIL_DOMAIN}"
        existing = User.objects.filter(username=username).first()
        if existing:
            return existing
        user = User(
            username=username,
            email=username,
            name=f"{DEMO}{self._faker.name()} {index}",
            first_name=self._faker.first_name(),
            last_name=self._faker.last_name(),
            chapter=chapter,
            badge_number=990000 + index,
            current_status="active",
        )
        user.set_password("demo-not-a-real-login")
        user.save()
        self._make_active_status(user)
        self.counts["members_created"] += 1
        return user

    def _ensure_members(self, chapters, needed):
        members = list(User.objects.exclude(username=APPROVER_USERNAME).order_by("pk")[:needed])
        index = 0
        while len(members) < needed:
            members.append(self._make_demo_member(chapters[index % len(chapters)], index))
            index += 1
        return members

    def _ensure_officer(self, chapter):
        officer = User.objects.filter(username=APPROVER_USERNAME).first()
        if officer is None:
            officer = User(
                username=APPROVER_USERNAME,
                email=APPROVER_USERNAME,
                name=f"{DEMO}Award Approver",
                first_name="Award",
                last_name="Approver",
                chapter=chapter,
                badge_number=999999,
                current_status="active",
            )
            officer.set_password("demo-not-a-real-login")
            officer.save()
            self._make_active_status(officer)
            self.counts["members_created"] += 1
        officer.groups.add(Group.objects.get_or_create(name="natoff")[0])
        return officer

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    def _ensure_award_types(self):
        awards = {}
        for spec in AWARD_TYPE_SPECS:
            (name, level, method, recur, single, multi_win, multi_nom, active, autocert, scopes) = spec
            obj, created = AwardType.objects.get_or_create(
                name=f"{DEMO}{name}",
                defaults=dict(
                    description=f"{DEMO}{name} — demo award for QA.",
                    level=level,
                    grant_method=method,
                    recurrence=recur,
                    single_winner=single,
                    allow_multiple_winners=multi_win,
                    allow_multiple_nominations=multi_nom,
                    is_active=active,
                    auto_generate_certificate=autocert,
                    nominator_scope=scopes,
                ),
            )
            awards[name] = obj
            if created:
                self.counts["award_types"] += 1
        return awards

    def _ensure_cycles(self):
        from thetatauCMT.events.models import Event

        event = Event.objects.first()
        specs = [
            ("2019", "year", datetime.date(2019, 1, 1), datetime.date(2019, 12, 31)),
            ("2023", "year", datetime.date(2023, 1, 1), datetime.date(2023, 12, 31)),
            (str(self._year), "year", datetime.date(self._year, 1, 1), datetime.date(self._year, 12, 31)),
            (f"Fall {self._year}", "term", datetime.date(self._year, 8, 1), datetime.date(self._year, 12, 15)),
            (f"{self._year} Convention", "event", None, None),
        ]
        cycles = {}
        for name, ptype, start, end in specs:
            defaults = dict(period_type=ptype, start_date=start, end_date=end)
            if ptype == "event" and event is not None:
                defaults["event"] = event
            obj, created = AwardCycle.objects.get_or_create(name=f"{DEMO}{name}", defaults=defaults)
            cycles[name] = obj
            if created:
                self.counts["cycles"] += 1
        return cycles

    def _ensure_eligibility(self, awards, chapters, regions):
        def rule(award, rule_type, *, member_status="", hook_key="", chapters_m2m=None, regions_m2m=None):
            obj, created = EligibilityRule.objects.get_or_create(
                award_type=award,
                rule_type=rule_type,
                member_status=member_status,
                hook_key=hook_key,
            )
            if chapters_m2m:
                obj.chapters.set(chapters_m2m)
            if regions_m2m:
                obj.regions.set(regions_m2m)
            if created:
                self.counts["eligibility_rules"] += 1

        rule(awards["Distinguished Service Award"], "member_status", member_status="active")
        rule(awards["Outstanding Alumni Award"], "member_status", member_status="alumni")
        rule(awards["PNM Scholarship"], "member_status", member_status="pnm")
        rule(awards["Chapter of the Year"], "chapter_scope", chapters_m2m=chapters[:2])
        rule(awards["Region of the Year"], "region_scope", regions_m2m=regions[:1])
        rule(awards["National Merit Award"], "custom_hook", hook_key="demo_active_hook")

    def _ensure_officer_badges(self, officer):
        specs = [
            ("grand regent", "GR", "fa-solid fa-crown"),
            ("grand scribe", "GS", "fa-solid fa-feather"),
        ]
        for role, label, icon in specs:
            _obj, created = OfficerBadge.objects.get_or_create(
                role=role,
                defaults={"short_label": f"{DEMO}{label}", "icon_class": icon, "is_active": True},
            )
            if created:
                self.counts["officer_badges"] += 1
        # Give the demo approver a national-officer role so inline name icons show.
        if "grand regent" not in (officer.current_roles or []):
            officer.current_roles = list(officer.current_roles or []) + ["grand regent"]
            officer.save(update_fields=["current_roles"])

    # ------------------------------------------------------------------
    # Grants
    # ------------------------------------------------------------------
    def _grant_once(self, award, cycle, recipient, granted_by, *, source, effective_date=None, reason=""):
        kwargs = _recipient_kwargs(recipient)
        if AwardGrant.objects.filter(award_type=award, cycle=cycle, **kwargs).exists():
            return None
        grant = grant_award(
            award, cycle, recipient, granted_by, effective_date=effective_date, reason=reason, source=source
        )
        self.counts[f"grants_{source}"] += 1
        return grant

    def _seed_grants(self, awards, cycles, members, chapters, regions, officer, scale):
        active_award = awards["Active of the Year"]
        service_award = awards["Distinguished Service Award"]
        chapter_award = awards["Chapter of the Year"]
        region_award = awards["Region of the Year"]
        pnm_award = awards["PNM Scholarship"]
        c2019, c2023, ccurrent, cterm = cycles["2019"], cycles["2023"], cycles[str(self._year)], cycles[f"Fall {self._year}"]

        # Direct-source member grants spread across two cycles + chapters/regions.
        for i in range(scale["member_grants"]):
            recipient = members[i % len(members)]
            cycle = ccurrent if i % 2 else c2023
            self._grant_once(active_award, cycle, recipient, officer, source="direct")

        # Exercise the real direct-grant service path (AWI-5), eligibility + winner rules.
        try:
            kwargs = _recipient_kwargs(members[0])
            if not AwardGrant.objects.filter(award_type=active_award, cycle=cterm, **kwargs).exists():
                direct_grant(active_award, cterm, members[0], officer, reason=f"{DEMO}direct-grant service")
                self.counts["grants_direct_service"] += 1
        except Exception:
            self._grant_once(active_award, cterm, members[0], officer, source="direct")

        # Backdated grant (historical effective_date).
        self._grant_once(
            service_award, c2019, members[0], officer, source="direct",
            effective_date=datetime.date(2019, 5, 1), reason=f"{DEMO}backdated historical grant",
        )
        # Revoked grant.
        revoked = self._grant_once(service_award, c2019, members[1 % len(members)], officer, source="direct")
        if revoked is not None:
            revoke_grant(revoked, officer, reason=f"{DEMO}revoked for QA")
            self.counts["grants_revoked"] += 1

        # Chapter- and region-recipient grants.
        self._grant_once(chapter_award, ccurrent, chapters[0], officer, source="nomination")
        self._grant_once(region_award, ccurrent, regions[0], officer, source="direct")

        # Group grant -> one individual grant per member.
        for member in members[: scale["group_size"]]:
            self._grant_once(pnm_award, ccurrent, member, officer, source="direct")

        # Import-source grants (backdated historical import).
        for i in range(scale["import_grants"]):
            recipient = members[i % len(members)]
            _grant, created = import_grant(
                service_award, c2023, recipient, officer, effective_date=datetime.date(2023, 6, 1)
            )
            if created:
                self.counts["grants_import"] += 1

    # ------------------------------------------------------------------
    # Nominations (viewflow) — pending / approved / rejected
    # ------------------------------------------------------------------
    def _start_nomination(self, award_type, cycle, recipient, nominator):
        activation = AwardNominationFlow.start.activation_class()
        activation.initialize(AwardNominationFlow.start, None)
        process = activation.process
        process.award_type = award_type
        process.cycle = cycle
        process.recipient_member = recipient
        process.nominator = nominator
        process.justification = f"{DEMO}Nominated for outstanding contributions."
        activation.prepare()
        activation.done()
        if getattr(activation, "lock", None):
            activation.lock.__exit__(None, None, None)
        process.refresh_from_db()
        return process

    def _complete_review(self, process, approver, result, reject_reason=""):
        from viewflow.activation import STATUS
        from viewflow.models import Task

        task = Task.objects.filter(
            process=process,
            flow_task=AwardNominationFlow.review,
            status__in=[STATUS.NEW, STATUS.ASSIGNED],
        ).first()
        if task is None:
            return
        process.result = result
        process.reject_reason = reject_reason
        process.reviewed_by = approver
        process.reviewed_at = timezone.now()
        process.review_notes = f"{DEMO}seeded review decision"
        process.save()
        activation = task.activate()
        if task.status == STATUS.NEW:
            activation.assign(approver)
        activation.prepare()
        activation.done()
        process.refresh_from_db()

    def _seed_nominations(self, awards, cycles, members, officer, scale):
        existing = AwardNominationProcess.objects.filter(award_type__name__startswith=DEMO).count()
        to_create = max(0, scale["nominations"] - existing)
        if to_create <= 0:
            return
        ccurrent = cycles[str(self._year)]
        pending_award = awards["National Merit Award"]
        approved_award = awards["Outstanding Alumni Award"]
        rejected_award = awards["Distinguished Service Award"]
        for i in range(to_create):
            member = members[i % len(members)]
            bucket = i % 3
            if bucket == 0:
                self._start_nomination(pending_award, ccurrent, member, officer)
                self.counts["nominations_pending"] += 1
            elif bucket == 1:
                process = self._start_nomination(approved_award, ccurrent, member, officer)
                self._complete_review(process, officer, AwardNominationProcess.Result.APPROVED)
                self.counts["nominations_approved"] += 1
            else:
                process = self._start_nomination(rejected_award, ccurrent, member, officer)
                self._complete_review(
                    process, officer, AwardNominationProcess.Result.REJECTED, reject_reason=f"{DEMO}not this cycle"
                )
                self.counts["nominations_rejected"] += 1

    # ------------------------------------------------------------------
    # Certificates
    # ------------------------------------------------------------------
    def _seed_artifacts(self, officer):
        demo_grants = AwardGrant.objects.filter(award_type__name__startswith=DEMO)
        generated_exists = GrantArtifact.objects.filter(
            artifact_type=GrantArtifact.ArtifactType.GENERATED, grant__in=demo_grants
        ).exists()
        uploaded_exists = GrantArtifact.objects.filter(
            artifact_type=GrantArtifact.ArtifactType.UPLOADED, grant__in=demo_grants
        ).exists()
        grants = list(demo_grants.filter(status=AwardGrant.Status.ACTIVE).order_by("pk"))
        if not generated_exists:
            for grant in grants:
                if grant.artifacts.exists():
                    continue
                GrantArtifact.objects.create(
                    grant=grant,
                    artifact_type=GrantArtifact.ArtifactType.GENERATED,
                    file=ContentFile(b"%PDF-1.4 demo generated certificate", name="certificate.pdf"),
                    generated_at=timezone.now(),
                    created_by=officer,
                )
                self.counts["artifacts_generated"] += 1
                break
        if not uploaded_exists:
            for grant in grants:
                if grant.artifacts.exists():
                    continue
                store_uploaded_artifact(
                    grant, ContentFile(b"%PDF-1.4 demo uploaded letter", name="letter.pdf"), officer
                )
                self.counts["artifacts_uploaded"] += 1
                break
