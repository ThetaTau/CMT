from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from core.views import (
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
    OfficerRequiredMixin,
)
from .models import Submission
from .tables import SubmissionTable
from .filters import SubmissionListFilter
from .forms import SubmissionListFormHelper


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    model = Submission
    slug_field = "slug"
    slug_url_kwarg = "slug"


class SubmissionCreateView(
    OfficerRequiredMixin, LoginRequiredMixin, TypeFieldFilteredChapterAdd, CreateView,
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
    OfficerRequiredMixin, LoginRequiredMixin, TypeFieldFilteredChapterAdd, UpdateView
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
