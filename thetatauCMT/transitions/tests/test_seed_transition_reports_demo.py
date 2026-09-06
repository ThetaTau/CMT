import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from freezegun import freeze_time

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.transitions import services
from thetatauCMT.transitions.models import ReportObligation, ReportTag, ReportTemplate, TransitionReport
from thetatauCMT.users.models import User

pytestmark = pytest.mark.django_db

QA_PREFIX = "[QA] Transitions"
EMAIL_DOMAIN = "transitions-qa.thetatau.local"


def _seed(**kwargs):
    kwargs.setdefault("force", True)
    call_command("seed_transition_reports_demo", **kwargs)


def _counts():
    return {
        "chapters": Chapter.objects.filter(name__startswith=QA_PREFIX).count(),
        "regions": Region.objects.filter(name__startswith=QA_PREFIX).count(),
        "users": User.objects.filter(email__endswith=f"@{EMAIL_DOMAIN}").count(),
        "obligations": ReportObligation.objects.filter(chapter__name__startswith=QA_PREFIX).count(),
        "reports": TransitionReport.objects.filter(chapter__name__startswith=QA_PREFIX).count(),
        "tags": ReportTag.objects.filter(report__chapter__name__startswith=QA_PREFIX).count(),
    }


def _user(local_part):
    return User.objects.get(username=f"{local_part}@{EMAIL_DOMAIN}")


# ---------------------------------------------------------------------------
# Runs cleanly on an empty DB + full status/type coverage
# ---------------------------------------------------------------------------
def test_seeds_full_coverage_on_empty_db():
    _seed()

    obligations = ReportObligation.objects.filter(chapter__name__startswith=QA_PREFIX)
    statuses = set(obligations.values_list("status", flat=True))
    assert statuses == {"open", "submitted", "missed", "na_vacant"}

    reports = TransitionReport.objects.filter(chapter__name__startswith=QA_PREFIX)
    assert reports.count() == 7
    position_types = set(reports.values_list("position_type", flat=True))
    assert position_types == {"CHAPTER_OFFICER", "COUNCIL", "NATIONAL_OFFICER", "COMMITTEE_CHAIR"}


def test_seeds_the_position_specific_treasurer_override():
    _seed()

    override = ReportTemplate.objects.get(position_type="CHAPTER_OFFICER", position_key="treasurer")
    default = ReportTemplate.objects.get(position_type="CHAPTER_OFFICER", position_key="")
    assert override.pk != default.pk
    assert override.prompts.filter(prompt_key="financial_handoff").exists()
    # Every treasurer report at Alpha resolved the OVERRIDE, not the type default.
    treasurer_reports = TransitionReport.objects.filter(chapter__name__startswith=QA_PREFIX, position_key="treasurer")
    assert treasurer_reports.count() == 3  # the 3-generation predecessor chain
    assert all(report.template_id == override.pk for report in treasurer_reports)


def test_seeds_a_multi_generation_treasurer_chain_with_mixed_tag_sources_and_an_attachment():
    _seed()

    successor = _user("treasurer")
    packet = list(services.get_handoff_packet(successor, successor.chapter, "treasurer"))
    assert len(packet) == 3  # 3 predecessor generations, most-recent-first

    most_recent = packet[0]
    assert most_recent.acknowledgements.exists()
    assert set(most_recent.tags.filter(source="manual").values_list("tag", flat=True)) == {"expertise"}
    assert most_recent.tags.filter(source="prompt").exists()

    minimal = [report for report in packet if report.attachments.exists()][0]
    assert minimal.attachments.count() == 1


def test_missed_and_na_vacant_obligations_have_no_report():
    _seed()

    missed = ReportObligation.objects.get(chapter__name=f"{QA_PREFIX} Chapter Alpha", position_key="scribe")
    assert missed.status == "missed"
    assert not hasattr(missed, "report")

    vacant = ReportObligation.objects.get(chapter__name=f"{QA_PREFIX} Chapter Beta", position_key="vice regent")
    assert vacant.status == "na_vacant"
    assert not hasattr(vacant, "report")


