import datetime
from django.contrib import messages
from django.shortcuts import redirect, reverse
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.http.request import QueryDict
from django.views.generic import DetailView, CreateView
from core.models import current_year_term_slug
from core.views import (
    PagedFilteredTableView,
    RequestConfig,
    OfficerRequiredMixin,
    LoginRequiredMixin,
)
from forms.tables import SignTable
from forms.views import get_sign_status, get_sign_status_discipline
from .models import TaskChapter, TaskDate
from .tables import TaskTable
from .filters import TaskListFilter
from .forms import TaskListFormHelper


class TaskCompleteView(LoginRequiredMixin, OfficerRequiredMixin, CreateView):
    model = TaskChapter
    fields = []
    template_name = "tasks/task_complete.html"
    officer_edit = "tasks"
    officer_edit_type = "complete"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_date_id = self.kwargs.get("pk")
        task_date = TaskDate.objects.get(pk=task_date_id)
        task = task_date.task
        context["task"] = task
        dates = task.incomplete_dates_for_task_chapter(
            chapter=self.request.user.current_chapter
        )
        context["due_date"] = task_date
        context["dates"] = dates
        return context

    def form_valid(self, form):
        task_date_id = self.kwargs.get("pk")
        task_date = TaskDate.objects.get(pk=task_date_id)
        task = task_date.task
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can sign off tasks. "
                f"Your current roles are: {*current_roles,}",
            )
            return super().form_invalid(form)
        form.instance.chapter = self.request.user.current_chapter
        form.instance.date = datetime.datetime.today()
        form.instance.task = task_date
        try:
            with transaction.atomic():
                result = super().form_valid(form)
        except IntegrityError:
            messages.add_message(
                self.request, messages.ERROR, "The task only needs to be complete once"
            )
            result = super().form_invalid(form)
        else:
            messages.add_message(
                self.request, messages.INFO, f"Task {task.name} marked as complete."
            )
        return result

    def get_success_url(self):
        return reverse("tasks:list")


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = TaskChapter


class TaskListView(LoginRequiredMixin, PagedFilteredTableView):
    model = TaskDate
    template_name = "tasks/task_list.html"
    context_object_name = "task"
    table_class = TaskTable
    filter_class = TaskListFilter
    formhelper_class = TaskListFormHelper

    def get_queryset(self, **kwargs):
        qs = TaskDate.dates_for_chapter(self.request.user.current_chapter)
        qs = super().get_queryset(other_qs=qs)
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("date", [""])
            request_get.setlist("complete", [""])
        if not cancel:
            if request_get.get("date", "") == "":
                request_get["date"] = current_year_term_slug()
            if request_get.get("complete", "") == "":
                request_get["complete"] = "0"
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.request.user.current_chapter
        qs = self.get_queryset()
        qs = qs.annotate(
            complete_link=models.Case(
                models.When(
                    models.Q(chapters__chapter=chapter), models.F("chapters__pk")
                ),
                default=models.Value(0),
            )
        )
        # Annotate is duplicating things
        qs = qs.distinct()
        # Distinct sees incomplete/complete as different, so need to combine
        complete = qs.exclude(complete_link=0)
        incomplete = qs.filter(complete_link=0)
        all_tasks = complete | incomplete
        table = TaskTable(data=all_tasks)
        table.request = self.request
        RequestConfig(self.request, paginate={"per_page": 40}).configure(table)
        context["table"] = table
        discipline_tasks = get_sign_status_discipline(
            self.request.user, name=True, complete=False
        )
        convention_tasks = get_sign_status(
            self.request.user, type_sign="creds", name=True, complete=False
        )
        resign_tasks = get_sign_status(
            self.request.user, type_sign="resign", name=True, complete=False
        )
        osm_tasks = get_sign_status(
            self.request.user, type_sign="osm", name=True, complete=False
        )
        all_process_tasks = (
            convention_tasks[0] + resign_tasks[0] + osm_tasks[0] + discipline_tasks
        )
        task_table = SignTable(data=all_process_tasks, extra=True)
        task_table.request = self.request
        RequestConfig(self.request, paginate={"per_page": 40}).configure(task_table)
        context["task_table"] = task_table
        return context
