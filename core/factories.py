import factory
from viewflow.models import Task
from users.tests.factories import UserFactory


class TaskFactory(factory.django.DjangoModelFactory):
    """
    From: https://github.com/darahsten/unittest_viewflow
    Use this factory like:
        process = SampleProcessFactory()
        task_owner = UserFactory()
        task = TaskFactory(process=process,
                           flow_task=SampleFlow.task_name,
                           owner=task_owner)
        url = reverse('viewflow:sampleflow:task_name',
                      kwargs={'process_pk':process.pk, 'task_pk': task.pk})
    """

    # in child class should be factory.SubFactory(SampleProcessFactory)
    process = None
    # in child class should be SampleFlow.start
    flow_task = None

    # It is important that you supply this owner if you want to
    # reference it in the views.
    owner = factory.SubFactory(UserFactory)
    token = "START"

    class Meta:
        model = Task

    @factory.post_generation
    def run_activations(self, create, extracted, **kwargs):
        # This causes the necessary status transitions to
        # make the task executable
        activation = self.activate()

        # this if condition implies that this factory can be
        # used to generate also a flow.Start task which
        # does not have the assign method
        if hasattr(activation, "assign"):
            activation.assign()  # This should require that you have set the task owner to work
