"""TRWI-2: seed the Default Prompt Set (see .github/copilot-memory/sessions/transitions-app.md).

Idempotent -- safe to re-run. Upserts by (position_type, position_key) for
templates and (template, prompt_key) for prompts, so re-running never
duplicates rows. Existing ``version`` values are left untouched -- bumping a
version after an intentional content change is an admin action, not this
command's job.

    docker exec thetataucmt_local_django python manage.py seed_transition_prompt_set [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.transitions.models import ReportTemplate, TemplatePrompt

# Master registry of every seeded prompt's stable content. Per-template
# is_required/min_chars/max_chars are declared where each template lists its
# prompts below, since the SAME prompt_key can carry different requirements on
# different templates (e.g. systems_access is required for CHAPTER_OFFICER but
# optional for COMMITTEE_CHAIR).
PROMPTS = {
    "successes": {
        "label": "What went well this term that your successor should keep doing?",
        "field_type": "long_text",
        "tag": "success",
        "help_text": (
            'Be specific. "Recruitment went well" doesn\'t help \u2014 "moving the info night to the second week '
            'of classes doubled attendance" does. Include what made it work so it can be repeated.'
        ),
    },
    "failures": {
        "label": "What didn't go well, and what would you do differently?",
        "field_type": "long_text",
        "tag": "failure",
        "help_text": (
            "This is the most valuable box on the page and nobody will hold it against you. Every officer hits "
            "problems; the ones who write them down save the next person a semester. Include what you tried, "
            "what happened, and what you'd try instead."
        ),
    },
    "campus_contacts": {
        "label": "Key campus contacts \u2014 who they are, what they help with, how to reach them",
        "field_type": "contact",
        "tag": "contacts",
        "help_text": (
            "Name, role/office, email or phone, and \u2014 most importantly \u2014 what they actually help with. "
            "Include the person who really gets things done, not just the person whose title suggests they should."
        ),
    },
    "experts": {
        "label": "Who else should your successor know? (alumni, advisors, vendors, other chapters)",
        "field_type": "contact",
        "tag": "expertise",
        "help_text": "Alumni who've held this role, advisors, reliable vendors, counterparts at other chapters. Note what each is good for.",
    },
    "key_dates": {
        "label": "Recurring dates and deadlines, and how far ahead to start each",
        "field_type": "list",
        "tag": "calendar",
        "help_text": (
            'One per line. Include the deadline AND the lead time \u2014 "IFC dues due Oct 1, start collecting '
            'Sept 1" is far more useful than "IFC dues, Oct 1."'
        ),
    },
    "systems_access": {
        "label": "Tools, accounts, files, and passwords-management \u2014 where everything lives",
        "field_type": "long_text",
        "tag": "systems",
        "help_text": (
            "Where do documents live? Which accounts exist and who holds credentials? What's on a personal device "
            "or personal email that needs to move? Do not paste actual passwords here \u2014 say where they're stored."
        ),
    },
    "unfinished": {
        "label": "What's unfinished or in-flight that lands on your successor's desk on day one?",
        "field_type": "long_text",
        "tag": "continuity",
        "help_text": "Open items, pending decisions, ongoing conversations, anything half-built. Include current status and who else is involved.",
    },
    "first_30_days": {
        "label": "If your successor does only three things in their first 30 days, what should they be?",
        "field_type": "long_text",
        "tag": "advice",
        "help_text": "The highest-impact actions. Think about what you wish you'd done in your first month instead of what you actually did.",
    },
    "pitfalls": {
        "label": "What surprised you about this role that nobody warned you about?",
        "field_type": "long_text",
        "tag": "risk",
        "help_text": "The unwritten rules, the thing that always takes longer than expected, the meeting that actually matters.",
    },
    "anything_else": {
        "label": "Anything else your successor should know",
        "field_type": "long_text",
        "tag": "advice",
        "help_text": "Anything that doesn't fit above.",
    },
    # -- COMMITTEE_CHAIR-only prompts. Help text invented (no exact wording was
    # specified) -- expect the pre-launch prompt-set review (F16) to revise it.
    "committee_roster": {
        "label": "Who served on your committee, and who should be asked back?",
        "field_type": "long_text",
        "tag": "continuity",
        "help_text": (
            "List members by name and what they handled. Flag who was reliable and should be recruited again, and "
            "who struggled so your successor knows where they might need more support or a different role."
        ),
    },
    "program_logistics": {
        "label": "Event/program logistics \u2014 venues, vendors, timelines, what to book and when",
        "field_type": "long_text",
        "tag": "systems",
        "help_text": (
            "Where things happened, who you booked (with contact info if you have it), and how far ahead you had "
            "to reserve them. Include anything that sold out or fell through last minute so your successor books "
            "it sooner."
        ),
    },
    "budget_actuals": {
        "label": "What did it actually cost vs. what was budgeted? Where were the surprises?",
        "field_type": "long_text",
        "tag": "risk",
        "help_text": (
            "Compare what you planned for to what you actually spent, line by line if you can. Call out anything "
            "that cost more than expected and why, so next year's budget starts closer to reality."
        ),
    },
    "participation": {
        "label": "What drove (or killed) member participation?",
        "field_type": "long_text",
        "tag": "success",
        "help_text": "Think about timing, communication, incentives, or competing events. What got people to show up, and what made them skip it?",
    },
    # -- COUNCIL/NATIONAL_OFFICER-only prompts. Help text invented (no exact
    # wording was specified) -- expect the pre-launch prompt-set review (F16)
    # to revise it.
    "cross_chapter": {
        "label": "Which chapters or regions need particular attention, and why?",
        "field_type": "long_text",
        "tag": "risk",
        "help_text": (
            'Name specific chapters or regions, not just "some chapters." Include what the concern is (officer '
            "turnover, low attendance, finances, communication) and anything already in motion to address it."
        ),
    },
    "external_relations": {
        "label": "External relationships \u2014 vendors, partners, host institutions, associations",
        "field_type": "contact",
        "tag": "contacts",
        "help_text": (
            "Name, organization, and what they help with \u2014 similar to campus contacts, but at the national "
            "level. Note which relationships need active maintenance versus which are dormant but worth keeping."
        ),
    },
    "governance": {
        "label": "Governance items in flight \u2014 policy changes, proposals, pending decisions",
        "field_type": "long_text",
        "tag": "continuity",
        "help_text": (
            "Anything moving through convention, the council, or committee review that isn't finished. Include "
            "current status, who else is involved, and what happens if nobody picks it up."
        ),
    },
    "national_systems": {
        "label": "National-level tools, accounts, files, and where they live",
        "field_type": "long_text",
        "tag": "systems",
        "help_text": (
            "The national-level equivalent of systems access \u2014 shared drives, admin accounts, databases, "
            "vendor portals. Note who else has access and where credentials are stored (don't paste passwords)."
        ),
    },
}


def _prompt(key, is_required, min_chars=None, max_chars=None):
    data = PROMPTS[key]
    return {
        "prompt_key": key,
        "label": data["label"],
        "field_type": data["field_type"],
        "tag": data["tag"],
        "help_text": data["help_text"],
        "is_required": is_required,
        "min_chars": min_chars,
        "max_chars": max_chars,
    }


# Ordering follows the design principle: successes -> failures -> reference
# material -> forward-looking. See transitions-app.md "Default Prompt Set".
TEMPLATES = [
    {
        "position_type": "CHAPTER_OFFICER",
        "name": "Chapter Officer Transition Report",
        "description": (
            "Help your successor start strong. This report is shared with whoever takes over this position next, "
            "and stays visible to every future holder after that."
        ),
        "prompts": [
            _prompt("successes", True, 150, 2000),
            _prompt("failures", True, 150, 2000),
            _prompt("campus_contacts", True, 80, 2500),
            _prompt("experts", False, None, 2000),
            _prompt("key_dates", True, 80, 2000),
            _prompt("systems_access", True, 100, 2000),
            _prompt("unfinished", True, 100, 2000),
            _prompt("first_30_days", True, 120, 1500),
            _prompt("pitfalls", False, None, 1500),
            _prompt("anything_else", False, None, 2000),
        ],
    },
    {
        "position_type": "COMMITTEE_CHAIR",
        "name": "Committee Chair Transition Report",
        "description": (
            "Help whoever chairs this committee next. This report is shared with your successor and stays visible "
            "to every future chair after that."
        ),
        "prompts": [
            _prompt("successes", True, 150, 2000),
            _prompt("failures", True, 150, 2000),
            _prompt("participation", False, None, 1500),
            _prompt("campus_contacts", True, 80, 2500),
            _prompt("key_dates", True, 80, 2000),
            _prompt("committee_roster", True, 80, 1500),
            _prompt("program_logistics", True, 120, 2500),
            _prompt("systems_access", False, 100, 2000),
            _prompt("budget_actuals", False, None, 1500),
            _prompt("unfinished", True, 100, 2000),
            _prompt("first_30_days", True, 120, 1500),
            _prompt("anything_else", False, None, 2000),
        ],
    },
    {
        "position_type": "COUNCIL",
        "name": "Council Transition Report",
        "description": (
            "Help your successor on National Council. This report is shared with the next person to hold this "
            "seat and every future holder after that."
        ),
        "prompts": [
            _prompt("successes", True, 150, 2000),
            _prompt("failures", True, 150, 2000),
            _prompt("experts", False, None, 2000),
            _prompt("key_dates", True, 80, 2000),
            _prompt("cross_chapter", False, None, 2000),
            _prompt("external_relations", False, None, 2000),
            _prompt("governance", False, None, 2000),
            _prompt("national_systems", False, None, 2000),
            _prompt("unfinished", True, 100, 2000),
            _prompt("first_30_days", True, 120, 1500),
            _prompt("anything_else", False, None, 2000),
        ],
    },
    {
        "position_type": "NATIONAL_OFFICER",
        "name": "National Officer Transition Report",
        "description": (
            "Help your successor in this national officer role. This report is shared with the next person to "
            "hold this position and every future holder after that."
        ),
        "prompts": [
            _prompt("successes", True, 150, 2000),
            _prompt("failures", True, 150, 2000),
            _prompt("experts", False, None, 2000),
            _prompt("key_dates", True, 80, 2000),
            _prompt("cross_chapter", False, None, 2000),
            _prompt("external_relations", False, None, 2000),
            _prompt("governance", False, None, 2000),
            _prompt("national_systems", False, None, 2000),
            _prompt("unfinished", True, 100, 2000),
            _prompt("first_30_days", True, 120, 1500),
            _prompt("anything_else", False, None, 2000),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the Default Prompt Set (TRWI-2) -- idempotent, safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        templates_created = templates_updated = 0
        prompts_created = prompts_updated = 0

        with transaction.atomic():
            for template_data in TEMPLATES:
                template, created = ReportTemplate.objects.update_or_create(
                    position_type=template_data["position_type"],
                    position_key="",
                    defaults={
                        "name": template_data["name"],
                        "description": template_data["description"],
                        "is_active": True,
                    },
                )
                templates_created += created
                templates_updated += not created

                for order, prompt_data in enumerate(template_data["prompts"], start=1):
                    prompt_key = prompt_data["prompt_key"]
                    fields = {k: v for k, v in prompt_data.items() if k != "prompt_key"}
                    fields["order"] = order
                    _, prompt_created = TemplatePrompt.objects.update_or_create(
                        template=template,
                        prompt_key=prompt_key,
                        defaults=fields,
                    )
                    prompts_created += prompt_created
                    prompts_updated += not prompt_created

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Templates: {templates_created} created, {templates_updated} updated. "
            f"Prompts: {prompts_created} created, {prompts_updated} updated."
        )
