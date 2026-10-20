import datetime

import pytest
from django.core.management import call_command

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .. import services
from ..models import ReportObligation, ReportTemplate, TemplatePrompt, TransitionTag

pytestmark = pytest.mark.django_db


def test_seed_creates_four_templates_and_44_prompts():
    call_command("seed_transition_prompt_set")
    assert ReportTemplate.objects.count() == 4
    assert TemplatePrompt.objects.count() == 44


def test_seed_is_idempotent():
    call_command("seed_transition_prompt_set")
    template_pks = set(ReportTemplate.objects.values_list("pk", flat=True))
    prompt_pks = set(TemplatePrompt.objects.values_list("pk", flat=True))

    call_command("seed_transition_prompt_set")

    assert ReportTemplate.objects.count() == 4
    assert TemplatePrompt.objects.count() == 44
    assert set(ReportTemplate.objects.values_list("pk", flat=True)) == template_pks
    assert set(TemplatePrompt.objects.values_list("pk", flat=True)) == prompt_pks


def test_seed_dry_run_writes_nothing():
    call_command("seed_transition_prompt_set", "--dry-run")
    assert ReportTemplate.objects.count() == 0
    assert TemplatePrompt.objects.count() == 0


@pytest.mark.parametrize(
    "position_type,expected_total,expected_required,expected_optional",
    [
        ("CHAPTER_OFFICER", 10, 7, 3),
        ("COMMITTEE_CHAIR", 12, 8, 4),
        ("COUNCIL", 11, 5, 6),
        ("NATIONAL_OFFICER", 11, 5, 6),
    ],
)
def test_seeded_required_optional_counts_per_template(
    position_type, expected_total, expected_required, expected_optional
):
    call_command("seed_transition_prompt_set")
    prompts = ReportTemplate.objects.get(position_type=position_type).prompts
    assert prompts.count() == expected_total
    assert prompts.filter(is_required=True).count() == expected_required
    assert prompts.filter(is_required=False).count() == expected_optional


def test_systems_access_is_required_for_chapter_officer_but_optional_for_committee_chair():
    call_command("seed_transition_prompt_set")
    chapter_officer = ReportTemplate.objects.get(position_type="CHAPTER_OFFICER")
    committee_chair = ReportTemplate.objects.get(position_type="COMMITTEE_CHAIR")

    assert chapter_officer.prompts.get(prompt_key="systems_access").is_required is True
    assert committee_chair.prompts.get(prompt_key="systems_access").is_required is False


def test_shared_prompt_key_has_identical_content_across_templates():
    call_command("seed_transition_prompt_set")
    successes_prompts = TemplatePrompt.objects.filter(prompt_key="successes")
    assert successes_prompts.count() == 4  # one per template
    labels = {p.label for p in successes_prompts}
    help_texts = {p.help_text for p in successes_prompts}
    tags = {p.tag for p in successes_prompts}
    assert len(labels) == 1
    assert len(help_texts) == 1
    assert len(tags) == 1


def test_prompt_order_is_sequential_within_each_template():
    call_command("seed_transition_prompt_set")
    for template in ReportTemplate.objects.all():
        orders = list(template.prompts.order_by("order").values_list("order", flat=True))
        assert orders == list(range(1, len(orders) + 1))


def test_advisor_roles_excluded_from_seeded_templates():
    call_command("seed_transition_prompt_set")
    seeded_types = set(ReportTemplate.objects.values_list("position_type", flat=True))
    assert "ADVISOR_ROLES" not in seeded_types
    assert seeded_types == {"CHAPTER_OFFICER", "COMMITTEE_CHAIR", "COUNCIL", "NATIONAL_OFFICER"}


@pytest.mark.parametrize(
    "position_key,expected_template_name",
    [
        ("treasurer", "Chapter Officer Transition Report"),
        ("pledge/new member educator", "Chapter Officer Transition Report"),
        ("committee chair", "Committee Chair Transition Report"),
        ("grand regent", "Council Transition Report"),
        ("regional director", "National Officer Transition Report"),
    ],
)
def test_resolve_template_after_seeding(position_key, expected_template_name):
    call_command("seed_transition_prompt_set")
    assert services.resolve_template(position_key).name == expected_template_name


