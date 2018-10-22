import datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, reverse
from django.http.request import QueryDict
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import TaskChapter, TaskDate, Task
from .tables import TaskTable
from .filters import TaskListFilter
from .forms import TaskListFormHelper


class TaskCompleteView(OfficerRequiredMixin,
                       LoginRequiredMixin, OfficerMixin, CreateView):
    model = TaskChapter
    fields = []
    template_name = "tasks/task_complete.html"
    officer_edit = 'tasks'
    officer_edit_type = 'complete'

    def get(self, request, *args, **kwargs):
        task_date_id = self.kwargs.get('pk')
        task = TaskDate.objects.get(pk=task_date_id).task
        if task.type == 'sub':
            if task.submission_type:
                return redirect(reverse('submissions:add-direct', args=(task.submission_type.slug,)))
        elif task.type == 'form':
            if task.resource:
                if 'http' not in task.resource:
                    return redirect(reverse(task.resource))
                return redirect(task.resource)
        self.object = None
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_date_id = self.kwargs.get('pk')
        task = TaskDate.objects.get(pk=task_date_id).task
        context['task'] = task
        return context

    def form_valid(self, form):
        task_date_id = self.kwargs.get('pk')
        task_date = TaskDate.objects.get(pk=task_date_id)
        task = task_date.task
        owner = task.owner.lower()
        user_role = self.request.user.get_current_role()
        if user_role:
            user_role = user_role.role.lower()
        if owner != user_role:
            messages.add_message(
                self.request, messages.ERROR,
                f"Only the task owner, {owner}, can mark a task complete."
                f" Your role is: {user_role}")
            return super().form_invalid(form)
        form.instance.chapter = self.request.user.current_chapter
        form.instance.date = datetime.datetime.today()
        form.instance.task = task_date
        try:
            with transaction.atomic():
                result = super().form_valid(form)
        except IntegrityError as e:
            messages.add_message(
                self.request, messages.ERROR,
                f"The task only needs to be complete once")
            result = super().form_invalid(form)
        else:
            messages.add_message(
                self.request, messages.INFO,
                f"Task {task.name} marked as complete.")
        return result

    def get_success_url(self):
        return reverse('tasks:list')


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = TaskChapter


class TaskListView(LoginRequiredMixin, OfficerMixin,
                   PagedFilteredTableView):
    model = TaskDate
    template_name = "tasks/task_list.html"
    context_object_name = 'task'
    table_class = TaskTable
    filter_class = TaskListFilter
    formhelper_class = TaskListFormHelper

    def get_queryset(self, **kwargs):
        qs = TaskDate.dates_for_chapter(self.request.user.current_chapter)
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.request.user.current_chapter
        qs = self.get_queryset()
        qs = qs.annotate(
                complete_link=models.Case(
                    models.When(
                        models.Q(chapters__chapter=chapter),
                        models.F('chapters__pk')
                    ),
                    default=models.Value(0),
                )
            ).annotate(
            complete_result=models.Case(
                models.When(
                    models.Q(chapters__chapter=chapter),
                    models.Value('True')
                ),
                default=models.Value(''),
                output_field=models.CharField()
            )
        )
        # Annotate is duplicating things
        qs = qs.distinct()
        # Distinct sees incomplete/complete as different, so need to combine
        complete = qs.filter(complete_result=True)
        incomplete = qs.filter(~models.Q(pk__in=complete), complete_result='')
        all_tasks = complete | incomplete
        table = TaskTable(all_tasks)
        table.request = self.request
        RequestConfig(self.request, paginate={'per_page': 40}).configure(table)
        context['table'] = table
        return context