# ---------------------------------------------------------------------------
# TRWI-6 access scenarios represented (mirrors docs/specs/transition-reports-qa.md)
# ---------------------------------------------------------------------------
def test_successor_reads_own_chapter_predecessors_only():
    _seed()
    successor = _user("treasurer")

    readable_chapters = set(services.get_readable_reports(successor).values_list("chapter__name", flat=True))
    assert readable_chapters == {f"{QA_PREFIX} Chapter Alpha"}


def test_regent_reads_every_position_in_their_own_chapter_only():
    _seed()
    regent = _user("regent")

    readable = services.get_readable_reports(regent)
    assert set(readable.values_list("chapter__name", flat=True)) == {f"{QA_PREFIX} Chapter Alpha"}
    assert set(readable.values_list("position_key", flat=True)) >= {"treasurer"}


def test_rd_reads_their_own_region_but_not_the_other_region():
    _seed()
    rd = _user("rd")

    readable_chapters = set(services.get_readable_reports(rd).values_list("chapter__name", flat=True))
    # Alpha and Beta are both in "[QA] Transitions Region" (the RD's own region);
    # Delta is in a SEPARATE region and must be excluded.
    assert readable_chapters == {f"{QA_PREFIX} Chapter Alpha", f"{QA_PREFIX} Chapter Beta"}
    assert f"{QA_PREFIX} Chapter Delta" not in readable_chapters


def test_ccd_and_national_officer_read_everywhere_including_the_other_region():
    _seed()
    ccd = _user("ccd")
    natoff = _user("natoff")

    for user in (ccd, natoff):
        readable_chapters = set(services.get_readable_reports(user).values_list("chapter__name", flat=True))
        assert readable_chapters == {
            f"{QA_PREFIX} Chapter Alpha",
            f"{QA_PREFIX} Chapter Beta",
            f"{QA_PREFIX} Chapter Delta",
        }


def test_outsider_reads_nothing():
    _seed()
    outsider = _user("outsider")

    assert not services.get_readable_reports(outsider).exists()


def test_national_trend_view_shows_the_zero_submission_chapter():
    _seed()

    no_submissions = services.get_chapters_with_no_submissions(cycle="all")
    assert f"{QA_PREFIX} Chapter Gamma" in no_submissions.values_list("name", flat=True)
    assert f"{QA_PREFIX} Chapter Alpha" not in no_submissions.values_list("name", flat=True)


# ---------------------------------------------------------------------------
# Idempotency / --flush / production guard
# ---------------------------------------------------------------------------
def test_rerun_without_flush_no_duplicates():
    _seed()
    before = _counts()

    _seed()

    assert _counts() == before


def test_rerun_after_real_time_passes_no_duplicate_obligations():
    """Regression test: re-running days later (no --flush) used to shift
    every role change's start/end forward, which shifted generate_obligations'
    own (chapter, position_key, term_start, term_end) natural key too --
    silently creating a SECOND ReportObligation per user/position instead of
    reusing the first, so _submit()'s .get(position_key=...) raised
    MultipleObjectsReturned the next time the command ran.
    """
    with freeze_time("2026-01-01"):
        _seed()
    with freeze_time("2026-01-20"):
        _seed()

    duplicated = (
        ReportObligation.objects.filter(chapter__name__startswith=QA_PREFIX)
        .values("officer_id", "position_key")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    assert not duplicated.exists()
    # The successor's own obligation must still be uniquely gettable, exactly
    # like the traceback from the reported bug.
    treasurer = _user("pred.treasurer.1")
    assert treasurer.transition_report_obligations.get(position_key="treasurer")


def test_flush_reseed_is_consistent():
    _seed()
    before = _counts()

    _seed(flush=True)

    assert _counts() == before


def test_flush_never_touches_the_shared_prompt_set_templates():
    _seed()
    template_count_before = ReportTemplate.objects.count()

    _seed(flush=True)

    assert ReportTemplate.objects.count() == template_count_before


def test_refuses_without_force(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_transition_reports_demo")
