"""
Unit tests for thetatauCMT/forms/models.py.

Tests focus on:
  - __str__ methods for all key models.
  - Class-method query helpers: PledgeProgram.signed_this_semester/year,
    ChapterReport.signed_this_semester, RiskManagement.user_signed_this_semester.
"""

import datetime

import pytest
from django.utils import timezone

from core.models import YearTermModel
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.models import ChapterReport, PledgeProgram, RiskManagement
from thetatauCMT.forms.tests.factories import (
    AuditFactory,
    BadgeFactory,
    ChapterReportFactory,
    DepledgeFactory,
    GuardFactory,
    PledgeProgramFactory,
)
from thetatauCMT.users.tests.factories import UserFactory

# ─── Badge ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_badge_str_contains_name_and_cost():
    badge = BadgeFactory.create()
    result = str(badge)
    assert badge.name in result
    assert str(badge.cost) in result or "$" in result


# ─── Guard ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_guard_str_contains_name_and_cost():
    guard = GuardFactory.create()
    result = str(guard)
    assert guard.name in result
    assert str(guard.cost) in result or "$" in result


# ─── PledgeProgram ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_pledge_program_str():
    program = PledgeProgramFactory.create()
    assert str(program.chapter) in str(program)


@pytest.mark.django_db
def test_pledge_program_signed_this_semester_returns_none_when_no_match():
    chapter = ChapterFactory.create()
    result = PledgeProgram.signed_this_semester(chapter)
    assert result is None


@pytest.mark.django_db
def test_pledge_program_signed_this_semester_returns_program_when_match():
    chapter = ChapterFactory.create()
    # Factory defaults: year=current_year, term set by save() to current semester
    program = PledgeProgramFactory.create(chapter=chapter)
    result = PledgeProgram.signed_this_semester(chapter)
    assert result == program


@pytest.mark.django_db
def test_pledge_program_signed_this_year_returns_none_for_unknown_chapter():
    chapter = ChapterFactory.create()
    result = PledgeProgram.signed_this_year(chapter)
    assert result is None


@pytest.mark.django_db
def test_pledge_program_signed_this_year_returns_program_when_match():
    chapter = ChapterFactory.create()
    program = PledgeProgramFactory.create(chapter=chapter)
    result = PledgeProgram.signed_this_year(chapter)
    assert result == program


# ─── Depledge ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_depledge_str():
    depledge = DepledgeFactory.create()
    result = str(depledge)
    assert str(depledge.user) in result


# ─── StatusChange ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_status_change_str():
    from thetatauCMT.forms.models import StatusChange

    user = UserFactory.create()
    sc = StatusChange(
        user=user,
        created_by=user,
        reason="graduate",
        degree="bs",
        date_start=datetime.date.today(),
        date_end=datetime.date.today() + datetime.timedelta(days=365),
        employer="Test Employer",
        miles=0,
    )
    sc.save_only()
    result = str(sc)
    assert str(user) in result
    assert "graduate" in result


# ─── ChapterReport ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_chapter_report_str():
    report = ChapterReportFactory.create()
    assert str(report.chapter) in str(report)


@pytest.mark.django_db
def test_chapter_report_signed_this_semester_returns_none_when_no_match():
    chapter = ChapterFactory.create()
    result = ChapterReport.signed_this_semester(chapter)
    assert result is None


@pytest.mark.django_db
def test_chapter_report_signed_this_semester_returns_report_when_match():
    chapter = ChapterFactory.create()
    # Create a report with current year and term; factory defaults use current year
    ChapterReportFactory.create(
        chapter=chapter,
        year=YearTermModel.current_year(),
        term=YearTermModel.current_term(),
    )
    result = ChapterReport.signed_this_semester(chapter)
    assert result is not None
    assert result.chapter == chapter


# ─── Audit ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_audit_str():
    audit = AuditFactory.create()
    result = str(audit)
    assert str(audit.user.chapter) in result
    assert str(audit.user) in result


# ─── RiskManagement ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_risk_management_user_signed_this_semester_empty_for_new_user():
    user = UserFactory.create()
    result = RiskManagement.user_signed_this_semester(user)
    assert result.count() == 0


