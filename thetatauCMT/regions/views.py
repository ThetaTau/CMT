from collections import defaultdict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.db import models
from django.views.generic import DetailView, ListView, RedirectView
import django_tables2 as tables
from django_tables2.utils import A
from core.views import OfficerMixin
from .models import Region
from tasks.models import TaskDate
from .tables import RegionChapterTaskTable


class RegionDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = Region
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_chapters_tasks = {task.pk: defaultdict(lambda: 0) for task in TaskDate.objects.all()}
        [all_chapters_tasks[task.id].update(
            {'task_name': task.task.name,
             'task_owner': task.task.owner,
             'school_type': task.school_type,
             'date': task.date})
            for task in TaskDate.objects.all()]
        extra_columns = []
        for chapter in self.object.chapters.all():
            qs = TaskDate.dates_for_chapter(chapter)
            chapter_name = chapter.name.replace(' ', '_')
            column_name = f'{chapter_name}_column'
            column_link = f'{chapter_name}_complete_link'
            column_result = f'{chapter_name}_complete_result'
            qs = qs.annotate(
                **{column_name: models.Case(
                    models.When(
                        models.Q(chapters__chapter=chapter),
                        models.Value(chapter.name)
                    ),
                    default=models.Value(chapter.name),
                    output_field=models.CharField()
                )}
            ).annotate(
                **{column_link: models.Case(
                    models.When(
                        models.Q(chapters__chapter=chapter),
                        models.F('chapters__pk')
                    ),
                    default=models.Value(0),
                )}
            ).annotate(
                **{column_result: models.Case(
                    models.When(
                        models.Q(chapters__chapter=chapter),
                        models.Value('True')
                    ),
                    default=models.Value(''),
                    output_field=models.CharField()
                )}
            )
            chapter_task_dict = qs.values(
                'pk', column_name, column_link, column_result)
            [all_chapters_tasks[chapter_task['id']].update(chapter_task)
             for chapter_task in chapter_task_dict.values()]
            extra_columns.append(
                (column_result,
                 tables.LinkColumn(
                     'tasks:detail',
                     verbose_name=chapter_name.replace('_', ' '),
                     args=[A(column_link)],
                     empty_values=())))
        table = RegionChapterTaskTable(
            data=all_chapters_tasks.values(),
            extra_columns=extra_columns)
        context['table'] = table
        return context


class RegionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class RegionListView(LoginRequiredMixin, OfficerMixin, ListView):
    model = Region
    # These next two lines tell the view to index lookups by username
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
