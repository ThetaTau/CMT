from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import models
from django.http import Http404
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, RedirectView, UpdateView

from core.models import NAT_OFFICERS
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    OfficerRequiredMixin,
    PagedFilteredTableView,
    RequestConfig,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import UserRoleChange

from .filters import BallotCompleteFilter, BallotFilter, BallotUserFilter
from .forms import (
    BallotCompleteForm,
    BallotCompleteListFormHelper,
    BallotForm,
    BallotListFormHelper,
    BallotUserListFormHelper,
)
from .models import BALLOT_CHAPTER_ROLES, Ballot, BallotComplete, can_view_ballot_results
from .notifications import send_ballot_notifications
from .tables import RESULT_COLUMNS, BallotCompleteTable, BallotTable, BallotUserTable


def get_ballot_or_404(slug):
    """Ballot for ``slug``, newest first.

    ``slug`` is only unique together with the due date, so a ballot re-run under
    the same name used to blow up with ``MultipleObjectsReturned``.
    """
    ballot = Ballot.get_by_slug(slug)
    if ballot is None:
        raise Http404("No ballot matches the given query.")
    return ballot


class BallotDetailView(
    LoginRequiredMixin,
    OfficerRequiredMixin,
    PagedFilteredTableView,
    DetailView,
):
    model = Ballot
    context_object_name = "ballot"
    template_name_suffix = "_completelist"
    table_class = BallotCompleteTable
    filter_class = BallotCompleteFilter
    formhelper_class = BallotCompleteListFormHelper
    officer_edit = "ballot status"
    officer_edit_type = "view"

    def get_object(self, queryset=None):
        return get_ballot_or_404(self.kwargs.get(self.slug_url_kwarg))

    @property
    def show_results(self):
        return can_view_ballot_results(self.request.user)

    def get_queryset(self):
        self.object = self.get_object()
        qs = self.object.completed.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        show_results = self.show_results
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        want_incomplete = request_get.get("status", "") in ("", "incomplete")
        region = request_get.get("region", "")
        all_ballots = self.object_list
        all_ballots = all_ballots.annotate(
            region=models.Case(
                models.When(role__in=NAT_OFFICERS, then=models.Value("National")),
                default=models.F("user__chapter__region__name"),
                output_field=models.CharField(),
            ),
            chapter=models.Case(
                models.When(role__in=NAT_OFFICERS, then=models.Value("")),
                default=models.F("user__chapter__name"),
                output_field=models.CharField(),
            ),
            user_name=models.F("user__name"),
        )
        if region == "national":
            all_ballots = all_ballots.filter(region="National")
        users = all_ballots.values_list("user", flat=True)
        chapters = all_ballots.exclude(role__in=NAT_OFFICERS).values_list("chapter", flat=True)
        data = list(
            all_ballots.values(
                "user_name",
                "chapter",
                "region",
                "motion",
                "role",
            )
        )
        nat_offs = UserRoleChange.get_current_natoff().exclude(user__in=users)
        incomplete_chapter = []
        nat_offs = nat_offs.filter(role__in=self.object.voters)
        if "all_chapters" in self.object.voters and region != "national":
            # Candidate Chapters can not vote
            chapters = Chapter.objects.filter(candidate_chapter=False, active=True).exclude(name__in=chapters)
            if region != "":
                chapters = chapters.filter(region__slug=region)
            incomplete_chapter = [
                {
                    "user_name": "",
                    "chapter": chapter,
                    "motion": "Incomplete",
                    "role": "",
                    "region": chapter.region,
                }
                for chapter in chapters
            ]
        incomplete_national = []
        if region == "" or region == "national":
            incomplete_national = [
                {
                    "user_name": user.user,
                    "chapter": "",
                    "motion": "Incomplete",
                    "role": user.role,
                    "region": "National",
                }
                for user in nat_offs
            ]
        incomplete = []
        if want_incomplete:
            incomplete = incomplete_national + incomplete_chapter
        table = BallotCompleteTable(data=data + incomplete)
        RequestConfig(self.request, paginate={"per_page": 200}).configure(table)
        context["table"] = table
        context["object"] = self.object
        context["incomplete"] = len(incomplete)
        context["submitted"] = len(data)
        context["show_results"] = show_results
        context[self.context_object_name] = self.object
        return context