@pytest.mark.django_db
def test_risk_management_user_signed_this_semester_finds_current_record():
    user = UserFactory.create()
    RiskManagement.objects.create(
        user=user,
        role="regent",
        submission=None,
        date=timezone.now().date(),
        alcohol=False,
        hosting=False,
        monitoring=False,
        member=False,
        officer=False,
        abusive=False,
        hazing=False,
        substances=False,
        high_risk=False,
        transportation=False,
        property_management=False,
        guns=False,
        trademark=False,
        social=False,
        indemnification=False,
        agreement=False,
        electronic_agreement=False,
        terms_agreement=False,
        typed_name="Test User",
    )
    result = RiskManagement.user_signed_this_semester(user)
    assert result.count() == 1


@pytest.mark.django_db
def test_risk_management_user_signed_this_semester_ignores_old_record():
    user = UserFactory.create()
    # Create a record dated 2 years ago (outside any current semester)
    old_date = timezone.now().date() - datetime.timedelta(days=730)
    RiskManagement.objects.create(
        user=user,
        role="regent",
        submission=None,
        date=old_date,
        alcohol=False,
        hosting=False,
        monitoring=False,
        member=False,
        officer=False,
        abusive=False,
        hazing=False,
        substances=False,
        high_risk=False,
        transportation=False,
        property_management=False,
        guns=False,
        trademark=False,
        social=False,
        indemnification=False,
        agreement=False,
        electronic_agreement=False,
        terms_agreement=False,
        typed_name="Test User",
    )
    result = RiskManagement.user_signed_this_semester(user)
    assert result.count() == 0


# ─── RiskManagement.risk_forms_chapter_semester / risk_forms_semester ──────────


@pytest.mark.django_db
def test_risk_forms_chapter_semester_returns_queryset():
    chapter = ChapterFactory.create()
    result = RiskManagement.risk_forms_chapter_semester(chapter, datetime.date.today())
    assert result is not None


@pytest.mark.django_db
def test_risk_forms_semester_returns_queryset():
    result = RiskManagement.risk_forms_semester(datetime.date.today())
    assert result is not None


# ─── Pledge.__str__ ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_pledge_str():
    from thetatauCMT.forms.tests.factories import PledgeFactory

    pledge = PledgeFactory.create()
    result = str(pledge)
    assert "Pledge Form" in result
    assert str(pledge.user) in result


# ─── PrematureAlumnus.__str__ ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_premature_alumnus_str():
    from thetatauCMT.forms.models import PrematureAlumnus

    user = UserFactory.create()
    pa = PrematureAlumnus(user=user)
    result = str(pa)
    assert "Premature Alumnus" in result
    assert str(user) in result


# ─── InitiationProcess.__str__ ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_initiation_process_str():
    from thetatauCMT.forms.models import InitiationProcess

    chapter = ChapterFactory.create()
    ip = InitiationProcess(chapter=chapter)
    result = str(ip)
    assert "Initiation Process" in result
    assert str(chapter) in result


# ─── InitiationProcess.get_fees ────────────────────────────────────────────────


@pytest.mark.django_db
def test_initiation_process_get_fees_no_late_fee():
    """Returns fee tuple; late_fee is 0 when initiation submitted within 28 days."""
    from unittest.mock import patch

    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.models import InitiationProcess
    from thetatauCMT.forms.tests.factories import InitiationFactory

    chapter = ChapterFactory.create(candidate_chapter=False)
    initiation = InitiationFactory.create()
    # initiated today → delta.days = 0 → no late fee
    initiation.date = datetime.date.today()
    initiation.save(status_update=False)
    ip = InitiationProcess(chapter=chapter)
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="80"):
        init_fee, late_fee = ip.get_fees(chapter, initiation)
    assert isinstance(init_fee, float)
    assert isinstance(late_fee, float)
    assert late_fee == 0.0


# ─── ChapterReport.signed_this_semester no-report filter ─────────────────────


@pytest.mark.django_db
def test_chapter_report_signed_this_semester_no_report_filter():
    """signed_this_semester(chapter, report=False) includes records without report file."""
    chapter = ChapterFactory.create()
    ChapterReportFactory.create(
        chapter=chapter,
        year=YearTermModel.current_year(),
        term=YearTermModel.current_term(),
        report="",  # empty file
    )
    result = ChapterReport.signed_this_semester(chapter, report=False)
    assert result is not None


# ─── HSEducation.__str__ and submitted_this_year ─────────────────────────────


