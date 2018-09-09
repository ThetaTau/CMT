from collections import defaultdict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.http.request import QueryDict
from django.db import models
from django.views.generic import DetailView, ListView, RedirectView
import django_tables2 as tables
from django_tables2.utils import A
from core.views import OfficerMixin, NatOfficerRequiredMixin, RequestConfig
from core.models import combine_annotations
from .models import Region
from tasks.models import TaskDate
from .tables import RegionChapterTaskTable
from .filters import RegionChapterTaskFilter
from .forms import RegionChapterTaskFormHelper
from users.tables import UserTable
from users.models import User
from users.filters import UserRoleListFilter
from users.forms import UserRoleListFormHelper


class RegionOfficerView(NatOfficerRequiredMixin,
                        LoginRequiredMixin, OfficerMixin, DetailView):
    model = Region
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    filter_class = UserRoleListFilter
    formhelper_class = UserRoleListFormHelper
    template_name = "regions/officer_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_chapter_officers = User.objects.none()
        for chapter in self.object.chapters.all():
            context = super().get_context_data(**kwargs)
            chapter_officers = chapter.get_current_officers(combine=False)
            all_chapter_officers = chapter_officers | all_chapter_officers
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=all_chapter_officers)
        self.filter.form.helper = self.formhelper_class()
        all_chapter_officers = combine_annotations(self.filter.qs)
        self.filter.form.base_fields['chapter'].queryset = self.object.chapters.all()
        table = UserTable(
            data=all_chapter_officers,
            extra_columns=[('chapter',
                            tables.LinkColumn(
                                'chapters:detail',
                                args=[A('chapter.slug')]))])
        RequestConfig(self.request, paginate={'per_page': 50}).configure(table)
        context['table'] = table
        context['filter'] = self.filter
        return context


class RegionDetailView(NatOfficerRequiredMixin,
                       LoginRequiredMixin, OfficerMixin, DetailView):
    model = Region
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class RegionTaskView(NatOfficerRequiredMixin,
                     LoginRequiredMixin, OfficerMixin, DetailView):
    model = Region
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    filter_class = RegionChapterTaskFilter
    formhelper_class = RegionChapterTaskFormHelper
    template_name = "regions/task_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.objects.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        all_chapters_tasks = {task.pk: defaultdict(lambda: 0) for task in self.filter.qs}
        [all_chapters_tasks[task.id].update(
            {'task_name': task.task.name,
             'task_owner': task.task.owner,
             'school_type': task.school_type,
             'date': task.date})
            for task in self.filter.qs]
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
            qs = qs.distinct()
            # Distinct sees incomplete/complete as different, so need to combine
            complete = qs.filter(**{column_result: True})
            incomplete = qs.filter(~models.Q(pk__in=complete), **{column_result: ""})
            all_tasks = complete | incomplete
            chapter_task_dict = all_tasks.values(
                'pk', column_name, column_link, column_result)
            [all_chapters_tasks[chapter_task['id']].update(chapter_task)
             for chapter_task in chapter_task_dict.values() if chapter_task['id'] in all_chapters_tasks]
            extra_columns.append(
                (column_result,
                 tables.LinkColumn(
                     'tasks:detail',
                     verbose_name=chapter_name.replace('_', ' '),
                     args=[A(column_link)],
                     empty_values=())))
        all_chapters_tasks = all_chapters_tasks.values()
        table = RegionChapterTaskTable(
            data=all_chapters_tasks,
            extra_columns=extra_columns)
        context['table'] = table
        context['filter'] = self.filter
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