class BallotCreateView(LoginRequiredMixin, NatOfficerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ballot
    template_name_suffix = "_create_form"
    officer_edit = "ballots"
    officer_edit_type = "create"
    success_message = "Ballot '%(name)s' was created and is now open for voting."
    form_class = BallotForm

    def form_valid(self, form):
        response = super().form_valid(form)
        sent = send_ballot_notifications(self.object, reminder=False)
        messages.add_message(
            self.request,
            messages.INFO,
            f"Ballot emailed to {sent} voter{'' if sent == 1 else 's'}; "
            "reminders go out every 7 days until they vote.",
        )
        return response

    def get_success_url(self):
        return reverse("ballots:list")


class BallotCopyView(BallotCreateView):
    def get_initial(self):
        ballot = get_object_or_404(Ballot, pk=self.kwargs["pk"])
        self.initial = {
            "name": ballot.name + " Copy",
            "sender": ballot.sender,
            "type": ballot.type,
            "attachment": ballot.attachment,
            "description": ballot.description,
            "voters": ballot.voters,
        }
        return self.initial


class BallotRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        # Only National Officers can reach the all-ballots list.
        if getattr(self.request, "is_nat_officer", False) or self.request.user.is_admin:
            return reverse("ballots:list")
        return reverse("ballots:votelist")


class BallotUpdateView(
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    officer_edit = "ballot"
    officer_edit_type = "edit"
    success_message = "Ballot '%(name)s' was updated."
    form_class = BallotForm
    model = Ballot

    def get_success_url(self):
        return reverse("ballots:list")


class BallotListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = Ballot
    context_object_name = "ballot"
    ordering = ["-due_date"]
    table_class = BallotTable
    filter_class = BallotFilter
    formhelper_class = BallotListFormHelper

    def get_queryset(self):
        qs = Ballot.counts()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        show_results = can_view_ballot_results(self.request.user)
        exclude = () if show_results else RESULT_COLUMNS
        table = BallotTable(self.object_list, exclude=exclude)
        RequestConfig(self.request, paginate={"per_page": 30}).configure(table)
        context["table"] = table
        context["show_results"] = show_results
        return context


class BallotCompleteCreateView(LoginRequiredMixin, OfficerRequiredMixin, CreateView):
    model = BallotComplete
    template_name_suffix = "_vote"
    officer_edit = "ballots"
    officer_edit_type = "vote"
    form_class = BallotCompleteForm

    def get_ballot(self):
        if not hasattr(self, "_ballot"):
            self._ballot = get_ballot_or_404(self.kwargs.get("slug"))
        return self._ballot

    def get_existing_vote(self, ballot):
        """The vote already on file for this user, or for their chapter."""
        own = ballot.get_completed(self.request.user)
        if own:
            return own
        if set(self.request.user.current_roles or []) & set(BALLOT_CHAPTER_ROLES):
            return ballot.chapter_vote(self.request.user.chapter)
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ballot = self.get_ballot()
        valid_roles = ballot.voting_roles_for(self.request.user)
        completed = self.get_existing_vote(ballot)
        if completed or not ballot.is_open:
            form = context["form"]
            for field in form.fields.values():
                field.disabled = True
        context["ballot"] = ballot
        context["complete"] = bool(completed)
        context["current_vote"] = completed
        context["show_results"] = can_view_ballot_results(self.request.user)
        context["voters"] = ballot.voters_display
        context["valid_roles"] = bool(valid_roles)
        context["ballot_open"] = ballot.is_open
        return context

    def form_valid(self, form):
        ballot = self.get_ballot()
        user = self.request.user
        form.instance.user = user
        form.instance.ballot = ballot
        if not ballot.is_open:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Voting on {ballot.name} closed on {ballot.closes_display}.",
            )
            return super().form_invalid(form)
        valid_roles = ballot.voting_roles_for(user)
        if not valid_roles:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only {ballot.voters_display} can vote on this ballot. "
                f"Your current roles are: {', '.join(user.current_roles or []) or 'none'}",
            )
            return super().form_invalid(form)
        existing = self.get_existing_vote(ballot)
        if existing:
            if existing.user == user:
                detail = "You have already voted on this ballot."
            else:
                detail = f"{existing.user.name} already cast your chapter's vote as {existing.role.title()}."
            messages.add_message(self.request, messages.ERROR, detail)
            return super().form_invalid(form)
        current_role = valid_roles[0]
        form.instance.role = current_role
        messages.add_message(
            self.request,
            messages.INFO,
            f"Vote for {ballot.name} completed as {current_role.title()}",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ballots:votelist")


class BallotUserListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Ballot
    context_object_name = "ballot"
    template_name_suffix = "_votelist"
    ordering = ["-due_date"]
    table_class = BallotUserTable
    filter_class = BallotUserFilter
    formhelper_class = BallotUserListFormHelper

    def get_queryset(self):
        qs = Ballot.user_ballots(self.request.user)
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = BallotUserTable(self.object_list)
        RequestConfig(self.request, paginate={"per_page": 30}).configure(table)
        context["table"] = table
        return context
