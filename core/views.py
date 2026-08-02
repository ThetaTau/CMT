from urllib.parse import urlparse, urlunparse

from braces.views import GroupRequiredMixin, LoginRequiredMixin
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin as DjangoLoginRequiredMixin
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import HttpResponseRedirect
from django.http.request import QueryDict
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin
from django_tables2 import SingleTableView
from django_tables2.config import RequestConfig  # Imported by others
from viewflow.frontend.views import AllTaskListView, DataTableMixin, FlowListMixin, TemplateResponseMixin, generic

from core.models import user_is_national_officer
from thetatauCMT.guides.services import get_role_guides, get_whats_new
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.tasks.models import TaskChapter, TaskDate
from thetatauCMT.tasks.tables import TaskTable
from thetatauCMT.users.models import User

# https://django-allauth.readthedocs.io/en/latest/advanced.html#admin
admin.site.login = login_required(admin.site.login)


def group_required(*group_names):
    """Requires user membership in at least one of the groups passed in."""

    def in_groups(u):
        if u.is_authenticated:
            if bool(u.groups.filter(name__in=group_names)) | u.is_superuser:
                return True
        return False

    return user_passes_test(in_groups)


class NatOfficerRequiredMixin(GroupRequiredMixin):
    group_required = "natoff"

    def check_membership(self, groups):
        # A National Officer previewing the site as a member (natoff_hidden) is
        # treated as a non-member so natoff-only pages become inaccessible too.
        if getattr(self.request.user, "natoff_hidden", False):
            return False
        return super().check_membership(groups)

    def get_login_url(self):
        if self.request.user.is_authenticated:
            messages.add_message(self.request, messages.ERROR, "Only National officers can edit this.")
            url = self.get_success_url()
        else:
            resolved_url = resolve_url(settings.LOGIN_URL)
            login_url_parts = list(urlparse(resolved_url))
            querystring = QueryDict(login_url_parts[4], mutable=True)
            querystring["next"] = self.get_success_url()
            login_url_parts[4] = querystring.urlencode(safe="/")
            url = urlunparse(login_url_parts)
        return url

    def get_success_url(self):
        return reverse("home")


AllTaskListView.dispatch = NatOfficerRequiredMixin.dispatch
AllTaskListView.check_membership = NatOfficerRequiredMixin.check_membership
AllTaskListView.get_group_required = NatOfficerRequiredMixin.get_group_required
AllTaskListView.group_required = NatOfficerRequiredMixin.group_required
AllTaskListView.handle_no_permission = NatOfficerRequiredMixin.handle_no_permission
AllTaskListView.__bases__ = (
    NatOfficerRequiredMixin,
    FlowListMixin,
    TemplateResponseMixin,
    DataTableMixin,
    generic.View,
)


class NationalOfficerRequiredMixin(DjangoLoginRequiredMixin):
    """Restrict a view to National Officers / Admins.

    Unlike :class:`NatOfficerRequiredMixin` (which checks only the ``natoff``
    Django group), qualification here is delegated to
    :func:`core.models.user_is_national_officer` — a superuser, membership in the
    ``natoff`` group, OR a current national-officer role. Authenticated users who
    do not qualify are redirected (default: ``home``) with an error message;
    unauthenticated users are handled by ``LoginRequiredMixin``.

    Views may override ``national_officer_redirect_url`` (a URL name or path) and
    ``national_officer_message``.
    """

    national_officer_redirect_url = "home"
    national_officer_message = "Only National Officers can access this."

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user_is_national_officer(user):
            messages.add_message(request, messages.ERROR, self.national_officer_message)
            return HttpResponseRedirect(resolve_url(self.national_officer_redirect_url))
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(DjangoLoginRequiredMixin):
    """Restrict a view to superusers (administrators) only.

    Authenticated non-superusers are redirected (default: ``home``) with an
    error message; unauthenticated users are handled by ``LoginRequiredMixin``.
    Views may override ``superuser_redirect_url`` and ``superuser_message``.
    """

    superuser_redirect_url = "home"
    superuser_message = "Only administrators can access this."

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user.is_superuser:
            messages.add_message(request, messages.ERROR, self.superuser_message)
            return HttpResponseRedirect(resolve_url(self.superuser_redirect_url))
        return super().dispatch(request, *args, **kwargs)


