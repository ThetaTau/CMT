from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig
from .models import Event
from scores.models import ScoreType
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    template_name_suffix = '_create_form'
    # initial = {
    #     'type': ScoreType.objects.filter(type='Evt').all()
    # }
    fields = ['name',
              'type', 'description',
              'duration', 'stem', 'host', 'miles',
              ]

    def get_success_url(self):
        return reverse('events:list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['type'].queryset = ScoreType.objects.filter(type='Evt').all()
        return form

    # def get_initial(self):
    #     initial = super().get_initial()
    #     print("INITIAL: ", initial)
    #     initial = initial.copy()
    #     initial['type'].queryset = ScoreType.objects.filter(type='Evt').all()
    #     print("TYPES: ", initial['type'])
    #     return initial

    def form_valid(self, form):
        form.instance.chapter = self.request.user.chapter
        response = super().form_valid(form)
        return response


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('events:list')


class EventUpdateView(LoginRequiredMixin, UpdateView):
    fields = ['name',
              # 'date',
              'description',
              'guests', 'duration', 'stem', 'host', 'miles']
    model = Event

    def get_success_url(self):
        return reverse('events:list')


class EventListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'
    context_object_name = 'event'
    ordering = ['date']
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
