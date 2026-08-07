import csv
import datetime
from collections import defaultdict

import django_tables2 as tables
from django.contrib import messages
from django.db import models
from django.http import HttpResponse
from django.http.request import QueryDict
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView, TemplateView
from django_tables2.utils import A

from core.csv_utils import escape_csv_row
from core.models import CHAPTER_ROLES
from core.views import LoginRequiredMixin, NatOfficerRequiredMixin, RequestConfig
from thetatauCMT.chapters.models import Chapter, advisors_in
from thetatauCMT.contact_sync.context import build_sync_modal_context
from thetatauCMT.tasks.models import TaskDate
from thetatauCMT.users.filters import AdvisorListFilter, UserRoleListFilter
from thetatauCMT.users.forms import AdvisorListFormHelper, UserRoleListFormHelper
from thetatauCMT.users.models import User
from thetatauCMT.users.tables import UserTable

from .filters import RegionChapterTaskFilter
from .forms import RegionChapterTaskFormHelper
from .models import Region
from .tables import RegionChapterTaskTable, TaskLinkColumn


def _contact_sync_context(request, region_slug):
    """Thin wrapper around :func:`contact_sync.context.build_sync_modal_context`.

    Retained as an internal helper so downstream tests can monkey-patch the
    context for a single region without touching the shared implementation.
    """
    return build_sync_modal_context(request, f"region:{region_slug}")


class RegionOfficerView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    filter_class = UserRoleListFilter
    formhelper_class = UserRoleListFormHelper
    template_name = "regions/officer_list.html"

    def get(self, request, *args, **kwargs):
        self.object = kwargs["slug"]
        context = self.get_context_data(object=kwargs["slug"])
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauOfficerExport_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            emails = context["email_list"]
            email_generic_map = context.get("email_generic_map", {})
            if emails != "":
                writer.writerow(list(context["table"].columns.names()) + ["Generic Officer Email"])
                for row in context["table"].as_values():
                    if row[4] and row[4] in emails:
                        writer.writerow(escape_csv_row(list(row) + [email_generic_map.get(row[4], "")]))
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All officers are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if "region" not in request_get:
            # The filter form always submits ``region``, so anything without it
            # (sort links, pagination, the CSV button) is not a filter change and
            # keeps this page's defaults instead of widening to every chapter.
            request_get.setlist(
                "current_roles",
                [
                    "corresponding secretary",
                    "regent",
                    "scribe",
                    "treasurer",
                    "vice regent",
                ],
            )
            request_get.setlist("region", [self.object])
        self.filter = self.filter_class(request_get, request=self.request)
        chapters = Chapter.objects.exclude(active=False)
        if self.filter.is_bound and self.filter.is_valid():
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                chapters = active_chapters.filter(region__in=[region])
            elif region_slug == "candidate_chapter":
                chapters = active_chapters.filter(candidate_chapter=True)
        # One query across every chapter. OR-ing a queryset per chapter piles up
        # subquery aliases and raised RecursionError on the larger regions.
        all_chapter_officers = User.objects.filter(chapter__in=chapters, current_roles__overlap=CHAPTER_ROLES)
        self.filter = self.filter_class(request_get, queryset=all_chapter_officers, request=self.request)
        self.filter.form.helper = self.formhelper_class()
        # Personal officer emails plus each officer's chapter generic mailbox(es)
        # for the role(s) they hold (e.g. the regent contributes the chapter's
        # ``email_regent``). ``email_generic_map`` keeps the association so the
        # CSV export can render the generic address alongside each officer.
        chapter_map = {chapter.pk: chapter for chapter in chapters}
        personal_emails = []
        generic_emails = []
        email_generic_map = {}
        for email, chapter_id, roles in self.filter.qs.values_list("email", "chapter_id", "current_roles").distinct():
            if email:
                personal_emails.append(email)
            chapter_obj = chapter_map.get(chapter_id)
            officer_generics = []
            if chapter_obj and roles:
                for role in roles:
                    generic = chapter_obj.generic_email_for_role(role)
                    if generic and generic not in officer_generics:
                        officer_generics.append(generic)
            generic_emails.extend(officer_generics)
            if email and officer_generics:
                email_generic_map[email] = "; ".join(officer_generics)
        seen = set()
        combined_emails = []
        for email in personal_emails + generic_emails:
            if email and email not in seen:
                seen.add(email)
                combined_emails.append(email)
        email_list = ", ".join(combined_emails)
        self.filter.form.fields["chapter"].queryset = chapters
        admin = self.request.user.is_admin
        table = UserTable(
            data=self.filter.qs,
            natoff=True,
            admin=admin,
            viewer=self.request.user,
            extra_columns=[
                (
                    "chapter",
                    tables.LinkColumn("chapters:detail", args=[A("chapter__slug")]),
                ),
                (
                    "chapter__region",
                    tables.LinkColumn("regions:detail", args=[A("chapter__region__slug")], verbose_name="Region"),
                ),
                ("chapter__school", tables.Column("School")),
            ],
        )
        RequestConfig(self.request, paginate={"per_page": 50}).configure(table)
        context["table"] = table
        context["filter"] = self.filter
        context["email_list"] = email_list
        context["email_generic_map"] = email_generic_map
        context["view_type"] = "Officers"
        context.update(_contact_sync_context(self.request, self.object))
        return context


