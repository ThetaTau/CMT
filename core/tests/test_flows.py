"""Smoke tests for core/flows.py helper classes (Phase 0.5.3).

Canary: if viewflow 1.11.0 is broken under Django 4.2, the imports below
surface it immediately — before any Phase 3.2 verification work begins.
"""

import pytest


def test_core_flows_module_imports():
    """core.flows imports cleanly — verifies viewflow 1.x base view classes load."""
    import core.flows as mod

    assert hasattr(mod, "AutoAssignUpdateProcessView")
    assert hasattr(mod, "NoAssignActivation")
    assert hasattr(mod, "NoAssignView")
    assert hasattr(mod, "FilterProcessListView")
    assert hasattr(mod, "FilterableFlowViewSet")
    assert hasattr(mod, "register_factory")
    assert hasattr(mod, "cancel_process")


def test_viewflow_base_classes_importable():
    """Core viewflow 1.x public API remains importable under Django 4.2."""
    from viewflow import flow  # noqa: F401
    from viewflow.activation import STATUS
    from viewflow.base import Flow  # noqa: F401
    from viewflow.models import Process, Task  # noqa: F401

    # STATUS values used throughout core/flows.py
    assert STATUS.NEW
    assert STATUS.DONE
    assert STATUS.CANCELED


def test_viewflow_frontend_importable():
    """viewflow.frontend imports cleanly (used by FilterableFlowViewSet)."""
    from viewflow import frontend  # noqa: F401
    from viewflow.frontend.views import ProcessListView
    from viewflow.frontend.viewset import FlowViewSet

    assert FlowViewSet is not None
    assert ProcessListView is not None


@pytest.mark.django_db
def test_process_and_task_models_accessible():
    """viewflow Process/Task ORM managers are queryable under Django 4.2."""
    from viewflow.models import Process, Task

    # Just calling .none() exercises the model manager without touching data
    assert Process.objects.none().count() == 0
    assert Task.objects.none().count() == 0
