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


@pytest.mark.django_db
def test_get_object_list_status_search_survives_none_task_title(rf, monkeypatch):
    """Regression for #1081.

    Some viewflow nodes (gateways, or views declared without a title) expose
    ``task_title = None``.  ``FilterProcessListView.get_object_list`` used to
    call ``.lower()`` on it directly during a status search, raising
    ``AttributeError: 'NoneType' object has no attribute 'lower'``.  It must now
    fall back to the node ``name`` instead of crashing.
    """
    from types import SimpleNamespace

    from core.flows import FilterProcessListView
    from thetatauCMT.nominations.flows import NominationFlow
    from thetatauCMT.nominations.models import Nomination
    from thetatauCMT.nominations.tests.factories import NominationFactory

    nomination = NominationFactory.create()

    class _ActiveTasks:
        """Stand-in for a non-empty active-task queryset."""

        def __bool__(self):
            return True

        def first(self):
            # flow_task with NO task_title, mimicking a titleless node.
            return SimpleNamespace(flow_task=SimpleNamespace(task_title=None, name="nominee_consent"))

    monkeypatch.setattr(Nomination, "active_tasks", lambda self: _ActiveTasks())

    view = FilterProcessListView()
    view.flow_class = NominationFlow
    view.get_queryset = lambda: Nomination.objects.all()
    # "<chapter>, <status>" search syntax; empty chapter, status="consent".
    view.request = rf.get("/", {"datatable-search[value]": ", consent"})

    result = view.get_object_list()

    # No crash, and the node name ("nominee_consent") satisfies the status search.
    assert nomination.pk in list(result.values_list("pk", flat=True))


@pytest.mark.django_db
@pytest.mark.parametrize("owner_permission", [None, ""])
def test_noassign_activation_has_perm_allows_when_no_task_permission(owner_permission):
    """Regression for #1075.

    ``AlumniExclusionFlow.review`` (the "RD Review" node) is a ``NoAssignView``
    declared WITHOUT a ``.Permission()``, so its task ``owner_permission`` is
    empty.  ``NoAssignActivation.has_perm`` used to call
    ``user.has_perm(None)``, which returns ``False`` for every non-superuser —
    so a regional director / national officer clicking the review link (shown to
    them, because ``can_execute`` returns ``True``) hit an uncaught
    ``PermissionDenied``.  With no task permission configured, ``has_perm`` must
    now defer to the view's own access control and return ``True``.
    """
    from types import SimpleNamespace

    from core.flows import NoAssignActivation
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory.create()  # non-superuser
    assert user.is_superuser is False
    # Sanity check that this is exactly the branch that used to fail.
    assert user.has_perm(owner_permission) is False

    activation = NoAssignActivation()
    activation.task = SimpleNamespace(owner_permission=owner_permission)
    assert activation.has_perm(user) is True


@pytest.mark.django_db
def test_noassign_activation_has_perm_enforces_configured_permission():
    """A configured task permission is still enforced (central-office nodes).

    The invoice/review nodes on the initiation, pledge, and pledge-program
    flows declare ``.Permission("auth.central_office")``; the #1075 fix must not
    relax those — ``has_perm`` still delegates to ``user.has_perm`` when an
    ``owner_permission`` is set.
    """
    from types import SimpleNamespace

    from core.flows import NoAssignActivation
    from thetatauCMT.users.tests.factories import UserFactory

    activation = NoAssignActivation()
    activation.task = SimpleNamespace(owner_permission="auth.central_office")

    without_perm = UserFactory.create()  # non-superuser, lacks the permission
    assert activation.has_perm(without_perm) is False

    superuser = UserFactory.create(is_superuser=True)  # has every permission
    assert activation.has_perm(superuser) is True
