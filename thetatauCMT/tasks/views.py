from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import TaskChapter


class TaskCompleteView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = TaskChapter


class TaskListView(LoginRequiredMixin, OfficerMixin,
                    PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = TaskChapter
    # slug_field = 'chapter'
    # slug_url_kwarg = 'chapter'
    # context_object_name = 'event'
    # ordering = ['-date']
    # table_class = EventTable
    # filter_class = EventListFilter
    # formhelper_class = EventListFormHelper
    #
    # def get_queryset(self):
    #     qs = super().get_queryset()
    #     return qs.filter(chapter=self.request.user.chapter)
    #
    # def post(self, request, *args, **kwargs):
    #     return PagedFilteredTableView.as_view()(request)
    #
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     table = EventTable(self.get_queryset())
    #     RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
    #     context['table'] = table
    #     return context