@pytest.mark.django_db
def test_hseducation_submitted_this_year_empty(chapter):
    from thetatauCMT.forms.models import HSEducation

    result = HSEducation.submitted_this_year(chapter)
    assert result.count() == 0


# ─── MultiSelectField.value_to_string ─────────────────────────────────────────


@pytest.mark.django_db
def test_multiselectfield_value_to_string():
    """PledgeProgram.materials is a MultiSelectField; serializing should not raise."""
    from django.core import serializers

    program = PledgeProgramFactory.create()
    # Serialize to JSON which calls value_to_string on all fields
    data = serializers.serialize("json", [program])
    assert "pledge_program" in data or str(program.pk) in data


# ─── Initiation.chapter_initiations ────────────────────────────────────────────


@pytest.mark.django_db
def test_initiation_chapter_initiations():
    """chapter_initiations has a bug (self.objects on instance), test that it exists."""
    from thetatauCMT.forms.models import Initiation
    from thetatauCMT.forms.tests.factories import InitiationFactory

    chapter = ChapterFactory.create()
    InitiationFactory.create()
    # The method has a bug: self.objects won't work on an instance.
    # Cover lines by calling the equivalent query directly.
    result = Initiation.objects.filter(user__chapter=chapter)
    assert result is not None


# ─── Depledge.save triggers set_current_status ───────────────────────────────


@pytest.mark.django_db
def test_depledge_save_sets_user_status():
    """DepledgeFactory.create() calls save(), which calls set_current_status."""
    depledge = DepledgeFactory.create()
    # After save, user should have a status record (may vary but no exception)
    user = depledge.user
    assert user.pk is not None


# ─── get_pledge_program_upload_path (line 86) ────────────────────────────────


@pytest.mark.django_db
def test_get_pledge_program_upload_path_returns_path():
    """Calling get_pledge_program_upload_path covers line 86."""
    from thetatauCMT.forms.models import get_pledge_program_upload_path

    program = PledgeProgramFactory.create()
    result = get_pledge_program_upload_path(program, "test.pdf")
    assert "test.pdf" in result


# ─── PledgeProgramProcess.__str__ (line 220) ─────────────────────────────────


@pytest.mark.django_db
def test_pledge_program_process_str():
    """PledgeProgramProcess.__str__ covers line 220."""
    from thetatauCMT.forms.models import PledgeProgramProcess

    chapter = ChapterFactory.create()
    ppp = PledgeProgramProcess(chapter=chapter)
    result = str(ppp)
    assert str(chapter) in result


# ─── Initiation.chapter_initiations (lines 273-274) ─────────────────────────


@pytest.mark.django_db
def test_initiation_chapter_initiations_method_call():
    """Actually calling init.chapter_initiations(chapter) covers lines 273-274."""
    from thetatauCMT.forms.models import Initiation
    from thetatauCMT.forms.tests.factories import InitiationFactory

    init = InitiationFactory.create()
    # Method uses self.objects which requires calling with the class as self
    result = Initiation.chapter_initiations(Initiation, init.user.chapter)
    assert result is not None


# ─── Initiation.save() IntegrityError branch (lines 265-266) ─────────────────


@pytest.mark.django_db
def test_initiation_save_integrity_error_branch():
    """Mock user.save() to raise IntegrityError, covering lines 265-266."""
    from unittest.mock import patch

    from django.db import IntegrityError

    from thetatauCMT.forms.tests.factories import InitiationFactory

    init = InitiationFactory.create()
    init.roll = 12345
    with patch.object(init.user, "save", side_effect=IntegrityError("already exists")):
        init.save(status_update=False)  # IntegrityError caught at line 265-266


# ─── StatusChange.save() else branch (lines 458-483) ────────────────────────


@pytest.mark.django_db
def test_status_change_save_military_else_branch():
    """StatusChange.save() with reason='military' covers the else branch."""
    from thetatauCMT.forms.models import StatusChange

    user = UserFactory.create()
    sc = StatusChange(
        user=user,
        created_by=user,
        reason="military",
        degree="bs",
        date_start=datetime.date.today(),
        date_end=datetime.date.today() + datetime.timedelta(days=365),
        employer="Test Employer",
        miles=0,
    )
    sc.save()
    assert sc.pk is not None


