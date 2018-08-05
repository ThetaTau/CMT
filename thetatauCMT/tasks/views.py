from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import TaskChapter, TaskDate
from .tables import TaskTable
from .filters import TaskListFilter
from .forms import TaskListFormHelper


class TaskCompleteView(LoginRequiredMixin, OfficerMixin, DetailView):
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
        qs = TaskDate.dates_for_chapter(self.request.user.chapter)
        self.filter = self.filter_class(self.request.GET,
                                        queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        cancel = self.request.GET.get('cancel', False)
        qs_out = self.filter.qs
        if cancel:
            qs_out = qs
        return qs_out

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = TaskTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table
        return context
