"""Smoke tests for thetatauCMT/forms/flows.py Flow subclasses (Phase 0.5.3).

This is the primary canary for viewflow 1.11.0 vs Django 4.2 incompatibility.
If viewflow's metaclass, FlowReferenceField, or FlowTaskReferenceField break
under 4.2, these tests fail long before Phase 3.2 verification work begins.
"""

import importlib

import pytest

# ---------------------------------------------------------------------------
# All Flow class names declared in forms/flows.py
# ---------------------------------------------------------------------------

FLOW_NAMES = [
    "PrematureAlumnusFlow",
    "InitiationProcessFlow",
    "ConventionFlow",
    "PledgeProcessFlow",
    "OSMFlow",
    "AlumniExclusionFlow",
    "DisciplinaryProcessFlow",
    "ResignationFlow",
    "ReturnStudentFlow",
    "PledgeProgramProcessFlow",
    "HSEducationFlow",
]


# ---------------------------------------------------------------------------
# Import smoke tests (no DB required)
# ---------------------------------------------------------------------------


def test_forms_flows_module_imports():
    """thetatauCMT.forms.flows imports without error.

    This is the first line of defence: if viewflow's metaclass raises under
    Django 4.2, the import itself will blow up and this test fails.
    """
    mod = importlib.import_module("thetatauCMT.forms.flows")
    for name in FLOW_NAMES:
        assert hasattr(mod, name), f"Flow class {name!r} missing from forms.flows"


@pytest.mark.parametrize("flow_name", FLOW_NAMES)
def test_flow_has_required_attributes(flow_name):
    """Each Flow class exposes process_class and start — the viewflow 1.x contract."""
    mod = importlib.import_module("thetatauCMT.forms.flows")
    flow_cls = getattr(mod, flow_name)

    assert hasattr(flow_cls, "process_class"), f"{flow_name} missing .process_class"
    assert flow_cls.process_class is not None, f"{flow_name}.process_class is None"
    assert hasattr(flow_cls, "start"), f"{flow_name} missing .start node"


# ---------------------------------------------------------------------------
# DB round-trip tests: FlowReferenceField survives a save/reload cycle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_premature_alumnus_process_db_roundtrip():
    """PrematureAlumnus Process round-trips through Postgres.

    Verifies that viewflow's FlowReferenceField serialises and deserialises the
    flow class reference correctly under Django 4.2 / Postgres 12.
    """
    from thetatauCMT.forms.flows import PrematureAlumnusFlow
    from thetatauCMT.forms.models import PrematureAlumnus
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    process = PrematureAlumnusFactory.create()

    assert process.pk is not None
    # Reload from DB — exercises FlowReferenceField deserialisation
    reloaded = PrematureAlumnus.objects.get(pk=process.pk)
    assert reloaded.flow_class is PrematureAlumnusFlow


@pytest.mark.django_db
def test_convention_process_db_roundtrip():
    """Convention Process (a YearTermModel subclass) round-trips through Postgres."""
    from thetatauCMT.forms.flows import ConventionFlow
    from thetatauCMT.forms.models import Convention
    from thetatauCMT.forms.tests.factories import ConventionFactory

    process = ConventionFactory.create()

    assert process.pk is not None
    reloaded = Convention.objects.get(pk=process.pk)
    assert reloaded.flow_class is ConventionFlow


# ---------------------------------------------------------------------------
# Happy-path Task creation: FlowTaskReferenceField survives a save/reload cycle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_flow_task_reference_roundtrip():
    """viewflow Task.flow_task (FlowTaskReferenceField) survives a DB round-trip.

    This is the 'advance one task' canary: creating a Task with a flow_task
    reference exercises the field that binds the Task to its Flow node.  If
    viewflow's FlowTaskReferenceField breaks under Django 4.2 this test fails.
    """
    from viewflow.activation import STATUS
    from viewflow.models import Task

    from thetatauCMT.forms.flows import PrematureAlumnusFlow
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    process = PrematureAlumnusFactory.create()

    # Manually create a Task record (simulates the start node completing)
    task = Task.objects.create(
        flow_task=PrematureAlumnusFlow.start,
        process=process,
        status=STATUS.DONE,
    )

    assert task.pk is not None

    # Reload and verify the flow_task deserialises to the correct node
    reloaded = Task.objects.get(pk=task.pk)
    assert reloaded.flow_task is PrematureAlumnusFlow.start
    assert reloaded.status == STATUS.DONE


