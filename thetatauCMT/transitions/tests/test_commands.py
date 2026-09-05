import pytest
from django.core.management import call_command

from .. import services
from ..models import ReportTemplate, TemplatePrompt

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
