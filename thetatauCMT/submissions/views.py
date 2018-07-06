from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd
from .models import Submission
from .tables import SubmissionTable
from .filters import SubmissionListFilter
from .forms import SubmissionListFormHelper


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = Submission
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class SubmissionCreateView(LoginRequiredMixin, CreateView,
                           TypeFieldFilteredChapterAdd):
    model = Submission
    score_type = 'Sub'
    template_name_suffix = '_create_form'
    fields = ['name', 'date',
              'type', 'file',
              ]

    def get_success_url(self):
        return reverse('submissions:list')


class SubmissionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('submissions:list')


class SubmissionUpdateView(LoginRequiredMixin, UpdateView,
                           TypeFieldFilteredChapterAdd):
    fields = ['name',
              'date',
              'type',
              'file',
              ]
    model = Submission

    def get_success_url(self):
        return reverse('submissions:list')


class SubmissionListView(LoginRequiredMixin, PagedFilteredTableView):
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
