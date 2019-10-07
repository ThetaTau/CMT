from django.db import models
from django.http.request import QueryDict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import PagedFilteredTableView, RequestConfig, TypeFieldFilteredChapterAdd,\
    OfficerMixin, OfficerRequiredMixin, NatOfficerRequiredMixin
from core.models import NAT_OFFICERS, COUNCIL
from users.models import UserRoleChange
from chapters.models import Chapter
from .models import Ballot, BallotComplete
from .tables import BallotTable, BallotCompleteTable
from .filters import BallotFilter, BallotCompleteFilter
from .forms import BallotListFormHelper, BallotCompleteListFormHelper


class BallotDetailView(NatOfficerRequiredMixin, LoginRequiredMixin, OfficerMixin,
                       PagedFilteredTableView, DetailView):
    model = Ballot
    context_object_name = 'ballot'
    ordering = ['-date']
    template_name_suffix = '_completelist'
    table_class = BallotCompleteTable
    filter_class = BallotCompleteFilter
    formhelper_class = BallotCompleteListFormHelper

    def get_queryset(self):
        self.object = self.get_object(queryset=super(DetailView, self).get_queryset())
        qs = self.object.completed.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_ballots = self.object_list
        all_ballots = all_ballots.annotate(
            region=models.Case(
                models.When(role__in=NAT_OFFICERS, then=models.Value('Nationals')),
                default=models.F("user__chapter__region__name"),
                output_field=models.CharField(),
            ),
            chapter=models.Case(
                models.When(role__in=NAT_OFFICERS, then=models.Value('')),
                default=models.F('user__chapter__name'),
                output_field=models.CharField(),
            ),
            user_name=models.F('user__name'),
        )
        users = all_ballots.values_list('user', flat=True)
        chapters = all_ballots.exclude(
            role__in=NAT_OFFICERS
            ).values_list('chapter', flat=True)
        data = list(all_ballots.values(
            'user_name', 'chapter', 'region', 'motion', 'role', ))
        nat_offs = UserRoleChange.get_current_natoff().exclude(user__in=users)
        incomplete_chapter = []
        if self.object.voters == 'council':
            nat_offs = nat_offs.filter(role__in=COUNCIL)
        elif self.object.voters == 'convention':
            incomplete_chapter = [
                {
                    'user_name': '',
                    'chapter': chapter,
                    'motion': 'Incomplete',
                    'role': '',
                    'region': chapter.region
                } for chapter in Chapter.objects.filter(colony=False).exclude(name__in=chapters)]
        incomplete_national = [
            {
                'user_name': user.user,
                'chapter': '',
                'motion': 'Incomplete',
                'role': user.role,
                'region': 'National'
            } for user in nat_offs]
        incomplete = incomplete_national + incomplete_chapter
        table = BallotCompleteTable(data=data+incomplete)
        RequestConfig(self.request, paginate={'per_page': 200}).configure(table)
        context['table'] = table
        context['object'] = self.object
        context['incomplete'] = len(incomplete)
        context[self.context_object_name] = self.object
        return context


class BallotCreateView(NatOfficerRequiredMixin,
                       LoginRequiredMixin, OfficerMixin,
                       CreateView):
    model = Ballot
    template_name_suffix = '_create_form'
    officer_edit = 'ballots'
    officer_edit_type = 'create'
    fields = ['sender', 'name', 'type', 'attachment', 'description',
              'due_date', 'voters']

    def get_success_url(self):
        return reverse('ballots:list')


class BallotCopyView(BallotCreateView):
    def get_initial(self):
        ballot = Ballot.objects.get(pk=self.kwargs['pk'])
        self.initial = {
            'name': ballot.name + " Copy",
            'sender': ballot.sender,
            'type': ballot.type,
            'attachment': ballot.attachment,
            'description': ballot.description,
            'voters': ballot.voters,
        }
        return self.initial


class BallotRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('ballots:list')


class BallotUpdateView(NatOfficerRequiredMixin, OfficerMixin,
                       LoginRequiredMixin,
                       TypeFieldFilteredChapterAdd,
                       UpdateView):
    officer_edit = 'ballot'
    officer_edit_type = 'edit'
    fields = ['sender', 'name', 'type', 'attachment', 'description',
              'due_date', 'voters']
    model = Ballot

    def get_success_url(self):
        return reverse('ballots:list')


class BallotListView(LoginRequiredMixin, OfficerMixin,
                     PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Ballot
    context_object_name = 'ballot'
    ordering = ['-date']
    table_class = BallotTable
    filter_class = BallotFilter
    formhelper_class = BallotListFormHelper

    def get_queryset(self):
        qs = Ballot.counts()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = BallotTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table
        return context
