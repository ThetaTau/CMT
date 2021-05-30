import csv
import datetime
from collections import defaultdict
from django.http import HttpResponse
from django.contrib import messages
from django.urls import reverse
from django.http.request import QueryDict
from django.db import models
from django.views.generic import DetailView, ListView, RedirectView
import django_tables2 as tables
from django_tables2.utils import A
from core.views import NatOfficerRequiredMixin, RequestConfig, LoginRequiredMixin
from core.models import combine_annotations
from .models import Region
from tasks.models import TaskDate
from chapters.models import Chapter
from .tables import RegionChapterTaskTable
from .filters import RegionChapterTaskFilter
from .forms import RegionChapterTaskFormHelper
from users.tables import UserTable
from users.models import User
from users.filters import UserRoleListFilter, AdvisorListFilter
from users.forms import UserRoleListFormHelper, AdvisorListFormHelper


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
            if emails != "":
                writer.writerow(context["table"].columns.names())
                for row in context["table"].as_values():
                    if row[2] in emails:
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
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist(
                "role",
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
        chapters = Chapter.objects.all()
        if self.filter.is_bound and self.filter.is_valid():
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                chapters = Chapter.objects.filter(region__in=[region])
            elif region_slug == "colony":
                chapters = Chapter.objects.filter(colony=True)
        all_chapter_officers = User.objects.none()
        for chapter in chapters:
            chapter_officers, _ = chapter.get_current_officers(combine=False)
            all_chapter_officers = chapter_officers | all_chapter_officers
        self.filter = self.filter_class(
            request_get, queryset=all_chapter_officers, request=self.request
        )
        self.filter.form.helper = self.formhelper_class()
        email_list = ", ".join(
            [x[0] for x in self.filter.qs.values_list("email").distinct()]
        )
        all_chapter_officers = combine_annotations(self.filter.qs)
        self.filter.form.fields["chapter"].queryset = chapters
        table = UserTable(
            data=all_chapter_officers,
            natoff=True,
            extra_columns=[
                (
                    "chapter",
                    tables.LinkColumn("chapters:detail", args=[A("chapter.slug")]),
                ),
                ("chapter.region", tables.Column("Region")),
                ("chapter.school", tables.Column("School")),
            ],
        )
        RequestConfig(self.request, paginate={"per_page": 50}).configure(table)
        context["table"] = table
        context["filter"] = self.filter
        context["email_list"] = email_list
        context["view_type"] = "Officers"
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
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("region", [self.object])
        self.filter = self.filter_class(request_get)
        chapters = Chapter.objects.all()
        if self.filter.is_bound and self.filter.is_valid():
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                chapters = Chapter.objects.filter(region__in=[region])
            elif region_slug == "colony":
                chapters = Chapter.objects.filter(colony=True)
        all_chapter_advisors = User.objects.none()
        for chapter in chapters:
            all_chapter_advisors = chapter.advisors | all_chapter_advisors
        self.filter = self.filter_class(request_get, queryset=all_chapter_advisors)
        self.filter.form.helper = self.formhelper_class()
        email_list = ", ".join(
            [x[0] for x in self.filter.qs.values_list("email").distinct()]
        )
        all_chapter_advisors = combine_annotations(self.filter.qs)
        self.filter.form.fields["chapter"].queryset = chapters
        table = UserTable(
            data=all_chapter_advisors,
            natoff=True,
            extra_columns=[
                (
                    "chapter",
                    tables.LinkColumn("chapters:detail", args=[A("chapter.slug")]),
                ),
                ("chapter.region", tables.Column("Region")),
                ("chapter.school", tables.Column("School")),
            ],
        )
        table.exclude = (
            "badge_number",
            "major",
            "graduation_year",
            "current_status",
            "role_end",
        )
        RequestConfig(self.request, paginate={"per_page": 50}).configure(table)
        context["table"] = table
        context["filter"] = self.filter
        context["email_list"] = email_list
        context["view_type"] = "Advisors"
        return context


class RegionDetailView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"


class RegionTaskView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = Region
    slug_field = "slug"
    slug_url_kwarg = "slug"
    filter_class = RegionChapterTaskFilter
    formhelper_class = RegionChapterTaskFormHelper
    template_name = "regions/task_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        all_chapters_tasks = {
            task.pk: defaultdict(lambda: 0) for task in self.filter.qs
        }
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
        for chapter in self.object.chapters.all():
            qs = TaskDate.dates_for_chapter(chapter)
            chapter_name = chapter.name.replace(" ", "_")
            column_name = f"{chapter_name}_column"
            column_link = f"{chapter_name}_complete_link"
            column_result = f"{chapter_name}_complete_result"
            qs = (
                qs.annotate(
                    **{
                        column_name: models.Case(
                            models.When(
                                models.Q(chapters__chapter=chapter),
                                models.Value(chapter.name),
                            ),
                            default=models.Value(chapter.name),
                            output_field=models.CharField(),
                        )
                    }
                )
                .annotate(
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
                .annotate(
                    **{
                        column_result: models.Case(
                            models.When(
                                models.Q(chapters__chapter=chapter),
                                models.Value("True"),
                            ),
                            default=models.Value(""),
                            output_field=models.CharField(),
                        )
                    }
                )
            )
            qs = qs.distinct()
            # Distinct sees incomplete/complete as different, so need to combine
            complete = qs.filter(**{column_result: True})
            incomplete = qs.filter(~models.Q(pk__in=complete), **{column_result: ""})
            all_tasks = complete | incomplete
            chapter_task_dict = all_tasks.values(
                "pk", column_name, column_link, column_result
            )
            [
                all_chapters_tasks[chapter_task["id"]].update(chapter_task)
                for chapter_task in chapter_task_dict.values()
                if chapter_task["id"] in all_chapters_tasks
            ]
            extra_columns.append(
                (
                    column_result,
                    tables.LinkColumn(
                        "tasks:detail",
                        verbose_name=chapter_name.replace("_", " "),
                        args=[A(column_link)],
                        empty_values=(),
                    ),
                )
            )
        all_chapters_tasks = all_chapters_tasks.values()
        table = RegionChapterTaskTable(
            data=all_chapters_tasks, extra_columns=extra_columns
        )
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
