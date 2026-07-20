import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef, Subquery
from django.db.utils import IntegrityError
from django.http.request import QueryDict
from django.shortcuts import reverse
from django.views.generic import CreateView, DetailView

from core.models import current_year_term_slug
from core.views import LoginRequiredMixin, OfficerRequiredMixin, PagedFilteredTableView, RequestConfig
from thetatauCMT.forms.tables import SignTable
from thetatauCMT.forms.views import get_sign_status, get_sign_status_discipline

from .filters import TaskListFilter
from .forms import TaskListFormHelper
from .models import TaskChapter, TaskDate
from .tables import TaskTable


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
        dates = task.incomplete_dates_for_task_chapter(chapter=self.request.user.current_chapter)
        context["due_date"] = task_date
        context["dates"] = dates
        context["is_archived"] = task_date.archived
        return context

    def form_valid(self, form):
        task_date_id = self.kwargs.get("pk")
        task_date = TaskDate.objects.get(pk=task_date_id)
        task = task_date.task
        if task_date.archived:
            messages.add_message(
                self.request,
                messages.ERROR,
                "This due date is marked as no longer needed and cannot be completed.",
            )
            return super().form_invalid(form)
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can sign off tasks. " f"Your current roles are: {*current_roles,}",
            )
            return super().form_invalid(form)
        form.instance.chapter = self.request.user.current_chapter
        form.instance.date = datetime.datetime.today()
        form.instance.task = task_date
        try:
            with transaction.atomic():
                result = super().form_valid(form)
        except IntegrityError:
            messages.add_message(self.request, messages.ERROR, "The task only needs to be complete once")
            result = super().form_invalid(form)
        else:
            messages.add_message(self.request, messages.INFO, f"Task {task.name} marked as complete.")
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
    table_pagination = {"per_page": 40}

    def _build_request_get(self):
        """Return a QueryDict of filter params with sensible defaults.

        Empty ``date`` and ``complete`` params get first-load defaults
        (current term and Incomplete). ``?cancel=`` clears every filter.
        """
        if self.request.GET.get("cancel"):
            return QueryDict(mutable=True)
        request_get = self.request.GET.copy()
        request_get._mutable = True
        if request_get.get("date", "") == "":
            request_get["date"] = current_year_term_slug()
        if request_get.get("complete", "") == "":
            request_get["complete"] = "0"
        if request_get.get("archived", "") == "":
            request_get["archived"] = "0"
        return request_get

    def get_queryset(self, **kwargs):
        chapter = self.request.user.current_chapter
        # Correlated subquery: the current chapter's completion for this
        # TaskDate (if any). Using Subquery/Exists instead of a JOIN keeps
        # each TaskDate as a single row and prevents completions by other
        # chapters from polluting the annotation.
        completed = TaskChapter.objects.filter(task=OuterRef("pk"), chapter=chapter).order_by("-date")
        # Include archived rows in the base queryset so the ``archived`` filter
        # can decide whether to surface them; it hides them by default.
        qs = TaskDate.dates_for_chapter(chapter, include_archived=True).annotate(
            complete_link=Subquery(completed.values("pk")[:1]),
            is_complete=Exists(completed),
        )
        request_get = self._build_request_get()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        discipline_tasks = get_sign_status_discipline(self.request.user, name=True, complete=False)
        convention_tasks = get_sign_status(self.request.user, type_sign="creds", name=True, complete=False)
        resign_tasks = get_sign_status(self.request.user, type_sign="resign", name=True, complete=False)
        osm_tasks = get_sign_status(self.request.user, type_sign="osm", name=True, complete=False)
        all_process_tasks = convention_tasks[0] + resign_tasks[0] + osm_tasks[0] + discipline_tasks
        task_table = SignTable(data=all_process_tasks, extra=True)
        task_table.request = self.request
        RequestConfig(self.request, paginate={"per_page": 40}).configure(task_table)
        context["task_table"] = task_table
        return context
