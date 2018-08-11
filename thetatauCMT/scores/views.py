from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView
from core.views import PagedFilteredTableView, RequestConfig, OfficerMixin
from .models import ScoreType
from .tables import ScoreTable
from events.tables import EventTable
from submissions.tables import SubmissionTable
from .filters import ScoreListFilter
from .forms import ScoreListFormHelper


class ScoreDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = ScoreType
    # These next two lines tell the view to index lookups by chapter
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'scores/score_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if context['object'].type == "Evt":
            chapter_events = context['object'].events.filter(chapter=self.request.user.chapter)
            table = EventTable(data=chapter_events)
        elif context['object'].type == "Sub":
            chapter_submissions = context['object'].submissions.filter(chapter=self.request.user.chapter)
            table = SubmissionTable(data=chapter_submissions)
        else:
            context['table'] = ScoreType.objects.none()
            return context
        RequestConfig(self.request, paginate={'per_page': 50}).configure(table)
        context['table'] = table
        return context


class ScoreRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('scores:detail',
                       kwargs={'chapter': self.request.user.chapter})


class ScoreListView(LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = ScoreType
    template_name = 'scores/score_list.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
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
        table = ScoreTable(data=self.get_queryset())
        table.request = self.request
        RequestConfig(self.request, paginate={'per_page': 50}).configure(table)
        context['table'] = table
        return context
