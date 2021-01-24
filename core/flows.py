from viewflow import flow
from viewflow.flow import views as flow_views
from viewflow.activation import now, Activation, STATUS


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
        return user.has_perm(self.task.owner_permission)

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
                raise ValueError(
                    "Activation metadata is broken {}".format(
                        self.management_form.errors
                    )
                )
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
