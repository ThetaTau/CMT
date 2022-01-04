import csv
import datetime
from django.contrib import messages
from django.db.models import Count, F
from django.http.response import HttpResponseRedirect, HttpResponse
from django.http.request import QueryDict
from django.shortcuts import redirect, reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from django.forms.models import modelformset_factory
from core.views import (
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
    OfficerRequiredMixin,
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    RequestConfig,
)
from core.forms import MultiFormsView
from chapters.models import Chapter
from regions.models import Region
from scores.models import ScoreType
from .models import Submission, Picture, GearArticle
from .tables import SubmissionTable, GearArticleTable
from .filters import SubmissionListFilter, GearArticleListFilter
from .forms import (
    SubmissionListFormHelper,
    GearArticleForm,
    PictureForm,
    GearArticleListFormHelper,
)


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = Submission
    slug_field = "slug"
    slug_url_kwarg = "slug"


class SubmissionCreateView(
    LoginRequiredMixin,
    OfficerRequiredMixin,
    TypeFieldFilteredChapterAdd,
    CreateView,
):
    model = Submission
    score_type = "Sub"
    template_name_suffix = "_create_form"
    fields = [
        "name",
        "date",
        "type",
        "file",
    ]
    officer_edit = "submissions"
    officer_edit_type = "create"

    def get_success_url(self):
        return reverse("submissions:list")


class SubmissionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("submissions:list")


class SubmissionUpdateView(
    LoginRequiredMixin, OfficerRequiredMixin, TypeFieldFilteredChapterAdd, UpdateView
):
    fields = [
        "name",
        "date",
        "type",
        "file",
    ]
    model = Submission
    score_type = "Sub"
    officer_edit = "submissions"
    officer_edit_type = "edit"

    def get(self, request, *args, **kwargs):
        submission_id = self.kwargs.get("pk")
        try:
            submission = Submission.objects.get(pk=submission_id)
        except Submission.DoesNotExist:
            messages.add_message(
                request, messages.ERROR, "Submission could not be found!"
            )
        else:
            if "forms:" in submission.file.name:
                path, args = submission.file.name, None
                if " " in path:
                    path, args = path.split(" ")
                    url = reverse(path, args=[args])
                else:
                    url = reverse(path)
                return redirect(url)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        locked = False
        if "object" in context:
            if self.object.type.name in [
                "Adopted New Member Education Program",
                "Risk Management Program",
            ]:
                form = context["form"]
                for field_name, field in form.fields.items():
                    field.disabled = True
                locked = True
        context["locked"] = locked
        return context

    def get_success_url(self):
        return reverse("submissions:list")


class SubmissionListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Submission
    slug_field = "slug"
    slug_url_kwarg = "slug"
    context_object_name = "submission"
    ordering = ["-date"]
    table_class = SubmissionTable
    filter_class = SubmissionListFilter
    formhelper_class = SubmissionListFormHelper
    filter_chapter = True


class GearArticleFormView(LoginRequiredMixin, OfficerRequiredMixin, MultiFormsView):
    template_name = "submissions/gear.html"
    form_classes = {
        "gear": GearArticleForm,
        "picture": PictureForm,
    }
    grouped_forms = {"article": ["gear", "picture"]}

    def get_success_url(self):
        return reverse("submissions:list")

    def _group_exists(self, group_name):
        return False

    def forms_valid(self, forms):
        gear_form = forms["gear"]
        picture_forms = forms["picture"]
        submission = Submission(
            user=self.request.user,
            file=gear_form.cleaned_data.get("file"),
            name=gear_form.cleaned_data.get("name"),
            type=ScoreType.objects.get(name="Gear Article"),
            chapter=self.request.user.current_chapter,
        )
        submission.save()
        gear_form.instance.submission = submission
        gear_form.save()
        for picture_form in picture_forms:
            picture_form.instance.submission = gear_form.instance
            picture_form.save()
        return HttpResponseRedirect(self.get_success_url())

    def create_picture_form(self, **kwargs):
        factory = modelformset_factory(
            Picture, form=PictureForm, **{"can_delete": True, "extra": 1}
        )
        formset_kwargs = dict(queryset=Picture.objects.none())
        if self.request.method in ("POST", "PUT"):
            formset_kwargs.update(
                {"data": self.request.POST.copy(), "files": self.request.FILES.copy()}
            )
        return factory(**formset_kwargs)


class GearArticleDetailView(LoginRequiredMixin, UpdateView):
    model = GearArticle
    fields = [
        "reviewed",
        "notes",
    ]

    def get_success_url(self):
        return reverse("submissions:gearlist")


class GearArticleListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
    model = GearArticle
    context_object_name = "geararticle"
    table_class = GearArticleTable
    filter_class = GearArticleListFilter
    formhelper_class = GearArticleListFormHelper

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"GearArticle_ThetaTauOfficerExport_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            email_list = context["email_list_table"]
            if email_list:
                writer.writerow(["Chapter", "Officer Emails"])
                for chapter, emails in email_list.items():
                    writer.writerow([chapter, ", ".join(emails)])
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All submissions are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_queryset(self, **kwargs):
        qs = GearArticle.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel or not request_get:
            request_get = QueryDict(mutable=True)
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_gears = self.object_list.prefetch_related("submission", "pictures")
        all_gears = all_gears.values(
            "reviewed",
            "notes",
            "pk",
            pictures_count=Count("pictures"),
            date=F("submission__date"),
            title=F("submission__name"),
            chapter=F("submission__chapter__name"),
        )
        form_chapters = all_gears.values_list("submission__chapter__id", flat=True)
        region_slug = self.filter.form.cleaned_data["region"]
        region = Region.objects.filter(slug=region_slug).first()
        if region:
            missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(
                region__in=[region]
            )
        elif region_slug == "candidate_chapter":
            missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(
                candidate_chapter=True
            )
        else:
            missing_chapters = Chapter.objects.exclude(id__in=form_chapters)
        chapter_names = all_gears.values_list("chapter", flat=True)
        chapter_officer_emails = {
            chapter: [
                user.email
                for user in Chapter.objects.get(
                    name=chapter
                ).get_current_officers_council()[0]
            ]
            for chapter in chapter_names
        }
        table = GearArticleTable(data=all_gears)
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        context["email_list_table"] = chapter_officer_emails
        context["email_list"] = ", ".join(
            [
                email
                for chapter_emails in chapter_officer_emails.values()
                for email in chapter_emails
            ]
        )
        return context