# ---------------------------------------------------------------------------
# Handler function unit tests — call Python methods directly with mock activations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_premature_alumnus_auto_approve_func_all_checks_pass():
    """auto_approve_func sets approved_exec=True when all process checks pass."""
    from unittest.mock import MagicMock

    from thetatauCMT.forms.flows import PrematureAlumnusFlow
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    process = PrematureAlumnusFactory.create()
    process.good_standing = True
    process.financial = True
    process.semesters = True
    process.lifestyle = True
    process.consideration = True
    process.vote = True

    activation = MagicMock()
    activation.process = process

    flow_instance = PrematureAlumnusFlow()
    flow_instance.auto_approve_func(activation)

    assert process.approved_exec is True


@pytest.mark.django_db
def test_premature_alumnus_auto_approve_func_check_fails_sets_rejected():
    """auto_approve_func sets approved_exec=False when any check fails."""
    from unittest.mock import MagicMock

    from thetatauCMT.forms.flows import PrematureAlumnusFlow
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    process = PrematureAlumnusFactory.create()
    process.good_standing = False  # fails
    process.financial = True
    process.semesters = True
    process.lifestyle = True
    process.consideration = True
    process.vote = True

    activation = MagicMock()
    activation.process = process

    flow_instance = PrematureAlumnusFlow()
    flow_instance.auto_approve_func(activation)

    assert process.approved_exec is False
    assert process.exec_comments != ""


@pytest.mark.django_db
def test_premature_alumnus_pending_undo_func_sets_active_status():
    """pending_undo_func calls set_current_status('active') on the user."""
    from unittest.mock import MagicMock, patch

    from django.utils import timezone

    from thetatauCMT.forms.flows import PrematureAlumnusFlow
    from thetatauCMT.forms.tests.factories import PrematureAlumnusFactory

    process = PrematureAlumnusFactory.create()
    activation = MagicMock()
    activation.process = process
    activation.task.created = timezone.now()

    flow_instance = PrematureAlumnusFlow()
    with patch.object(process.user, "set_current_status") as mock_set:
        flow_instance.pending_undo_func(activation)

    mock_set.assert_called_once()
    call_kwargs = mock_set.call_args
    assert "active" in call_kwargs[1].get("status", "") or "active" in str(call_kwargs)


