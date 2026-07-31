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


# ---------------------------------------------------------------------------
# get_task_url — stale viewflow node state (#952)
# ---------------------------------------------------------------------------


def test_get_task_url_survives_missing_owner_permission_obj(rf):
    """Regression for #952.

    A stale DB task can carry an ``owner_permission`` while its flow node was
    later redefined WITHOUT a ``.Permission()``.  viewflow's ``PermissionMixin``
    only sets ``self._owner_permission_obj`` inside ``.Permission()``, so
    ``View.can_assign`` then reads an unset attribute and raises
    ``AttributeError: 'View' object has no attribute '_owner_permission_obj'``.
    ``FilterProcessListView.get_task_url`` only builds a process-list link, so it
    must degrade to an empty string instead of 500ing the whole listing.
    """
    from types import SimpleNamespace

    from core.flows import FilterProcessListView

    class _StaleFlowTask:
        def get_task_url(self, *args, **kwargs):
            raise AttributeError("'View' object has no attribute '_owner_permission_obj'")

    task = SimpleNamespace(flow_task=_StaleFlowTask())

    view = FilterProcessListView()
    request = rf.get("/")
    request.user = SimpleNamespace()
    request.resolver_match = SimpleNamespace(namespace="viewflow:forms:disciplinaryprocess")
    view.request = request

    assert view.get_task_url(task) == ""


def test_get_task_url_survives_noreversematch(rf):
    """A renamed/removed task URL (NoReverseMatch) also degrades to no link (#952)."""
    from types import SimpleNamespace

    from django.urls import NoReverseMatch

    from core.flows import FilterProcessListView

    class _StaleFlowTask:
        def get_task_url(self, *args, **kwargs):
            raise NoReverseMatch("reverse for a renamed task node failed")

    task = SimpleNamespace(flow_task=_StaleFlowTask())

    view = FilterProcessListView()
    request = rf.get("/")
    request.user = SimpleNamespace()
    request.resolver_match = SimpleNamespace(namespace="viewflow:forms:disciplinaryprocess")
    view.request = request

    assert view.get_task_url(task) == ""


# ---------------------------------------------------------------------------
# Site-wide /workflow/ listings — stale viewflow node state (#952)
# ---------------------------------------------------------------------------


def _stale_queue_view(rf, exc):
    """Build a GuardedAllQueueListView whose single task raises ``exc`` from
    ``flow_task.get_task_url`` (the ``can_assign`` stale-node crash)."""
    from types import SimpleNamespace

    from core.flows import GuardedAllQueueListView

    flow_class = object()  # opaque registry key

    class _StaleFlowTask:
        def get_task_url(self, *args, **kwargs):
            raise exc

    task = SimpleNamespace(
        flow_task=_StaleFlowTask(),
        process=SimpleNamespace(flow_class=flow_class),
    )

    view = GuardedAllQueueListView()
    view.ns_map = {flow_class: "disciplinaryprocess"}
    request = rf.get("/")
    request.user = SimpleNamespace(is_anonymous=False)
    request.resolver_match = SimpleNamespace(namespace="viewflow")
    view.request = request
    return view, task


def test_queue_get_task_url_survives_missing_owner_permission_obj(rf):
    """Regression for the ``/workflow/queue/`` 500 (same root cause as #952).

    The site-wide queue (``GuardedAllQueueListView``) iterates NEW unassigned
    tasks across every flow and reaches ``View.can_assign``, which reads the
    node's ``_owner_permission_obj``.  A stale task whose node lost its
    ``.Permission()`` makes that read raise ``AttributeError``.  The queue must
    degrade the bad row to no link instead of 500ing the whole page.
    """
    exc = AttributeError("'View' object has no attribute '_owner_permission_obj'")
    view, task = _stale_queue_view(rf, exc)
    assert view.get_task_url(task) == ""


def test_queue_get_task_url_survives_noreversematch(rf):
    """A renamed/removed task URL (NoReverseMatch) also degrades to no link."""
    from django.urls import NoReverseMatch

    view, task = _stale_queue_view(rf, NoReverseMatch("reverse for a renamed task node failed"))
    assert view.get_task_url(task) == ""


# ---------------------------------------------------------------------------
# complete_activation — concurrent/duplicate submit (#980)
# ---------------------------------------------------------------------------


def test_complete_activation_returns_true_on_success():
    """complete_activation completes the task and reports success."""
    from types import SimpleNamespace

    from core.flows import complete_activation

    calls = []
    activation = SimpleNamespace(done=lambda: calls.append("done"))
    assert complete_activation(activation) is True
    assert calls == ["done"]


def test_complete_activation_swallows_transition_not_allowed():
    """Regression for #980.

    A concurrent/duplicate submit of the same task node makes
    ``Activation.done()`` -> ``activate_next()`` raise ``TransitionNotAllowed``
    (the following task already exists, so ``all_leading_canceled`` is False).
    ``complete_activation`` must swallow it and report the task was already
    completed instead of 500ing.
    """
    from types import SimpleNamespace

    from viewflow.fsm import TransitionNotAllowed

    from core.flows import complete_activation

    def _raise():
        raise TransitionNotAllowed("Transition conditions have not been met for method 'activate_next'")

    activation = SimpleNamespace(done=_raise)
    assert complete_activation(activation) is False
