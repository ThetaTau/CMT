from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from braces.views import GroupRequiredMixin
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin
from .models import Event
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'


class EventCreateView(LoginRequiredMixin, TypeFieldFilteredChapterAdd,
                      CreateView):
    model = Event
    template_name_suffix = '_create_form'
    fields = ['name',
              'date',
              'type',
              'description',
              'members', 'pledges', 'alumni',
              'guests', 'duration', 'stem', 'host', 'miles'
              ]

    def get_success_url(self):
        return reverse('events:list')


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('events:list')


class EventUpdateView(GroupRequiredMixin, LoginRequiredMixin,
                      TypeFieldFilteredChapterAdd,
                      UpdateView):
    group_required = u"officer"
    fields = ['name',
              'date',
              'type',
              'description',
              'members', 'pledges', 'alumni',
              'guests', 'duration', 'stem', 'host', 'miles']
    model = Event

    def get_success_url(self):
        return reverse('events:list')

    def get_login_url(self):
        messages.add_message(
            self.request, messages.ERROR,
            f"Only officers can edit events")
        return self.get_success_url()


class EventListView(LoginRequiredMixin, OfficerMixin,
                    PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'
    context_object_name = 'event'
    ordering = ['-date']
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