class RegionAdvisorView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    filter_class = AdvisorListFilter
    formhelper_class = AdvisorListFormHelper
    template_name = "regions/officer_list.html"

    def get(self, request, *args, **kwargs):
        self.object = kwargs["slug"]
        context = self.get_context_data(object=kwargs["slug"])
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauOfficerExport_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            emails = context["email_list"]
            if emails != "":
                writer.writerow(context["table"].columns.names())
                email_index = context["table"].columns.names().index("email")
                for row in context["table"].as_values():
                    if row[email_index]:
                        if row[email_index] in emails:
                            writer.writerow(row)
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All officers are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if "region" not in request_get:
            # See RegionOfficerView: only a filter submit carries ``region``.
            request_get.setlist("region", [self.object])
        self.filter = self.filter_class(request_get)
        chapters = Chapter.objects.exclude(active=False)
        if self.filter.is_bound and self.filter.is_valid():
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                chapters = active_chapters.filter(region__in=[region])
            elif region_slug == "candidate_chapter":
                chapters = active_chapters.filter(candidate_chapter=True)
        # See RegionOfficerView: one query, not one per chapter.
        all_chapter_advisors = advisors_in(User.objects.filter(chapter__in=chapters))
        self.filter = self.filter_class(request_get, queryset=all_chapter_advisors)
        self.filter.form.helper = self.formhelper_class()
        email_list = ", ".join([x[0] for x in self.filter.qs.values_list("email").distinct()])
        self.filter.form.fields["chapter"].queryset = chapters
        admin = self.request.user.is_admin
        table = UserTable(
            data=self.filter.qs,
            natoff=True,
            admin=admin,
            viewer=self.request.user,
            extra_columns=[
                (
                    "chapter",
                    tables.LinkColumn("chapters:detail", args=[A("chapter__slug")]),
                ),
                (
                    "chapter__region",
                    tables.LinkColumn("regions:detail", args=[A("chapter__region__slug")], verbose_name="Region"),
                ),
                ("chapter__school", tables.Column("School")),
            ],
        )
        table.exclude = (
            "badge_number",
            "major",
            "graduation_year",
            "rmp_complete",
        )
        RequestConfig(self.request, paginate={"per_page": 50}).configure(table)
        context["table"] = table
        context["filter"] = self.filter
        context["email_list"] = email_list
        context["view_type"] = "Advisors"
        return context


class RegionDashboardView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    """National-officer analytics dashboard (plotly) for a region."""

    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "regions/region_dashboard.html"

    def get_object(self, queryset=None):
        # `candidate_chapter` and `national` are synthetic scopes surfaced in
        # `Region.region_choices()` (national == ALL chapters, not a per-region
        # filter). Neither is guaranteed to have a backing Region row, so fall
        # back to a synthetic instance (the dashboard template only reads
        # `.name`/`.slug`) instead of 404ing when the row is absent.
        slug = self.kwargs.get(self.slug_url_kwarg)
        if slug == "candidate_chapter":
            region = Region(name="Candidate Chapters")
            region.slug = "candidate_chapter"
            return region
        if slug == "national":
            region = Region.objects.filter(slug="national").first()
            if region is None:
                region = Region(name="National")
                region.slug = "national"
            return region
        return super().get_object(queryset)