# ---------------------------------------------------------------------------
# generate_transition_obligations (TRWI-3)
# ---------------------------------------------------------------------------
def test_generate_transition_obligations_creates_and_reports_counts(capsys):
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    end = datetime.date.today() + datetime.timedelta(days=30)
    UserRoleChange.objects.create(user=user, role="treasurer", start=end - datetime.timedelta(days=180), end=end)

    call_command("generate_transition_obligations")

    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()
    output = capsys.readouterr().out
    assert "created from term ends" in output


def test_generate_transition_obligations_dry_run_flag_writes_nothing(capsys):
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    end = datetime.date.today() + datetime.timedelta(days=30)
    UserRoleChange.objects.create(user=user, role="treasurer", start=end - datetime.timedelta(days=180), end=end)

    call_command("generate_transition_obligations", "--dry-run")

    assert not ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_generate_transition_obligations_lookahead_days_flag_is_respected():
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    end = datetime.date.today() + datetime.timedelta(days=100)
    UserRoleChange.objects.create(user=user, role="treasurer", start=end - datetime.timedelta(days=180), end=end)

    call_command("generate_transition_obligations", "--lookahead-days", "45")
    assert not ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()

    call_command("generate_transition_obligations", "--lookahead-days", "150")
    assert ReportObligation.objects.filter(chapter=chapter, position_key="treasurer").exists()


# ---------------------------------------------------------------------------
# send_transition_report_reminders (TRWI-4)
# ---------------------------------------------------------------------------
def test_send_transition_report_reminders_reports_counts(capsys):
    chapter = ChapterFactory()
    user = UserFactory(chapter=chapter)
    due_date = datetime.date.today() + datetime.timedelta(days=21)
    ReportObligation.objects.create(
        chapter=chapter,
        position_type="CHAPTER_OFFICER",
        position_key="treasurer",
        officer=user,
        term_start=due_date - datetime.timedelta(days=166),
        term_end=due_date + datetime.timedelta(days=14),
        due_date=due_date,
        is_required=True,
        status="open",
    )

    call_command("send_transition_report_reminders")

    output = capsys.readouterr().out
    assert "1 due-date reminder(s)" in output


def test_send_transition_report_reminders_dry_run_flag(capsys):
    call_command("send_transition_report_reminders", "--dry-run")
    assert "[dry-run]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# seed_transition_tags (2026-09 follow-up to TRWI-13)
# ---------------------------------------------------------------------------
# NOTE: migration 0008 data-seeds the original 9 TAG_CHOICES names into every
# test database, so assertions below check for specific names/deltas rather
# than assuming TransitionTag starts out empty.
def test_seed_transition_tags_creates_suggested_region_and_chapter_tags():
    region = RegionFactory(name="Test Seed Region")
    chapter = ChapterFactory(name="alpha", region=region, active=True)

    call_command("seed_transition_tags")

    names = set(TransitionTag.objects.values_list("name", flat=True))
    assert "budget" in names
    assert region.name in names
    assert chapter.name in names


def test_seed_transition_tags_skips_inactive_chapters():
    inactive = ChapterFactory(name="beta", active=False)

    call_command("seed_transition_tags")

    assert not TransitionTag.objects.filter(name__iexact=inactive.name).exists()


def test_seed_transition_tags_is_idempotent():
    ChapterFactory(name="kappa", active=True)
    call_command("seed_transition_tags")
    pks_after_first_run = set(TransitionTag.objects.values_list("pk", flat=True))

    call_command("seed_transition_tags")

    assert set(TransitionTag.objects.values_list("pk", flat=True)) == pks_after_first_run


def test_seed_transition_tags_does_not_duplicate_an_existing_tag_with_different_case():
    TransitionTag.objects.create(name="Budget")

    call_command("seed_transition_tags")

    assert TransitionTag.objects.filter(name__iexact="budget").count() == 1


def test_seed_transition_tags_dry_run_writes_nothing(capsys):
    chapter = ChapterFactory(name="delta", active=True)
    count_before = TransitionTag.objects.count()

    call_command("seed_transition_tags", "--dry-run")

    assert TransitionTag.objects.count() == count_before
    assert not TransitionTag.objects.filter(name__iexact=chapter.name).exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_seed_transition_tags_reports_created_and_skipped_counts(capsys):
    call_command("seed_transition_tags")

    output = capsys.readouterr().out
    assert "created" in output
    assert "already existed" in output
