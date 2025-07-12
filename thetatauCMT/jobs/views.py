from django.urls import reverse
from django.views.generic import (
    DetailView,
    UpdateView,
    RedirectView,
    CreateView,
    FormView,
)
from django.db.models import Q
from django.http.request import QueryDict
from dal import autocomplete
from core.views import (
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
)
from .models import Job, Keyword, Major, JobSearch
from .tables import JobTable, JobSearchTable
from .filters import JobListFilter, JobSearchListFilter
from .forms import (
    JobListFormHelper,
    JobForm,
    JobSearchForm,
    JobSearchFormHelper,
    JobSearchListFormHelper,
)


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job


class JobCreateView(
    LoginRequiredMixin,
    CreateView,
):
    model = Job
    template_name = "jobs/job_create_form.html"
    form_class = JobForm

    def get_success_url(self):
        return reverse("jobs:list")


class JobSearchCreateView(
    LoginRequiredMixin,
    CreateView,
):
    model = JobSearch
    template_name = "jobs/jobsearch_create_form.html"
    officer_edit = "jobs"
    officer_edit_type = "create"
    form_class = JobSearchForm

    def get_success_url(self):
        return reverse("jobs:list")


class JobCopyView(JobCreateView):
    fields = [
        "title",
        "company",
        "education_qualification",
        "experience",
        "job_type",
        "sponsored",
        "title",
        "keywords",
        "location",
        "country",
    ]

    def get_job_initial(self):
        job = Job.objects.get(pk=self.kwargs["pk"])
        self.initial = {}
        return self.initial


class JobRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("jobs:list")


class JobSearchUpdateView(LoginRequiredMixin, UpdateView):
    model = JobSearch
    form_class = JobSearchForm
    template_name = "jobs/jobsearch_create_form.html"

    def get_success_url(self):
        return reverse("jobs:search")


class JobUpdateView(
    LoginRequiredMixin,
    UpdateView,
):
    form_class = JobForm
    model = Job

    def get_success_url(self):
        return reverse("jobs:list")

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class JobSearchListView(LoginRequiredMixin, PagedFilteredTableView):
    model = JobSearch
    context_object_name = "job search"
    ordering = ["-modified"]
    table_class = JobSearchTable
    filter_class = JobSearchListFilter
    formhelper_class = JobSearchListFormHelper
    filter_chapter = False


class JobListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Job
    context_object_name = "job"
    ordering = ["priority", "-publish_start"]
    table_class = JobTable
    filter_class = JobListFilter
    formhelper_class = JobListFormHelper
    filter_chapter = False
    search_object = None
    pk_url_kwarg = "pk"
    search_description_ands = None
    search_description_ors = None
    search_description_nots = None

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk is not None:
            self.search_object = JobSearch.objects.get(pk=pk)
        return super().get(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        self.queryset = self.model.get_live_jobs(request=self.request)
        queryset = super().get_queryset(**kwargs)
        if self.search_object is not None:
            (
                queryset,
                search_description_ands,
                search_description_ors,
                search_description_nots,
            ) = self.search_object.search(queryset)
            self.search_description_ands = search_description_ands
            self.search_description_ors = search_description_ors
            self.search_description_nots = search_description_nots
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_description_ands"] = self.search_description_ands
        context["search_description_ors"] = self.search_description_ors
        context["search_description_nots"] = self.search_description_nots
        context["search_object"] = self.search_object
        return context


class KeywordAutocomplete(autocomplete.Select2QuerySetView):
    def create_object(self, text):
        return super().create_object(text.lower())

    def get_queryset(self):
        qs = Keyword.objects.none()
        if self.request.user.is_authenticated:
            if self.q:
                qs = Keyword.objects.all()
                qs = qs.filter(Q(name__icontains=self.q))
        return qs.order_by("name")


class MajorAutocomplete(autocomplete.Select2QuerySetView):
    def create_object(self, text):
        return super().create_object(text.lower())

    def get_queryset(self):
        qs = Major.objects.none()
        if self.request.user.is_authenticated:
            if self.q:
                qs = Major.objects.all()
                qs = qs.filter(Q(name__icontains=self.q))
        return qs.order_by("name")