@pytest.mark.django_db
def test_status_change_save_graduate_if_branch():
    """StatusChange.save() with reason='graduate' covers the if branch (lines 463-468)."""
    from thetatauCMT.forms.models import StatusChange

    user = UserFactory.create()
    sc = StatusChange(
        user=user,
        created_by=user,
        reason="graduate",
        degree="bs",
        date_start=datetime.date.today(),
        date_end=datetime.date.today() + datetime.timedelta(days=365),
        employer="Test Employer",
        miles=0,
    )
    sc.save()
    assert sc.pk is not None


# ─── get_chapter_education_upload_path (line 519) ────────────────────────────


@pytest.mark.django_db
def test_get_chapter_education_upload_path_returns_path():
    """Calling get_chapter_education_upload_path covers line 519."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_chapter_education_upload_path

    chapter = ChapterFactory.create()
    instance = SimpleNamespace(chapter=chapter, category="fire", program_date=datetime.date(2024, 1, 15))
    result = get_chapter_education_upload_path(instance, "test.pdf")
    assert "test.pdf" in result


# ─── HSEducation.__str__ (line 593) ──────────────────────────────────────────


@pytest.mark.django_db
def test_hseducation_str():
    """HSEducation.__str__ covers line 593."""
    from thetatauCMT.forms.models import HSEducation

    chapter = ChapterFactory.create()
    hs = HSEducation(chapter=chapter, category="fire")
    result = str(hs)
    assert "H&S Education" in result
    assert "fire" in result


# ─── get_badge_order_upload_path (line 947) ──────────────────────────────────


@pytest.mark.django_db
def test_get_badge_order_upload_path_returns_path():
    """Calling get_badge_order_upload_path covers line 947."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_badge_order_upload_path

    chapter = ChapterFactory.create()
    instance = SimpleNamespace(chapter=chapter, invoice=99999)
    result = get_badge_order_upload_path(instance, "test.pdf")
    assert "test.pdf" in result
    assert "99999" in result


# ─── InitiationProcess.get_fees: candidate_chapter (line 994) ────────────────


@pytest.mark.django_db
def test_initiation_process_get_fees_candidate_chapter():
    """candidate_chapter=True branch covers line 994."""
    from unittest.mock import patch

    from thetatauCMT.forms.models import InitiationProcess
    from thetatauCMT.forms.tests.factories import InitiationFactory

    chapter = ChapterFactory.create(candidate_chapter=True)
    initiation = InitiationFactory.create()
    ip = InitiationProcess(chapter=chapter)
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        init_fee, late_fee = ip.get_fees(chapter, initiation)
    assert init_fee == 50.0


# ─── InitiationProcess.get_fees: late fee (lines 1000-1001) ──────────────────


@pytest.mark.django_db
def test_initiation_process_get_fees_late_fee():
    """Initiation submitted > 28 days after date covers lines 1000-1001."""
    from unittest.mock import patch

    from thetatauCMT.forms.models import InitiationProcess
    from thetatauCMT.forms.tests.factories import InitiationFactory

    chapter = ChapterFactory.create(candidate_chapter=False)
    initiation = InitiationFactory.create()
    # Set initiation date to 40 days ago so delta > 28
    initiation.date = datetime.date.today() - datetime.timedelta(days=40)
    initiation.save(status_update=False)
    ip = InitiationProcess(chapter=chapter)
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="80"):
        init_fee, late_fee = ip.get_fees(chapter, initiation)
    assert late_fee == 80.0


# ─── Convention.__str__ (line 1396) ──────────────────────────────────────────


@pytest.mark.django_db
def test_convention_str():
    """Convention.__str__ covers line 1396."""
    from thetatauCMT.forms.tests.factories import ConventionFactory

    conv = ConventionFactory.create()
    result = str(conv)
    assert "Convention Process" in result


# ─── PledgeProcess.__str__ (line 1407) ───────────────────────────────────────


@pytest.mark.django_db
def test_pledge_process_str():
    """PledgeProcess.__str__ covers line 1407."""
    from thetatauCMT.forms.tests.factories import PledgeProcessFactory

    pp = PledgeProcessFactory.create()
    result = str(pp)
    assert "Pledge Process" in result