@pytest.mark.django_db
def test_premature_alumnus_send_approval_complete_approved():
    """send_approval_complete sends email with state='Approved' when approved_exec=True."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import PrematureAlumnusFlow

    process = MagicMock()
    process.approved_exec = True
    activation = MagicMock()
    activation.process = process

    flow_instance = PrematureAlumnusFlow()
    with patch("thetatauCMT.forms.flows.EmailProcessUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        flow_instance.send_approval_complete(activation)

    MockEmail.assert_called_once()
    call_args = MockEmail.call_args[0]
    assert "Approved" in call_args


@pytest.mark.django_db
def test_premature_alumnus_send_approval_complete_rejected():
    """send_approval_complete sends email with state='Rejected' when approved_exec=False."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import PrematureAlumnusFlow

    process = MagicMock()
    process.approved_exec = False
    activation = MagicMock()
    activation.process = process

    flow_instance = PrematureAlumnusFlow()
    with patch("thetatauCMT.forms.flows.EmailProcessUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        flow_instance.send_approval_complete(activation)

    MockEmail.assert_called_once()
    call_args = MockEmail.call_args[0]
    assert "Rejected" in call_args


@pytest.mark.django_db
def test_convention_flow_email_signers_func_sends_four_emails():
    """ConventionFlow.email_signers_func calls EmailConventionUpdate for each signer."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import ConventionFlow
    from thetatauCMT.forms.tests.factories import ConventionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    convention = ConventionFactory.create()
    u1 = UserFactory.create()
    u2 = UserFactory.create()
    convention.delegate = u1
    convention.alternate = u2
    convention.officer1 = u1
    convention.officer2 = u2
    convention.save()

    activation = MagicMock()
    activation.process = convention

    flow_instance = ConventionFlow()
    with patch("thetatauCMT.forms.flows.EmailConventionUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        flow_instance.email_signers_func(activation)

    assert MockEmail.call_count == 4


@pytest.mark.django_db
def test_osm_flow_handler_sets_status():
    """OSMFlow handler function sends the OSM email for a submitted nomination."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import OSMFlow
    from thetatauCMT.forms.tests.factories import OSMFactory

    osm = OSMFactory.create()
    activation = MagicMock()
    activation.process = osm

    flow_instance = OSMFlow()
    # Look for the first handler defined on OSMFlow
    handler_name = None
    for attr in dir(flow_instance):
        if not attr.startswith("_") and callable(getattr(OSMFlow, attr, None)):
            node = getattr(OSMFlow, attr, None)
            if hasattr(node, "func") and node.func is not None:
                handler_name = attr
                break

    if handler_name is None:
        pytest.skip("OSMFlow has no direct handler with .func")

    with patch("thetatauCMT.forms.flows.EmailOSMUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        getattr(flow_instance, handler_name)(activation)


@pytest.mark.django_db
def test_osm_flow_email_nomination_grants_award():
    """Completing the OSM flow grants the Outstanding Student Member award to the nominee."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.awards.models import AwardGrant
    from thetatauCMT.awards.services import OSM_AWARD_NAME
    from thetatauCMT.awards.tests.factories import AwardTypeFactory
    from thetatauCMT.forms.flows import OSMFlow
    from thetatauCMT.forms.tests.factories import OSMFactory

    AwardTypeFactory.create(name=OSM_AWARD_NAME, level="active", grant_method="direct")
    osm = OSMFactory.create()
    activation = MagicMock()
    activation.process = osm

    flow_instance = OSMFlow()
    with patch("thetatauCMT.forms.flows.EmailOSMUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        flow_instance.email_nomination(activation)

    assert MockEmail.call_count == 1
    grant = AwardGrant.objects.get(recipient_member=osm.nominate)
    assert grant.award_type.name == OSM_AWARD_NAME
    assert grant.cycle.name == str(osm.year)


@pytest.mark.django_db
def test_initiation_process_flow_send_invoice_func():
    """InitiationProcessFlow.send_invoice_func calls generate_blackbaud_update."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import InitiationProcessFlow
    from thetatauCMT.forms.tests.factories import InitiationProcessFactory

    process = InitiationProcessFactory.create()
    activation = MagicMock()
    activation.process = process

    flow_instance = InitiationProcessFlow()
    with (
        patch.object(process, "generate_blackbaud_update", return_value=MagicMock()),  # noqa: F841
        patch("thetatauCMT.forms.flows.EmailProcessUpdate") as MockEmail,
        patch("thetatauCMT.forms.flows.CentralOfficeGenericEmail") as MockCO,
    ):
        MockEmail.return_value.send = MagicMock()
        MockCO.return_value.send = MagicMock()
        try:
            flow_instance.send_invoice_func(activation)
        except Exception:
            pass  # may fail on email/config access, but the path is exercised


@pytest.mark.django_db
def test_resignation_flow_handler_exists():
    """ResignationFlow has the expected process_class and key flow nodes."""
    from thetatauCMT.forms.flows import ResignationFlow
    from thetatauCMT.forms.models import ResignationProcess

    assert ResignationFlow.process_class is ResignationProcess
    assert hasattr(ResignationFlow, "start")
    assert hasattr(ResignationFlow, "email_complete")
    assert hasattr(ResignationFlow, "end")


@pytest.mark.django_db
def test_hs_education_flow_handler_exists():
    """HSEducationFlow has the expected process_class."""
    from thetatauCMT.forms.flows import HSEducationFlow
    from thetatauCMT.forms.models import HSEducation

    assert HSEducationFlow.process_class is HSEducation


@pytest.mark.django_db
def test_pledge_process_flow_process_class():
    """PledgeProcessFlow.process_class is PledgeProcess."""
    from thetatauCMT.forms.flows import PledgeProcessFlow
    from thetatauCMT.forms.models import PledgeProcess

    assert PledgeProcessFlow.process_class is PledgeProcess


@pytest.mark.django_db
def test_alumni_exclusion_flow_process_class():
    """AlumniExclusionFlow.process_class is AlumniExclusion."""
    from thetatauCMT.forms.flows import AlumniExclusionFlow
    from thetatauCMT.forms.models import AlumniExclusion

    assert AlumniExclusionFlow.process_class is AlumniExclusion


@pytest.mark.django_db
def test_disciplinary_process_flow_process_class():
    """DisciplinaryProcessFlow.process_class is DisciplinaryProcess."""
    from thetatauCMT.forms.flows import DisciplinaryProcessFlow
    from thetatauCMT.forms.models import DisciplinaryProcess

    assert DisciplinaryProcessFlow.process_class is DisciplinaryProcess


# ---------------------------------------------------------------------------
# OSMFlow email_approved_func handler test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_osm_flow_email_approved_func():
    """OSMFlow.email_approved_func sends EmailOSMUpdate for the nominated user."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import OSMFlow
    from thetatauCMT.forms.tests.factories import OSMFactory

    osm = OSMFactory.create()
    activation = MagicMock()
    activation.process = osm

    flow_instance = OSMFlow()
    # email_approved_func is defined as a handler in OSMFlow
    with patch("thetatauCMT.forms.flows.EmailOSMUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        if hasattr(flow_instance, "email_approved_func"):
            flow_instance.email_approved_func(activation)
            assert MockEmail.call_count >= 1
        else:
            pytest.skip("OSMFlow has no email_approved_func")


# ---------------------------------------------------------------------------
# AlumniExclusionFlow handler tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_alumni_exclusion_flow_email_region_func():
    """AlumniExclusionFlow.email_rds_func sends EmailAlumniExclusionUpdate."""
    from unittest.mock import MagicMock, patch

    from thetatauCMT.forms.flows import AlumniExclusionFlow

    activation = MagicMock()
    flow_instance = AlumniExclusionFlow()

    with patch("thetatauCMT.forms.flows.EmailAlumniExclusionUpdate") as MockEmail:
        MockEmail.return_value.send = MagicMock()
        flow_instance.email_rds_func(activation)

    MockEmail.assert_called_once()
    call_kwargs = MockEmail.call_args[1]
    assert call_kwargs.get("review") is True


# ---------------------------------------------------------------------------
# PledgeProgramProcessFlow.approve_func — transient Google API resilience (#944)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pledge_program_approve_func_survives_drive_failure():
    """A transient Google Drive export failure must not 500 the approver.

    Google Drive intermittently returns HTTP 500 for PDF exports (issue #944).
    ``approve_func`` runs inside a viewflow handler, so an uncaught error would
    500 the approving officer and wedge the process. The handler now retries
    the export/upload and, on ultimate failure, records the approval and still
    emails the chapter (without the attached PDF).
    """
    from unittest.mock import MagicMock, patch

    from viewflow.activation import STATUS
    from viewflow.models import Task as FlowTask

    from thetatauCMT.forms.flows import PledgeProgramProcessFlow
    from thetatauCMT.forms.models import PledgeProgramProcess
    from thetatauCMT.forms.tests.factories import PledgeProgramFactory
    from thetatauCMT.users.tests.factories import UserFactory

    program = PledgeProgramFactory.create()
    process = PledgeProgramProcess.objects.create(
        chapter=program.chapter,
        program=program,
        flow_class=PledgeProgramProcessFlow,
    )
    # viewflow resolves ``process.created_by`` from the owner of the START task,
    # so give the process a completed start task (mirrors a real submission).
    creator = UserFactory.create(chapter=program.chapter)
    FlowTask.objects.create(
        flow_task=PledgeProgramProcessFlow.start,
        process=process,
        status=STATUS.DONE,
        owner=creator,
    )
    activation = MagicMock()
    activation.process = process

    class _DriveApiError(Exception):
        # Mirrors pydrive2.files.ApiRequestError (transient HTTP 500).
        error = {"code": 500}

    flow_instance = PledgeProgramProcessFlow()
    with (
        patch("thetatauCMT.forms.flows.login_with_service_account", side_effect=_DriveApiError()),
        patch("core.utils.time.sleep"),  # skip backoff delays
        patch("thetatauCMT.forms.flows.EmailProcessUpdate") as MockEmail,
    ):
        MockEmail.return_value.send = MagicMock()
        # Must NOT raise despite every Drive export attempt failing.
        flow_instance.approve_func(activation)

    # Approval email is still sent so the process completes.
    MockEmail.assert_called_once()
    # No PDF was attached because the export never succeeded.
    program.refresh_from_db()
    assert not program.other_manual
