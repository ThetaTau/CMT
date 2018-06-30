from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView

from .models import Event
from .tables import EventTable


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


class EventListView(LoginRequiredMixin, ListView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = 'chapter'
    slug_url_kwarg = 'chapter'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.chapter)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = EventTable(self.get_queryset())
        context['table'] = table
        return context
