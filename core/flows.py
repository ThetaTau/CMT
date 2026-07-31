import datetime
import re

from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe
from material.frontend import frontend_url
from viewflow import flow, frontend
from viewflow.activation import STATUS, Activation, now
from viewflow.compat import _
from viewflow.flow import views as flow_views
from viewflow.flow.views.mixins import FlowListMixin
from viewflow.frontend.views import AllArchiveListView, AllQueueListView, AllTaskListView, ProcessListView
from viewflow.frontend.viewset import FlowViewSet, FrontendViewSet
from viewflow.fsm import TransitionNotAllowed


def complete_activation(activation):
    """Complete a viewflow task/start activation, tolerating a task that was
    already completed by a concurrent or duplicate submit.

    ``Activation.done()`` marks the task finished and then calls
    ``activate_next()``, whose ``all_leading_canceled`` condition raises
    ``TransitionNotAllowed`` when the following task already exists -- i.e. the
    same task node was submitted twice and a first (possibly concurrent) request
    already advanced the process (#980, disciplinary "Submit Form 2"). viewflow's
    task dispatch already redirects gracefully for a *sequential* re-submit
    (``prepare.can_proceed()`` is False once the task is DONE); this guards the
    *concurrent* race that slips past that check.

    Returns ``True`` when this call advanced the process, ``False`` when the task
    had already been completed.
    """
    try:
        activation.done()
    except TransitionNotAllowed:
        return False
    return True


class AutoAssignUpdateProcessView(flow_views.UpdateProcessView):
    """
    This class will automatically assign the task to the user that completes it.
    """

    def dispatch(self, request, **kwargs):
        """Lock the process, initialize `self.activation`, check permission and execute."""
        result = super().dispatch(request, **kwargs)
        if not self.activation.task.owner:
            self.activation.task.owner = request.user
        if self.activation.task.status == STATUS.DONE:
            self.activation.task.save()
        return result


class NoAssignActivation(flow.nodes.ManagedViewActivation):
    """
    This Activation will not assign or unassign users to tasks
    Also will check permission based on permission to view
    """

    @Activation.status.transition(source=STATUS.NEW, target=STATUS.ASSIGNED)
    def assign(self, user=None):
        """Assign user to the task."""
        pass

    def has_perm(self, user):
        owner_permission = self.task.owner_permission
        if not owner_permission:
            # No task-level permission is configured for this node (e.g.
            # ``AlumniExclusionFlow.review`` — the "RD Review" node, which,
            # unlike the central-office invoice/review nodes, has no
            # ``.Permission()``). Defer to the view's own access control
            # (``LoginRequiredMixin``/``NatOfficerRequiredMixin``) instead of
            # calling ``user.has_perm(None)``, which returns False for every
            # non-superuser and raised an uncaught ``PermissionDenied``
            # (issue #1075) even though ``NoAssignView.can_execute`` shows the
            # task link to them. Mirrors viewflow's ``View.can_execute``, where
            # a task with no ``owner_permission`` and no owner is executable.
            return True
        return user.has_perm(owner_permission)

    @Activation.status.transition(source=STATUS.NEW, target=STATUS.PREPARED)
    def prepare(self, data=None, user=None):
        """
        Initialize start task for execution.

        No db changes performed. It is safe to call it on GET requests.
        """
        if self.task.started is None:
            self.task.started = now()
        if user:
            self.task.owner = user

        management_form_class = self.get_management_form_class()
        self.management_form = management_form_class(data=data, instance=self.task)

        if data:
            if not self.management_form.is_valid():
                raise ValueError("Activation metadata is broken {}".format(self.management_form.errors))
            self.task = self.management_form.save(commit=False)


class NoAssignView(flow.View):
    activation_class = NoAssignActivation

    @property
    def assign_view(self):
        return self.view

    def can_unassign(self, user, task):
        return True

    def can_assign(self, user, task):
        return True

    def can_execute(self, user, task):
        return True


def register_factory(viewset_class):
    def decorator(function):
        return frontend.register(function, viewset_class=viewset_class)

    return decorator