class OfficerRequiredMixin(GroupRequiredMixin):
    group_required = ["officer", "natoff"]
    officer_edit = "this"
    officer_edit_type = "edit"
    redirect_field_name = ""

    def get_login_url(self):
        if self.request.user.is_authenticated:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only officers can {self.officer_edit_type} {self.officer_edit}",
            )
            url = self.get_success_url()
        else:
            resolved_url = resolve_url(settings.LOGIN_URL)
            login_url_parts = list(urlparse(resolved_url))
            querystring = QueryDict(login_url_parts[4], mutable=True)
            querystring["next"] = self.get_success_url()
            login_url_parts[4] = querystring.urlencode(safe="/")
            url = urlunparse(login_url_parts)
        return url

    def get_success_url(self):
        return reverse("home")


class PagedFilteredTableView(SingleTableView):
    filter_class = None
    formhelper_class = None
    context_filter_name = "filter"
    filter_chapter = False
    filter_user_chapter = False
    filter = None

    def get_filter_kwargs(self):
        return {}

    def get_filter_helper_kwargs(self):
        return {}

    def get_queryset(self, **kwargs):
        other_qs = kwargs.get("other_qs", None)
        if other_qs is None:
            qs = super(PagedFilteredTableView, self).get_queryset()
        else:
            qs = other_qs
        cancel = self.request.GET.get("cancel", False)
        request_get = kwargs.get("request_get", self.request.GET.copy())
        if cancel:
            request_get = QueryDict()
        if self.filter_chapter:
            qs = qs.filter(chapter=self.request.user.current_chapter)
        elif self.filter_user_chapter:
            qs = qs.filter(user__chapter=self.request.user.current_chapter)
        self.filter = self.filter_class(request_get, queryset=qs, **self.get_filter_kwargs())
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class(**self.get_filter_helper_kwargs())
        if kwargs.get("clean_date", False):
            self.filter.form.full_clean()
            self.filter.form.cleaned_data.pop("date")
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super(PagedFilteredTableView, self).get_context_data()
        context[self.context_filter_name] = self.filter
        return context