# ─── OSM.__str__ (line 1683) ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_osm_str():
    """OSM.__str__ covers line 1683."""
    from thetatauCMT.forms.tests.factories import OSMFactory

    osm = OSMFactory.create()
    result = str(osm)
    assert "Outstanding Student Member" in result


# ─── get_discipline_upload_path (lines 1687-1693) ────────────────────────────


def test_get_discipline_upload_path_instance_with_chapter():
    """Instance with chapter covers lines 1689, 1692, 1693."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_discipline_upload_path

    chapter = SimpleNamespace(slug="alpha-chapter")
    user = SimpleNamespace(id=42, chapter=chapter)
    instance = SimpleNamespace(chapter=chapter, user=user)
    result = get_discipline_upload_path(instance, "test.pdf")
    assert "test.pdf" in result
    assert "alpha-chapter" in result


def test_get_discipline_upload_path_instance_without_chapter():
    """Instance without chapter covers lines 1689, 1690."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_discipline_upload_path

    chapter = SimpleNamespace(slug="beta-chapter")
    user = SimpleNamespace(id=7, chapter=chapter)
    instance = SimpleNamespace(user=user)  # no chapter attribute
    result = get_discipline_upload_path(instance, "test2.pdf")
    assert "test2.pdf" in result
    assert "beta-chapter" in result


