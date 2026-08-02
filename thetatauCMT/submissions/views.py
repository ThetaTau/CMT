import csv
import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, F
from django.forms.models import modelformset_factory
from django.http import Http404
from django.http.request import QueryDict
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, reverse
from django.views.generic import CreateView, DetailView, RedirectView, UpdateView

from core.forms import MultiFormsView
from core.notifications import GenericEmail
from core.views import (
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    PagedFilteredTableView,
    RequestConfig,
    TypeFieldFilteredChapterAdd,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.tasks.models import Task

from .filters import GearArticleListFilter, SubmissionListFilter
from .forms import GearArticleForm, GearArticleListFormHelper, PictureForm, SubmissionListFormHelper
from .models import GearArticle, Picture, Submission
from .tables import GearArticleTable, SubmissionTable


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = Submission
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        # The detail URL is date + slug based and slug is not unique, so more
        # than one submission can match; return the earliest to stay deterministic.
        obj = (
            Submission.objects.filter(
                date__year=self.kwargs["year"],
                date__month=self.kwargs["month"],
                date__day=self.kwargs["day"],
                slug=self.kwargs["slug"],
            )
            .order_by("pk")
            .first()
        )
        if obj is None:
            raise Http404("No submission matches the given query.")
        return obj


class SubmissionCreateView(
    LoginRequiredMixin,
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
    success_message = "Submission '%(name)s' was submitted."

    def get_success_url(self):
        name = None
        if not hasattr(self, "object"):
            return reverse("submissions:list")
        if self.object.type == "Lock-In and Goal Setting":
            name = "Lock-in"
        elif self.object.name == "Alumni Newsletter":
            name = "Newsletter for Alumni"
        if name:
            Task.mark_complete(
                name=name,
                chapter=self.request.user.current_chapter,
                user=self.request.user,
                obj=self.object,
            )
        return reverse("submissions:list")


class SubmissionRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("submissions:list")


class SubmissionUpdateView(LoginRequiredMixin, TypeFieldFilteredChapterAdd, UpdateView):
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
    success_message = "Submission '%(name)s' was updated."

    def get(self, request, *args, **kwargs):
        submission_id = self.kwargs.get("pk")
        try:
            submission = Submission.objects.get(pk=submission_id)
        except Submission.DoesNotExist:
            messages.add_message(request, messages.ERROR, "Submission could not be found!")
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

    def get_queryset(self, **kwargs):
        qs = super().get_queryset(**kwargs)
        qs = qs.exclude(type__slug="rmp")
        return qs


class GearArticleFormView(LoginRequiredMixin, MultiFormsView):
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
        chapter = self.request.user.current_chapter
        submission = Submission(
            user=self.request.user,
            file=gear_form.cleaned_data.get("file"),
            name=gear_form.cleaned_data.get("name"),
            type=ScoreType.objects.get(name="Gear Article"),
            chapter=chapter,
        )
        submission.save()
        gear_form.instance.submission = submission
        obj = gear_form.save()
        for picture_form in picture_forms:
            if picture_form.is_valid() and picture_form.instance.image.name != "":
                picture_form.instance.submission = gear_form.instance
                picture_form.save()
        link = reverse("submissions:gear_detail", kwargs={"pk": gear_form.instance.pk})
        link = settings.CURRENT_URL + link
        Task.mark_complete(
            name="Gear Article",
            chapter=chapter,
            user=self.request.user,
            obj=obj,
        )
        GenericEmail(
            emails=["gear@thetatau.org"],
            subject=f"{chapter.name} Gear Article Submission",
            message=(
                f"{chapter.name} Gear Article Submission <br>"
                f"Please see the form at: <a href='{link}'>{submission.name}</a>"
            ),
            cc=False,
            reply="cmt@thetatau.org",
            addressee="Dear Gear Editor",
        ).send()
        messages.add_message(
            self.request,
            messages.SUCCESS,
            f"Your Gear article '{submission.name}' was submitted to the Gear editor.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def create_picture_form(self, **kwargs):
        factory = modelformset_factory(Picture, form=PictureForm, **{"can_delete": True, "extra": 1})
        formset_kwargs = dict(queryset=Picture.objects.none())
        if self.request.method in ("POST", "PUT"):
            formset_kwargs.update({"data": self.request.POST.copy(), "files": self.request.FILES.copy()})
        return factory(**formset_kwargs)


class GearArticleDetailView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = GearArticle
    fields = [
        "reviewed",
        "notes",
    ]
    success_message = "Gear article review was saved."

    def get_success_url(self):
        return reverse("submissions:gearlist")


class GearArticleListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
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
        all_gears = GearArticle.objects.all().prefetch_related("submission", "pictures")
        all_gears = all_gears.values(
            "reviewed",
            "notes",
            "pk",
            pictures_count=Count("pictures"),
            date=F("submission__date"),
            title=F("submission__name"),
            chapter=F("submission__chapter__name"),
            chapter_slug=F("submission__chapter__slug"),
            candidate_chapter=F("submission__chapter__candidate_chapter"),
            region=F("submission__chapter__region__name"),
            region_slug=F("submission__chapter__region__slug"),
        )
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel or not request_get:
            request_get = QueryDict(mutable=True)
        self.filter = self.filter_class(request_get, queryset=all_gears)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_gears = self.object_list
        form_chapters = all_gears.values_list("chapter_slug", flat=True)
        region_slug = self.filter.form.cleaned_data["region"]
        region = Region.objects.filter(slug=region_slug).first()
        if region:
            missing_chapters = Chapter.objects.exclude(slug__in=form_chapters).filter(region__in=[region])
        elif region_slug == "candidate_chapter":
            missing_chapters = Chapter.objects.exclude(slug__in=form_chapters).filter(candidate_chapter=True)
        else:
            missing_chapters = Chapter.objects.exclude(slug__in=form_chapters)
        chapter_officer_emails = {
            chapter: [user.email for user in Chapter.objects.get(name=chapter).get_current_officers_council()[0]]
            for chapter in missing_chapters
        }
        table = GearArticleTable(data=all_gears)
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        context["email_list_table"] = chapter_officer_emails
        context["email_list"] = ", ".join(
            [email for chapter_emails in chapter_officer_emails.values() for email in chapter_emails]
        )
        return context