class TypeFieldFilteredChapterAdd(FormMixin):
    score_type = "Evt"
    # Opt-in confirmation shown after a successful save. Subclasses set this to
    # a specific string (supports ``%(name)s`` / ``%(object)s`` placeholders
    # filled from the saved instance) so the user is told exactly what happened.
    success_message = ""

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        slug = self.kwargs.get("slug")
        score_obj = ScoreType.objects.filter(slug=slug) if slug else ScoreType.objects.none()
        if score_obj:
            form.initial = {"type": score_obj[0].pk}
            form.fields["type"].queryset = score_obj
        else:
            # A stale/unknown ScoreType slug (the row was renamed or deleted)
            # used to IndexError on ``score_obj[0]`` (issue #1033); fall back to
            # the default type dropdown instead of 500-ing.
            form.fields["type"].queryset = ScoreType.objects.filter(type=self.score_type).all().exclude(slug="article")
        return form

    def form_valid(self, form):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        if hasattr(form.instance, "user"):
            form.instance.user = self.request.user
        score_obj = form.instance.type
        task = score_obj.task.first()
        if task:
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        try:
            with transaction.atomic():
                response = super().form_valid(form)  # This saves the form
        except IntegrityError:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Name, date, and type together must be unique."
                " You can have the same name on different dates or different type.",
            )
            message = (
                "Name, date, and type together must be unique. "
                + f"Another {self.officer_edit} has the same name & date & type."
            )
            form.add_error("name", message)
            form.add_error("date", message)
            form.add_error("type", message)
            return self.render_to_response(self.get_context_data(form=form))
        if task:
            if next_date:
                prev_task = TaskChapter.check_previous(
                    task=next_date,
                    chapter=chapter,
                    date=timezone.now(),
                )
                if not prev_task:
                    TaskChapter(
                        task=next_date,
                        chapter=chapter,
                        date=timezone.now(),
                        submission_object=self.object,
                    ).save()
                else:
                    messages.add_message(self.request, messages.ERROR, f"Duplicate {self.officer_edit}!")
        success_message = self.get_success_message()
        if success_message:
            messages.add_message(self.request, messages.SUCCESS, success_message)
        return response

    def get_success_message(self):
        """Return the confirmation message shown after a successful save.

        Opt-in: returns ``""`` unless the subclass sets ``success_message`` (so
        views that manage their own messaging are unaffected). ``%(name)s`` and
        ``%(object)s`` placeholders are filled from the saved instance.
        """
        if not self.success_message:
            return ""
        obj = getattr(self, "object", None)
        try:
            return self.success_message % {
                "name": getattr(obj, "name", "") or str(obj or ""),
                "object": str(obj or ""),
            }
        except (KeyError, TypeError, ValueError):
            return self.success_message

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        descriptions = (
            ScoreType.objects.filter(type=self.score_type)
            .all()
            .values("id", "description", "formula", "points", "slug")
        )
        context["descriptions"] = descriptions
        return context


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.incomplete_dates_for_chapter(self.request.user.current_chapter)
        table = TaskTable(data=qs, complete=False)
        RequestConfig(self.request, paginate={"per_page": 40}).configure(table)
        context["table"] = table
        # The What's New feed (TWI-6) replaces the old raw announcement list: same
        # published announcements, now alongside recently released features and
        # each with a "Got it" button. Acknowledged items are still returned so
        # the template can tuck them behind a disclosure rather than vanishing
        # them -- nothing a user dismisses becomes unreachable.
        context["whats_new"] = get_whats_new(self.request.user, include_acknowledged=True)
        context["seen_count"] = sum(1 for item in context["whats_new"] if item["is_acknowledged"])
        # The Role Guide card (TWI-12) sits above the task table because that is
        # where a newly elected officer is already looking -- the tasks below it
        # are the very thing the guide explains.
        context["role_guides"] = get_role_guides(self.request.user)
        # Scope the embedded RegionDashboard to the viewer's own chapter so the
        # home page shows the same dashboard as the regional/national views, but
        # auto-filtered. The template renders this into a hidden element that the
        # dashboard reads client-side; a user without a chapter falls back to
        # the national scope.
        chapter = self.request.user.current_chapter
        if chapter is not None and getattr(chapter, "slug", None):
            context["dashboard_scope"] = f"chapter_{chapter.slug}"
        return context


class AssignOfficerFormMixin(object):
    def check_officers(self, officers):
        if not all(officers):
            missing = [
                [
                    "regent",
                    "scribe",
                    "vice regent",
                    "treasurer",
                    "corresponding secretary",
                ][ind]
                for ind, miss in enumerate(officers)
                if not miss
            ]
            messages.add_message(
                self.request,
                messages.ERROR,
                f"You must update the officers list! Missing officers: {missing}",
            )
            return False
        return True

    def assign_officers_form(self, users, form, officers):
        for officer in officers:
            # Should be in order [regent, scribe, vice, treasurer, corsec]
            if officer and officer not in users:
                if not hasattr(form.instance, "officer1"):
                    form.instance.officer1 = officer
                else:
                    form.instance.officer2 = officer
                    break
        if not hasattr(form.instance, "officer1"):
            form.instance.officer1 = User.objects.get(username=settings.EXECUTIVE_DIRECTOR)
        if not hasattr(form.instance, "officer2"):
            form.instance.officer2 = User.objects.get(username=settings.EXECUTIVE_DIRECTOR)
