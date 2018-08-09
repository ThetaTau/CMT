from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import Submission
from .tables import SubmissionTable
from .filters import SubmissionListFilter
from .forms import SubmissionListFormHelper


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = Submission
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class SubmissionCreateView(OfficerRequiredMixin, OfficerMixin,
                           LoginRequiredMixin, TypeFieldFilteredChapterAdd,
                           CreateView):
    model = Submission
    score_type = 'Sub'
    template_name_suffix = '_create_form'
    fields = ['name', 'date',
              'type', 'file',
              ]
    officer_edit = 'submissions'
    officer_edit_type = 'create'

    def get_success_url(self):
        return reverse('submissions:list')

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     submit_type = self.kwargs.get('slug')
    #     return context


class SubmissionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('submissions:list')


class SubmissionUpdateView(OfficerRequiredMixin,
                           LoginRequiredMixin,
                           TypeFieldFilteredChapterAdd,
                           UpdateView):
    fields = ['name',
              'date',
              'type',
              'file',
              ]
    model = Submission
    officer_edit = 'submissions'
    officer_edit_type = 'edit'

    def get_success_url(self):
        return reverse('submissions:list')


class SubmissionListView(LoginRequiredMixin, OfficerMixin,
                         PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Submission
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    context_object_name = 'submission'
    ordering = ['-date']
    table_class = SubmissionTable
    filter_class = SubmissionListFilter
    formhelper_class = SubmissionListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.chapter)

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = SubmissionTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table
        return context
