from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.request import QueryDict
from django_tables2 import SingleTableView
from django_tables2.config import RequestConfig  # Imported by others
from django.views.generic.edit import FormMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.contrib import messages
from scores.models import ScoreType
from tasks.models import TaskChapter, TaskDate
from tasks.tables import TaskIncompleteTable
from .utils import check_officer, check_nat_officer
from braces.views import GroupRequiredMixin


class NatOfficerRequiredMixin(GroupRequiredMixin):
    group_required = u"natoff"

    def get_login_url(self):
        messages.add_message(
            self.request, messages.ERROR,
            f"Only National officers can edit this.")
        return self.get_success_url()


class OfficerRequiredMixin(GroupRequiredMixin):
    group_required = u"officer"
    officer_edit = 'this'
    officer_edit_type = 'edit'
    redirect_field_name = ""

    def get_login_url(self):
        messages.add_message(
            self.request, messages.ERROR,
            f"Only officers can {self.officer_edit_type} {self.officer_edit}")
        return self.get_success_url()


class OfficerMixin:
    def dispatch(self, request, *args, **kwargs):
        request = check_nat_officer(request)
        request = check_officer(request)
        return super().dispatch(request, *args, **kwargs)


class PagedFilteredTableView(SingleTableView):
    filter_class = None
    formhelper_class = None
    context_filter_name = 'filter'

    def get_queryset(self, **kwargs):
        qs = super(PagedFilteredTableView, self).get_queryset()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super(PagedFilteredTableView, self).get_context_data()
        context[self.context_filter_name] = self.filter
        return context


class TypeFieldFilteredChapterAdd(FormMixin):
    score_type = "Evt"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        slug = self.kwargs.get('slug')
        if slug:
            score_obj = ScoreType.objects.filter(slug=slug)
            form.initial = {'type': score_obj[0].pk}
            form.fields['type'].queryset = score_obj
        else:
            form.fields['type'].queryset = ScoreType.objects.filter(
                type=self.score_type).all()
        return form

    def form_valid(self, form):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        score_obj = form.instance.type
        task = score_obj.task.first()
        if task:
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        response = super().form_valid(form)  # This saves the form
        if task:
            if next_date:
                TaskChapter(task=next_date, chapter=chapter,
                            date=timezone.now(),
                            submission_object=self.object).save()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        descriptions = ScoreType.objects.filter(
            type=self.score_type).all().values(
                'id', 'description', 'formula', 'points', 'slug')
        context['descriptions'] = descriptions
        return context


class HomeView(LoginRequiredMixin, OfficerMixin, TemplateView):
    template_name = 'pages/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = TaskDate.incomplete_dates_for_chapter(self.request.user.current_chapter)
        table = TaskIncompleteTable(qs)
        RequestConfig(self.request, paginate={'per_page': 40}).configure(table)
        context['table'] = table
        return context
