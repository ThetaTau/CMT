from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin
from .models import Ballot
from .tables import EventTable
from .filters import EventListFilter
from .forms import EventListFormHelper


class BallotDetailView(LoginRequiredMixin, OfficerMixin, DetailView):
    model = Ballot


class BallotCreateView(OfficerRequiredMixin,
                       LoginRequiredMixin, OfficerMixin,
                       TypeFieldFilteredChapterAdd,
                       CreateView):
    model = Ballot
    template_name_suffix = '_create_form'
    officer_edit = 'ballots'
    officer_edit_type = 'create'
    fields = []

    def get_success_url(self):
        return reverse('events:list')


class BallotCopyView(BallotCreateView):
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


class BallotRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('ballots:list')


class BallotUpdateView(OfficerRequiredMixin, OfficerMixin,
                       LoginRequiredMixin,
                       TypeFieldFilteredChapterAdd,
                       UpdateView):
    officer_edit = 'ballot'
    officer_edit_type = 'edit'
    fields = []
    model = Ballot

    def get_success_url(self):
        return reverse('events:list')


class BallotListView(LoginRequiredMixin, OfficerMixin,
                    PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Ballot
    context_object_name = 'ballot'
    ordering = ['-date']
    table_class = BallotTable
    filter_class = BallotListFilter
    formhelper_class = BallotListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.current_chapter)

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = BallotTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table
        return context
