from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView
from core.views import PagedFilteredTableView, RequestConfig
from .models import ScoreType
from .tables import ScoreTable
from .filters import ScoreListFilter
from .forms import ScoreListFormHelper


class ScoreDetailView(LoginRequiredMixin, DetailView):
    model = ScoreType
    # These next two lines tell the view to index lookups by chapter
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'


class ScoreRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('scores:detail',
                       kwargs={'chapter': self.request.user.chapter})


class ScoreListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = ScoreType
    template_name = 'scores/score_list.html'
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'
    context_object_name = 'event'
    ordering = ['name']
    table_class = ScoreTable
    filter_class = ScoreListFilter
    formhelper_class = ScoreListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter()

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = ScoreTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 50}).configure(table)
        context['table'] = table
        return context
