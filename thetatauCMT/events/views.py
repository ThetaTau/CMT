from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView
from core.views import PagedFilteredTableView, RequestConfig
from .models import Event
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    # These next two lines tell the view to index lookups by username
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.request.user.username})


class EventListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'
    context_object_name = 'event'
    ordering = ['date']
    # group_required = u'company-user'
    table_class = EventTable
    filter_class = EventListFilter
    formhelper_class = EventListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.chapter)

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = EventTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table

        return context
