import datetime
from collections import Counter, defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import dateformat, timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from core.models import CSS_ROLE
from thetatauCMT.users.models import User, UserAlter

from .forms import CSSAssignForm, CSSChapterForm, CSSCreateForm, CSSEndForm
from .models import ChapterSupportAssignment
from .notifications import EmailSupportWelcome
from .overview import chapter_overview
from .services import (
    CSSAccountError,
    assign_chapter,
    can_manage_css,
    can_view_css_directory,
    clear_css_state,
    create_css_account,
    css_chapters,
    css_state,
    current_css_users,
    end_assignment,
    holds_css_role,
    is_member_account,
    remove_css,
    wants_css_landing,
)


def _safe_next(request, fallback):
    redirect_to = request.POST.get("next", "")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect_to
    return fallback


class CSSChapterSwitchView(LoginRequiredMixin, View):
    """The CSS chapter switcher (S3): view another assigned chapter, or reset.

    The choice is kept in the user's ``UserAlter`` row, the same row National Officers'
    switcher uses, so it is remembered between sign-ins. Reset forgets it, which lands the
    CSS on the fallback chapter (their own chapter for a member, else their first assignment).
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        user = request.user
        state = css_state(user)
        if not state.is_css or user.in_national_officer_group:
            messages.error(request, "Only Chapter Support Specialists can use this switcher.")
            return HttpResponseRedirect(reverse("home"))
        if request.POST.get("action") == "reset":
            UserAlter.objects.filter(user=user).delete()
            clear_css_state(user)
            messages.info(request, f"Now viewing {user.current_chapter}.")
            return HttpResponseRedirect(self._next(request))
        form = CSSChapterForm(request.POST, user=user)
        if not form.is_valid():
            messages.error(request, "; ".join(form.errors.get("chapter", ["Pick one of your chapters."])))
            return HttpResponseRedirect(_safe_next(request, reverse("home")))
        chapter = form.cleaned_data["chapter"]
        UserAlter.objects.update_or_create(user=user, defaults={"chapter": chapter, "role": None})
        clear_css_state(user)
        messages.info(request, f"Now viewing {chapter}.")
        return HttpResponseRedirect(self._next(request))

    def _next(self, request):
        # A chapter page of the chapter just left would be confusing, so land on the newly
        # viewed chapter's page instead (the National Officers' switcher does the same).
        chapter_home = reverse("chapters:detail", kwargs={"slug": request.user.current_chapter.slug})
        redirect_to = _safe_next(request, chapter_home)
        if "/chapters/" in redirect_to:
            return chapter_home
        return redirect_to


class CSSLandingView(LoginRequiredMixin, TemplateView):
    """A CSS's Home (Q12, Q24 A): their chapters at a glance, the dashboard, What's New."""

    template_name = "support/my_chapters.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not wants_css_landing(request.user):
            messages.info(request, "My Chapters is for Chapter Support Specialists.")
            return HttpResponseRedirect(reverse("home"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from thetatauCMT.contact_sync.context import build_sync_modal_context
        from thetatauCMT.contact_sync.officers import SUPPORT_SCOPE as CONTACTS_SCOPE
        from thetatauCMT.guides.services import get_whats_new
        from thetatauCMT.regions.dashboard import SUPPORT_SCOPE

        context = super().get_context_data(**kwargs)
        user = self.request.user
        whats_new = get_whats_new(user, include_acknowledged=True)
        rows = chapter_overview(css_chapters(user))
        context.update(
            {
                "rows": rows,
                "viewing": user.current_chapter,
                "member": is_member_account(user),
                "dashboard_scope": SUPPORT_SCOPE,
                "whats_new": whats_new,
                "seen_count": sum(1 for item in whats_new if item["is_acknowledged"]),
            }
        )
        if rows:
            # Sync the officers of these chapters into the CSS's own contacts (CSSWI-10).
            context.update(build_sync_modal_context(self.request, CONTACTS_SCOPE))
        return context


# --- Managing CSSs (CSSWI-5) ---------------------------------------------------------------


class CSSDirectoryAccessMixin(LoginRequiredMixin):
    """CSS managers, and National Officers read only (Q6)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_css_directory(request.user):
            messages.error(request, "Only National Officers can see the Chapter Support Specialists.")
            return HttpResponseRedirect(reverse("home"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = can_manage_css(self.request.user)
        return context


class CSSManagerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_manage_css(request.user):
            messages.error(request, "Only Chapter Support Specialist managers can do this.")
            fallback = "support:list" if can_view_css_directory(request.user) else "home"
            return HttpResponseRedirect(reverse(fallback))
        return super().dispatch(request, *args, **kwargs)


class CSSDirectoryView(CSSDirectoryAccessMixin, TemplateView):
    """Every current CSS and the chapters they cover."""

    template_name = "support/directory.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        people = list(current_css_users())
        chapters = defaultdict(list)
        current = ChapterSupportAssignment.objects.current().filter(user__in=people).select_related("chapter")
        for assignment in current.order_by("chapter__name"):
            chapters[assignment.user_id].append(assignment.chapter)
        upcoming = Counter(
            ChapterSupportAssignment.objects.upcoming().filter(user__in=people).values_list("user_id", flat=True)
        )
        context["rows"] = [
            {
                "person": person,
                "member": is_member_account(person),
                "chapters": chapters[person.pk],
                "upcoming": upcoming[person.pk],
            }
            for person in people
        ]
        return context


class CSSDetailView(CSSDirectoryAccessMixin, DetailView):
    """One CSS: current, upcoming and past assignments; managers assign and end them here."""

    template_name = "support/detail.html"
    context_object_name = "person"

    def get_queryset(self):
        return User.objects.filter(Q(roles__role=CSS_ROLE) | Q(support_assignments__isnull=False)).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = self.object
        today = timezone.localdate()
        assignments = person.support_assignments.select_related("chapter", "created_by", "ended_by")
        context.update(
            {
                "is_css": holds_css_role(person),
                "member": is_member_account(person),
                "css_roles": person.roles.filter(role=CSS_ROLE).order_by("-start"),
                "current": assignments.current().order_by("chapter__name"),
                "upcoming": assignments.upcoming().order_by("start"),
                "past": assignments.ended().order_by("-end"),
                "today": today,
                "yesterday": today - datetime.timedelta(days=1),
            }
        )
        if context["can_manage"] and context["is_css"]:
            context["assign_form"] = CSSAssignForm(css=person)
        return context


class CSSCreateView(CSSManagerRequiredMixin, FormView):
    template_name = "support/create.html"
    form_class = CSSCreateForm

    def form_valid(self, form):
        try:
            person, outcome = create_css_account(
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
            )
        except CSSAccountError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        if outcome == "member":
            messages.success(
                self.request,
                f"{person} keeps their account and membership and is now a Chapter Support Specialist. "
                "Assign their chapters below.",
            )
        else:
            EmailSupportWelcome(person).send()
            messages.success(
                self.request,
                f"{person} is now a Chapter Support Specialist. We emailed {person.email} a link to set "
                "their password. Assign their chapters below.",
            )
        return HttpResponseRedirect(reverse("support:detail", kwargs={"pk": person.pk}))


class CSSAssignView(CSSManagerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        person = get_object_or_404(User, pk=pk)
        detail = reverse("support:detail", kwargs={"pk": person.pk})
        form = CSSAssignForm(request.POST, css=person)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return HttpResponseRedirect(detail)
        data = form.cleaned_data
        try:
            assignment = assign_chapter(
                person, data["chapter"], start=data["start"], end=data["end"], notes=data["notes"], by=request.user
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return HttpResponseRedirect(detail)
        messages.success(request, f"{person} supports {assignment.chapter} from {_day(assignment.start)}.")
        return HttpResponseRedirect(detail)


class CSSEndAssignmentView(CSSManagerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        assignment = get_object_or_404(ChapterSupportAssignment.objects.select_related("user", "chapter"), pk=pk)
        person, chapter = assignment.user, assignment.chapter
        detail = reverse("support:detail", kwargs={"pk": person.pk})
        today = timezone.localdate()
        if assignment.end is not None and assignment.end < today:
            messages.error(request, f"{person}'s assignment to {chapter} has already ended.")
            return HttpResponseRedirect(detail)
        if assignment.start >= today:
            end_assignment(assignment, None, by=request.user)
            messages.success(request, f"Cancelled {person}'s assignment to {chapter}.")
            return HttpResponseRedirect(detail)
        form = CSSEndForm(request.POST)
        if not form.is_valid():
            messages.error(request, _form_errors(form))
            return HttpResponseRedirect(detail)
        try:
            end_assignment(assignment, form.cleaned_data["end"], by=request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return HttpResponseRedirect(detail)
        messages.success(request, f"{person} stops supporting {chapter} after {_day(assignment.end)}.")
        return HttpResponseRedirect(detail)


class CSSRemoveView(CSSManagerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        person = get_object_or_404(User, pk=pk)
        if not holds_css_role(person):
            messages.error(request, f"{person} is not a Chapter Support Specialist.")
            return HttpResponseRedirect(reverse("support:list"))
        staff = not is_member_account(person)
        remove_css(person, by=request.user)
        if staff:
            messages.success(
                request,
                f"{person} is no longer a Chapter Support Specialist. Their assignments have ended and their "
                "account is switched off.",
            )
        else:
            messages.success(
                request,
                f"{person} is no longer a Chapter Support Specialist. Their assignments have ended; they keep "
                "their member account.",
            )
        return HttpResponseRedirect(reverse("support:list"))


def _form_errors(form):
    return " ".join(str(error) for errors in form.errors.values() for error in errors)


def _day(value):
    return dateformat.format(value, "F j, Y")
