from django.contrib import messages
from django.http.response import HttpResponseRedirect
from django.shortcuts import redirect, reverse
from django.views.generic import DetailView, UpdateView, RedirectView, CreateView
from django.forms.models import modelformset_factory
from core.views import (
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
    OfficerRequiredMixin,
    LoginRequiredMixin,
)
from core.forms import MultiFormsView
from scores.models import ScoreType
from .models import Submission, Picture
from .tables import SubmissionTable
from .filters import SubmissionListFilter
from .forms import SubmissionListFormHelper, GearArticleForm, PictureForm


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
