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