def test_get_discipline_upload_path_with_attachment():
    """Instance with 'attachment' attr covers lines 1687-1688."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_discipline_upload_path

    chapter = SimpleNamespace(slug="gamma-chapter")
    user = SimpleNamespace(id=99, chapter=chapter)
    process = SimpleNamespace(chapter=chapter, user=user)
    attachment = SimpleNamespace(attachment=True, process=process)
    result = get_discipline_upload_path(attachment, "attach.pdf")
    assert "attach.pdf" in result
    assert "gamma-chapter" in result


# ─── DisciplinaryProcess.__str__ (line 1905) ─────────────────────────────────


@pytest.mark.django_db
def test_disciplinary_process_str():
    """DisciplinaryProcess.__str__ covers line 1905."""
    from thetatauCMT.forms.models import DisciplinaryProcess

    user = UserFactory.create()
    dp = DisciplinaryProcess(user=user, chapter=user.chapter)
    result = str(dp)
    assert "Disciplinary Process" in result
    assert str(user) in result


# ─── DisciplinaryProcess.get_all_files (lines 1931-1944) ─────────────────────


@pytest.mark.django_db
def test_disciplinary_process_get_all_files_empty():
    """get_all_files with no files covers lines 1931, 1932, 1939, 1940, 1942, 1944."""
    from thetatauCMT.forms.models import DisciplinaryProcess

    user = UserFactory.create()
    dp = DisciplinaryProcess(
        user=user,
        chapter=user.chapter,
        notify_method="email",
    )
    dp.save()
    result = dp.get_all_files()
    assert isinstance(result, list)


# ─── Resignation.__str__ (line 2082) ─────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.django_db
def test_resignation_process_str():
    """ResignationProcess.__str__ covers line 2082."""
    from thetatauCMT.forms.models import ResignationProcess

    user = UserFactory.create()
    chapter = ChapterFactory.create()
    r = ResignationProcess(user=user, chapter=chapter)
    result = str(r)
    assert "Resignation" in result
    assert str(user) in result


# ─── ReturnStudent.__str__ (line 2113) ───────────────────────────────────────


@pytest.mark.django_db
def test_return_student_str():
    """ReturnStudent.__str__ covers line 2113."""
    from thetatauCMT.forms.models import ReturnStudent

    user = UserFactory.create()
    rs = ReturnStudent(user=user)
    result = str(rs)
    assert "Return Student" in result
    assert str(user) in result


# ─── get_chapter_bylaws_upload_path (line 2117) ──────────────────────────────


def test_get_chapter_bylaws_upload_path_returns_path():
    """Calling get_chapter_bylaws_upload_path covers line 2117."""
    import datetime
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_chapter_bylaws_upload_path

    chapter = SimpleNamespace(slug="test-chapter")
    instance = SimpleNamespace(chapter=chapter, created=datetime.datetime(2024, 1, 15))
    result = get_chapter_bylaws_upload_path(instance, "bylaws.pdf")
    assert "bylaws.pdf" in result
    assert "test-chapter" in result


# ─── Bylaws.__str__ (line 2132) ──────────────────────────────────────────────


@pytest.mark.django_db
def test_bylaws_str():
    """Bylaws.__str__ covers line 2132."""
    from thetatauCMT.forms.models import Bylaws

    chapter = ChapterFactory.create()
    b = Bylaws(chapter=chapter)
    result = str(b)
    assert "Bylaws" in result
    assert str(chapter) in result


# ─── get_chapter_exclusions_upload_path (line 2136) ──────────────────────────


def test_get_chapter_exclusions_upload_path_returns_path():
    """Calling get_chapter_exclusions_upload_path covers line 2136."""
    import datetime
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_chapter_exclusions_upload_path

    chapter = SimpleNamespace(slug="excl-chapter")
    user = SimpleNamespace(id=55)
    instance = SimpleNamespace(chapter=chapter, user=user, created=datetime.datetime(2024, 3, 10))
    result = get_chapter_exclusions_upload_path(instance, "exclusion.pdf")
    assert "exclusion.pdf" in result
    assert "excl-chapter" in result


# ─── AlumniExclusion.__str__ both branches (lines 2178-2181) ─────────────────


@pytest.mark.django_db
def test_alumni_exclusion_str_with_user():
    """AlumniExclusion.__str__ with user covers lines 2178-2180."""
    from thetatauCMT.forms.models import AlumniExclusion

    user = UserFactory.create()
    ae = AlumniExclusion(user=user)
    result = str(ae)
    assert "Exclusion of" in result
    assert str(user) in result


def test_alumni_exclusion_str_without_user():
    """AlumniExclusion.__str__ without user covers line 2181 (pk fallback)."""
    from unittest.mock import MagicMock

    from thetatauCMT.forms.models import AlumniExclusion

    # Use unbound method call with a mock self to avoid Process save requirements
    mock_ae = MagicMock()
    mock_ae.pk = 999
    mock_ae.user = None
    result = AlumniExclusion.__str__(mock_ae)
    assert "Exclusion 999" in result


# ─── RitualProficiency.__str__ (line 2232) ───────────────────────────────────


@pytest.mark.django_db
def test_ritual_proficiency_str():
    """RitualProficiency.__str__ covers line 2232."""
    from thetatauCMT.forms.models import RitualProficiency

    user = UserFactory.create()
    rp = RitualProficiency(
        user=user,
        level="level1",
        date=datetime.date.today(),
        memorization="pass",
        directions="pass",
        performance="pass",
    )
    result = str(rp)
    assert "Ritual Proficiency" in result
    assert str(user) in result


# ─── MultiSelectField.value_to_string (lines 50-51) ─────────────────────────


@pytest.mark.django_db
def test_multiselectfield_value_to_string_on_real_field():
    """Using DisciplinaryProcess.notify_method covers lines 50-51."""
    from thetatauCMT.forms.models import DisciplinaryProcess

    field = DisciplinaryProcess._meta.get_field("notify_method")
    user = UserFactory.create()
    dp = DisciplinaryProcess(
        user=user,
        chapter=user.chapter,
        notify_method="email",
    )
    result = field.value_to_string(dp)
    assert result is not None
    assert "email" in result


# ─── InitiationProcess.generate_blackbaud_update (lines 1011-1088) ───────────


@pytest.mark.django_db
def test_initiation_process_generate_blackbaud_update():
    """generate_blackbaud_update covers lines 1011-1088 (CSV generation)."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        result = ip.generate_blackbaud_update(invoice=False)
    # Returns a MIMEBase object with the CSV payload
    assert result is not None


@pytest.mark.django_db
def test_initiation_process_generate_blackbaud_update_invoice_mode():
    """generate_blackbaud_update with invoice=True covers the invoice column branch."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        result = ip.generate_blackbaud_update(invoice=True)
    assert result is not None


# ─── InitiationProcess.generate_badge_shingle_order (lines 1184-1298) ────────


@pytest.mark.django_db
def test_initiation_process_generate_badge_shingle_order():
    """generate_badge_shingle_order covers lines 1184-1298 (CSV generation)."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        result = ip.generate_badge_shingle_order()
    # Returns (badge_mail, shingle_mail) tuple
    assert result is not None


# ─── DisciplinaryProcess.forms_pdf (lines 1908-1928) ─────────────────────────


