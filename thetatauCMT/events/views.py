from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import Event
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper


class EventDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'


class EventCreateView(OfficerRequiredMixin,
                      LoginRequiredMixin, OfficerMixin,
                      TypeFieldFilteredChapterAdd,
                      CreateView):
    model = Event
    template_name_suffix = '_create_form'
    officer_edit = 'events'
    officer_edit_type = 'create'
    fields = ['name',
              'date',
              'type',
              'description',
              'members', 'pledges', 'alumni',
              'guests', 'duration', 'stem', 'host', 'miles'
              ]

    def get_success_url(self):
        return reverse('events:list')


class EventCopyView(EventCreateView):
    def get_initial(self):
        event = Event.objects.get(pk=self.kwargs['pk'])
        self.initial = {
            'name': event.name,
            'date': event.date,
            'type': event.type,
            'description': event.description,
            'members': event.members,
            'pledges': event.pledges,
            'alumni': event.alumni,
            'guests': event.guests,
            'duration': event.duration,
            'stem': event.stem,
            'host': event.host,
            'miles': event.miles
        }
        return self.initial


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('events:list')


class EventUpdateView(OfficerRequiredMixin, OfficerMixin,
                      LoginRequiredMixin,
                      TypeFieldFilteredChapterAdd,
                      UpdateView):
    officer_edit = 'events'
    officer_edit_type = 'edit'
    fields = ['name',
              'date',
              'type',
              'description',
              'members', 'pledges', 'alumni',
              'guests', 'duration', 'stem', 'host', 'miles']
    model = Event

    def get_success_url(self):
        return reverse('events:list')


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
    filter_chapter = True
