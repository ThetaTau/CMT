from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.request import QueryDict
from django.urls import reverse
from django_tables2 import SingleTableView
from django_tables2.config import RequestConfig  # Imported by others
from django.views.generic.edit import FormMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.db import transaction
from django.db.utils import IntegrityError
from django.contrib import messages
from scores.models import ScoreType
from tasks.models import TaskChapter, TaskDate
from tasks.tables import TaskIncompleteTable
from .utils import check_officer, check_nat_officer
from braces.views import GroupRequiredMixin
from viewflow.frontend.views import (
    AllTaskListView,
    FlowListMixin,
    TemplateResponseMixin,
    DataTableMixin,
    generic,
)


class NatOfficerRequiredMixin(GroupRequiredMixin):
    group_required = "natoff"

    def get_login_url(self):
        messages.add_message(
            self.request, messages.ERROR, f"Only National officers can edit this."
        )
        return self.get_success_url()

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


class OfficerRequiredMixin(GroupRequiredMixin):
    group_required = ["officer", "natoff"]
    officer_edit = "this"
    officer_edit_type = "edit"
    redirect_field_name = ""

    def get_login_url(self):
        messages.add_message(
            self.request,
            messages.ERROR,
            f"Only officers can {self.officer_edit_type} {self.officer_edit}",
        )
        return self.get_success_url()

    def get_success_url(self):
        return reverse("home")


class OfficerMixin:
    def dispatch(self, request, *args, **kwargs):
        request = check_nat_officer(request)
        request = check_officer(request)
        return super().dispatch(request, *args, **kwargs)


class PagedFilteredTableView(SingleTableView):
    filter_class = None
    formhelper_class = None
    context_filter_name = "filter"
    filter_chapter = False

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
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        slug = self.kwargs.get("slug")
        if slug:
            score_obj = ScoreType.objects.filter(slug=slug)
            form.initial = {"type": score_obj[0].pk}
            form.fields["type"].queryset = score_obj
        else:
            form.fields["type"].queryset = ScoreType.objects.filter(
                type=self.score_type
            ).all()
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
        except IntegrityError as e:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Name, date, and type together must be unique."
                " You can have the same name on different dates or different type.",
            )
            message = (
                f"Name, date, and type together must be unique. "
                + f"Another {self.officer_edit} has the same name & date & type."
            )
            form.add_error("name", message)
            form.add_error("date", message)
            form.add_error("type", message)
            return self.render_to_response(self.get_context_data(form=form))
        if task:
            if next_date:
                prev_task = TaskChapter.check_previous(
                    task=next_date, chapter=chapter, date=timezone.now(),
                )
                if not prev_task:
                    TaskChapter(
                        task=next_date,
                        chapter=chapter,
                        date=timezone.now(),
                        submission_object=self.object,
                    ).save()
                else:
                    messages.add_message(
                        self.request, messages.ERROR, f"Duplicate {self.officer_edit}!"
                    )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        descriptions = (
            ScoreType.objects.filter(type=self.score_type)
            .all()
            .values("id", "description", "formula", "points", "slug")
        )
        context["descriptions"] = descriptions
        return context


class HomeView(LoginRequiredMixin, OfficerMixin, TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.incomplete_dates_for_chapter(self.request.user.current_chapter)
        table = TaskIncompleteTable(qs)
        RequestConfig(self.request, paginate={"per_page": 40}).configure(table)
        context["table"] = table
        return context