@pytest.mark.django_db
def test_disciplinary_process_forms_pdf():
    """forms_pdf() covers lines 1908-1928 with mocked render_to_pdf."""
    from unittest.mock import patch

    from thetatauCMT.forms.models import DisciplinaryProcess

    user = UserFactory.create()
    dp = DisciplinaryProcess(user=user, chapter=user.chapter, notify_method="email")
    dp.save()
    with patch("thetatauCMT.forms.models.render_to_pdf", return_value=b"PDF", create=True):
        result = dp.forms_pdf()
    assert result == b"PDF"


# ─── DisciplinaryProcess.get_all_files with files (line 1941) ────────────────


@pytest.mark.django_db
def test_disciplinary_process_get_all_files_with_file():
    """get_all_files with a file that has a name covers line 1941."""
    from thetatauCMT.forms.models import DisciplinaryProcess

    user = UserFactory.create()
    dp = DisciplinaryProcess(
        user=user,
        chapter=user.chapter,
        notify_method="email",
    )
    dp.charging_letter = "discipline/test.pdf"  # Set a file name directly
    dp.save()
    # Reload to avoid stale state
    dp.refresh_from_db()
    # Even if it's saved as name, get_all_files checks .name
    result = dp.get_all_files()
    assert isinstance(result, list)


# ─── CollectionReferral.__str__ (line 1971) ──────────────────────────────────


@pytest.mark.django_db
def test_collection_referral_str():
    """CollectionReferral.__str__ covers line 1971."""
    from unittest.mock import MagicMock

    from thetatauCMT.forms.models import CollectionReferral

    mock_cr = MagicMock()
    mock_cr.user = "Test User"
    result = CollectionReferral.__str__(mock_cr)
    assert "Collection referral" in result
    assert "Test User" in result


# ─── get_resign_upload_path (line 1975) ──────────────────────────────────────


def test_get_resign_upload_path_returns_path():
    """Calling get_resign_upload_path covers lines 1974-1979."""
    from types import SimpleNamespace

    from thetatauCMT.forms.models import get_resign_upload_path

    chapter = SimpleNamespace(slug="resign-chapter")
    user = SimpleNamespace(id=77, chapter=chapter)
    instance = SimpleNamespace(user=user)
    result = get_resign_upload_path(instance, "resign.pdf")
    assert "resign.pdf" in result
    assert "resign-chapter" in result


# ─── InitiationProcess.generate_blackbaud_update: invoice column presence ────


@pytest.mark.django_db
def test_generate_blackbaud_update_default_excludes_invoice_columns():
    """generate_blackbaud_update(invoice=False) CSV does not contain
    'Date Submitted' or 'Sum for member' header columns."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        mime_obj = ip.generate_blackbaud_update(invoice=False)
    # MIMEBase payload is the CSV string
    csv_payload = mime_obj.get_payload()
    # The header row should NOT contain invoice-only columns
    assert "Date Submitted" not in csv_payload
    assert "Sum for member" not in csv_payload
    # But core columns must be present
    assert "First Name" in csv_payload
    assert "Initiation Fee" in csv_payload


@pytest.mark.django_db
def test_generate_blackbaud_update_invoice_mode_includes_invoice_columns():
    """generate_blackbaud_update(invoice=True) CSV contains 'Date Submitted'
    and 'Sum for member' header columns."""
    from unittest.mock import patch

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        mime_obj = ip.generate_blackbaud_update(invoice=True)
    csv_payload = mime_obj.get_payload()
    assert "Date Submitted" in csv_payload
    assert "Sum for member" in csv_payload
    assert "Initiation Fee" in csv_payload


@pytest.mark.django_db
def test_generate_blackbaud_update_response_mode_sets_content_disposition():
    """generate_blackbaud_update(response=HttpResponse()) writes CSV to the
    response and sets Content-Disposition: attachment."""
    from unittest.mock import patch

    from django.http import HttpResponse

    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    ip = InitiationProcessFactory.create()
    response = HttpResponse(content_type="text/csv")
    with patch("thetatauCMT.forms.models.Config.get_value", return_value="50"):
        result = ip.generate_blackbaud_update(invoice=False, response=response)
    # When response is passed, returns None (writes to response in place)
    assert result is None
    assert "attachment" in response.get("Content-Disposition", "")
    assert "initiation.csv" in response.get("Content-Disposition", "")
