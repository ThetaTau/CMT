import factory
from ..models import TaskDate, TaskChapter
from chapters.tests.factories import ChapterFactory


class TaskChapterFactory(factory.django.DjangoModelFactory):
    task = factory.Iterator(TaskDate.objects.all())
    chapter = factory.SubFactory(ChapterFactory)
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")

    # @factory.post_generation
    # def add_submission(self, create, extracted, **kwargs):
    #     """
    #     Test adding a submission
    #     :param create:
    #     :param extracted:
    #     :param kwargs:
    #     :return:
    #     """
    #     submission_type =
    #     submission_id =
    #     submission_object = GenericForeignKey("submission_type", "submission_id")
    #     return

    class Meta:
        model = TaskChapter