class FilterProcessListView(ProcessListView, FlowListMixin):
    template_name = "forms/process_list.html"
    list_display = [
        "current_task",
        "user",
        "chapter",
        "created",
        "finished",
    ]
    datatable_config = {"searching": True}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_titles = []
        for var_name in dir(self.flow_class):
            var = getattr(self.flow_class, var_name)
            if hasattr(var, "task_title"):
                task_title = var.task_title
                if task_title:
                    task_titles.append(task_title)
        context["task_titles"] = task_titles
        return context

    def chapter(self, process):
        chapter = "unknown"
        if hasattr(process, "chapter"):
            chapter = process.chapter
        elif hasattr(process, "user"):
            chapter = process.user.chapter
        elif getattr(process, "nominee_id", None):
            chapter = process.nominee.chapter
        return chapter

    chapter.short_description = "Chapter"

    def user(self, process):
        user = "N/A"
        if hasattr(process, "user"):
            user = process.user
        elif hasattr(process, "nominee_display"):
            user = process.nominee_display
        elif hasattr(process, "nominate"):
            user = process.nominate
        elif hasattr(process, "delegate"):
            user = f"{process.delegate} and {process.alternate}"
        return user

    user.short_description = "User"

    def get_object_list(self):
        """Create prepared queryset for datatables view."""
        queryset = self.get_queryset()
        search = self.request.GET.get("datatable-search[value]", False)
        if search:
            search_chapter = search
            search_status = False
            if "invoice:" in search:
                matches = re.findall(r"invoice:\s*(\d*)", search)
                search = re.sub(r"invoice:\s*(\d*)", "", search)
                search_chapter = search
                invoice_number = matches[0]
                queryset = queryset.filter(Q(invoice__contains=invoice_number))
            if "," in search:
                search_chapter, search_status = search.split(",", 1)
                search_chapter = search_chapter.strip()
                search_status = search_status.strip().lower()
            if not search_chapter:
                search_chapter = False
            if not search_status:
                search_status = False
            if search_chapter:
                # Search for chapter or user
                extra = {}
                filter_key = "chapter__"
                if hasattr(queryset.model, "user"):
                    filter_key = "user__chapter__"
                    extra = {"user__name__icontains": search_chapter}
                if "-" in search_chapter:
                    search_chapter = search_chapter.replace("-", "")
                    filter_key = filter_key + "name__iexact"
                else:
                    filter_key = filter_key + "name__icontains"
                queryset = queryset.filter(Q(**{filter_key: search_chapter}) | Q(**extra))
            if search_status:
                processes = []
                for process in queryset:
                    title = "complete"
                    active_tasks = process.active_tasks()
                    if active_tasks:
                        flow_task = active_tasks.first().flow_task
                        if flow_task:
                            # Some flow nodes (gateways, or views defined without a
                            # title) have task_title=None; fall back to the node name.
                            title = (flow_task.task_title or flow_task.name or "n/a").lower()
                        else:
                            title = "n/a"
                    if search_status in title:
                        processes.append(process.pk)
                queryset = queryset.model.objects.filter(pk__in=processes)
        return queryset

    def current_task(self, process):
        if process.finished is None:
            task = process.active_tasks().first()
            if task:
                flow_task = task.flow_task
                summary = "n/a"
                if flow_task:
                    summary = flow_task.task_title or flow_task.name
                task_url = frontend_url(self.request, self.get_task_url(task), back_link="here")
                return mark_safe('<a href="{}">{}</a>'.format(task_url, summary))
        process_url = self.get_process_url(process)
        return mark_safe('<a href="{}">Complete</a>'.format(process_url))

    current_task.short_description = _("Current Task")

    def get_process_url(self, process, url_type="detail"):
        namespace = self.request.resolver_match.namespace
        return reverse("{}:{}".format(namespace, url_type), args=[process.pk])

    def get_task_url(self, task, url_type=None):
        namespace = self.request.resolver_match.namespace
        if task.flow_task:
            try:
                return task.flow_task.get_task_url(
                    task,
                    url_type=url_type if url_type else "guess",
                    user=self.request.user,
                    namespace=namespace,
                )
            except (AttributeError, NoReverseMatch):
                # A stale task can reference viewflow node state that no longer
                # matches the current flow definition -- e.g. the DB task has an
                # ``owner_permission`` but the node was later redefined without a
                # ``.Permission()``, so viewflow's ``View.can_assign`` reads an
                # unset ``self._owner_permission_obj`` (#952) -- or a task URL
                # name was renamed (NoReverseMatch). This method only builds the
                # process-list link, so degrade to no link instead of 500ing the
                # whole listing.
                return ""
        else:
            return ""


class FilterableFlowViewSet(FlowViewSet):
    process_list_view = [r"^$", FilterProcessListView.as_view(), "index"]


class _ResilientTaskUrlMixin:
    """Degrade a task link to no link instead of 500ing the whole listing when a
    stale DB task references viewflow node state that no longer matches the flow
    definition.

    The site-wide ``/workflow/`` listings iterate every registered flow's tasks
    and call ``FlowListMixin.get_task_url`` -> ``View.can_assign``, which reads
    ``self._owner_permission_obj``.  ``PermissionMixin`` only sets that attribute
    inside ``.Permission()``; a task whose ``owner_permission`` column was
    persisted while its node still had a ``.Permission()`` -- but whose node was
    later redefined without one -- makes ``can_assign`` read an unset attribute
    and raise ``AttributeError`` (a renamed task url raises ``NoReverseMatch``).
    Mirrors ``FilterProcessListView.get_task_url`` (#952) for the queue/inbox/
    archive views (``/workflow/queue/`` lists NEW unassigned tasks and is the
    one that actually reaches ``can_assign``).
    """

    def get_task_url(self, task, url_type=None):
        try:
            return super().get_task_url(task, url_type=url_type)
        except (AttributeError, NoReverseMatch):
            return ""


class GuardedAllTaskListView(_ResilientTaskUrlMixin, AllTaskListView):
    pass


class GuardedAllQueueListView(_ResilientTaskUrlMixin, AllQueueListView):
    pass


class GuardedAllArchiveListView(_ResilientTaskUrlMixin, AllArchiveListView):
    pass


class GuardedFrontendViewSet(FrontendViewSet):
    """Frontend site viewset wired to the resilient list views so the workflow
    queue (``/workflow/queue/``) survives stale task rows (#952).  Selected via
    ``core.apps.GuardedViewflowFrontendConfig`` in ``INSTALLED_APPS``.
    """

    inbox_view_class = GuardedAllTaskListView
    queue_view_class = GuardedAllQueueListView
    archive_view_class = GuardedAllArchiveListView


def cancel_process(process):
    active_tasks = process.task_set.exclude(status__in=[STATUS.DONE, STATUS.CANCELED])
    for task in active_tasks:
        print(f"Cancelling process task: {task.flow_task.name} for process: {process.flow_class.process_title}")
        activation = task.activate()
        if hasattr(activation, "unassign"):
            activation.unassign()
        activation.cancel()
    process.status = STATUS.CANCELED
    process.finished = datetime.datetime.now(datetime.timezone.utc)
    process.save()