class RegionDetailView(LoginRequiredMixin, DetailView):
    """Public-facing region detail page.

    Shows the region's details, its regional director(s), and the chapters that
    belong to the region. Visible to any authenticated member (linked from the
    chapter and region tables). The national-officer analytics dashboard lives
    at ``regions:dashboard``.
    """

    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "regions/region_detail.html"

    def get_object(self, queryset=None):
        slug = self.kwargs.get(self.slug_url_kwarg)
        if slug == "candidate_chapter":
            region = Region(name="Candidate Chapters")
            region.slug = "candidate_chapter"
            return region
        return super().get_object(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        region = self.object
        if region.pk is None:
            # Synthetic candidate_chapter scope — no real Region row/directors.
            chapters = Chapter.objects.filter(candidate_chapter=True)
            directors = User.objects.none()
        else:
            chapters = region.chapters.all()
            directors = region.directors.all()
        context["chapter_count"] = chapters.count()
        context["active_chapter_count"] = chapters.filter(active=True).count()
        context["chapters"] = chapters.select_related("region").order_by("name")
        context["directors"] = directors.order_by("last_name", "name")
        context["is_natoff"] = self.request.user.is_national_officer_group
        return context


class RegionTaskView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    filter_class = RegionChapterTaskFilter
    formhelper_class = RegionChapterTaskFormHelper
    template_name = "regions/task_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.objects.filter(archived=False)
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        all_chapters_tasks = {task.pk: defaultdict(lambda: None) for task in self.filter.qs}
        [
            all_chapters_tasks[task.id].update(
                {
                    "task_name": task.task.name,
                    "task_owner": task.task.owner,
                    "school_type": task.school_type,
                    "date": task.date,
                }
            )
            for task in self.filter.qs
        ]
        extra_columns = []
        for chapter in self.object.chapters.exclude(active=False):
            qs = TaskDate.dates_for_chapter(chapter)
            chapter_name = chapter.name.replace(" ", "_")
            column_link = f"{chapter_name}_complete_link"
            qs = qs.annotate(
                **{
                    column_link: models.Case(
                        models.When(
                            models.Q(chapters__chapter=chapter),
                            models.F("chapters__pk"),
                        ),
                        default=models.Value(0),
                    )
                }
            )
            qs = qs.distinct()
            # Distinct sees incomplete/complete as different, so need to combine
            complete = qs.exclude(**{column_link: 0})
            incomplete = qs.filter(**{column_link: 0})
            all_tasks = complete | incomplete
            chapter_task_dict = all_tasks.values("pk", column_link)
            [
                all_chapters_tasks[chapter_task["id"]].update(chapter_task)
                for chapter_task in chapter_task_dict.values()
                if chapter_task["id"] in all_chapters_tasks
            ]
            extra_columns.append(
                (
                    column_link,
                    TaskLinkColumn(verbose_name=chapter_name.replace("_", " "), empty_values=()),
                )
            )
        all_chapters_tasks = all_chapters_tasks.values()
        table = RegionChapterTaskTable(data=all_chapters_tasks, extra_columns=extra_columns)
        context["table"] = table
        context["filter"] = self.filter
        return context


class RegionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse(
            "regions:detail",
            kwargs={"slug": self.request.user.current_chapter.region.slug},
        )


class RegionListView(LoginRequiredMixin, ListView):
    model = Region
    # These next two lines tell the view to index lookups by username
    slug_field = "slug"
    slug_url_kwarg = "slug"


class EventAttendanceDashboardView(LoginRequiredMixin, NatOfficerRequiredMixin, TemplateView):
    """WI-9 — regional & national events + attendance review dashboard.

    Restricted to National Officers (same permission as the other region
    dashboards). Offers a region/national scope selector with the top-15
    attended events for that scope, plus a type-to-search national-event lookup
    that renders a chapter-by-chapter attendance-percentage breakdown built from
    the recorded snapshot values.
    """

    template_name = "regions/event_attendance_dashboard.html"

    def get_context_data(self, **kwargs):
        from thetatauCMT.attendance.forms import NationalEventLookupForm
        from thetatauCMT.attendance.services import national_event_chapter_breakdown, top_attended_events

        context = super().get_context_data(**kwargs)
        scope = self.request.GET.get("scope") or "national"
        valid_scopes = {"national", "candidate_chapter"} | set(Region.objects.values_list("slug", flat=True))
        if scope not in valid_scopes:
            scope = "national"
        context["scope"] = scope
        context["scope_choices"] = Region.region_choices()
        context["top_events"] = top_attended_events(scope=scope, limit=15)

        lookup_form = NationalEventLookupForm(self.request.GET or None)
        context["lookup_form"] = lookup_form
        breakdown_event = None
        if lookup_form.is_bound and lookup_form.is_valid():
            breakdown_event = lookup_form.cleaned_data.get("event")
        if breakdown_event is not None:
            context["breakdown_event"] = breakdown_event
            context["chapter_breakdown"] = national_event_chapter_breakdown(breakdown_event)
        return context
