from dal import autocomplete
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, RedirectView, UpdateView, View

from core.views import LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
from thetatauCMT.forms.notifications import CentralOfficeGenericEmail

from .filters import JobListFilter, JobSearchListFilter
from .forms import JobForm, JobListFormHelper, JobSearchForm, JobSearchListFormHelper
from .models import Job, JobPostingBan, JobSearch, Keyword, Major
from .notifications import notify_job_banned, notify_job_created, notify_job_deleted
from .tables import JobSearchTable, JobTable


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        is_owner = obj.created_by == request.user
        is_natoff = bool(getattr(request, "is_nat_officer", False)) or (
            request.user.is_authenticated and request.user.is_admin
        )
        if obj.deleted and not (is_owner or is_natoff):
            messages.error(request, f"The job {obj.title} is no longer available.")
            return redirect("jobs:list")
        if obj.is_pending_report_review and not (is_owner or is_natoff):
            messages.error(request, f"The job {obj.title} is not currently available.")
            return redirect("jobs:list")
        now = timezone.now().date()
        if (
            (obj.publish_start and now < obj.publish_start) or (obj.publish_end and now > obj.publish_end)
        ) and not is_owner:
            messages.error(request, f"The job {obj.title} is not currently available.")
            return redirect("jobs:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        context["creator_is_banned"] = job.created_by is not None and JobPostingBan.is_banned(job.created_by)
        try:
            context["creator_ban"] = getattr(job.created_by, "job_posting_ban", None)
        except JobPostingBan.DoesNotExist:
            context["creator_ban"] = None
        return context


class JobCreateView(
    LoginRequiredMixin,
    CreateView,
):
    model = Job
    template_name = "jobs/job_create_form.html"
    form_class = JobForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and JobPostingBan.is_banned(request.user):
            messages.error(
                request,
                "Your account has been barred from creating job postings. "
                "Please contact the Central Office if you believe this is in error.",
            )
            return redirect("jobs:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["user_is_natoff_or_superuser"] = bool(
            user.is_authenticated and (user.is_national_officer_group or user.is_admin)
        )
        return context

    def form_valid(self, form):
        user = self.request.user
        is_natoff = bool(user.is_authenticated and (user.is_national_officer_group or user.is_admin))
        if is_natoff:
            form.instance.approved = True
            form.instance.approved_at = timezone.now()
            form.instance.approved_by = user
            form.instance.approved_reason = "Auto-approved: posted by National Officer or superuser."
        response = super().form_valid(form)
        notify_job_created(self.object)
        messages.success(self.request, f"Your job posting '{self.object.title}' was created.")
        return response

    def get_success_url(self):
        return reverse("jobs:list")


class JobSearchCreateView(
    LoginRequiredMixin,
    SuccessMessageMixin,
    CreateView,
):
    model = JobSearch
    template_name = "jobs/jobsearch_create_form.html"
    officer_edit = "jobs"
    officer_edit_type = "create"
    form_class = JobSearchForm
    success_message = "Your job search was saved."

    def get_success_url(self):
        return reverse("jobs:search")


class JobCopyView(JobCreateView):
    """Clone an existing job posting into the create form.

    Only the job's creator (or a superuser) may clone; the view pre-fills
    the create form with the source posting's values so the user can edit
    and submit as a new posting.
    """

    _clone_fields = (
        "title",
        "company",
        "url",
        "contact",
        "other_contact",
        "education_qualification",
        "experience",
        "job_type",
        "majors_specific",
        "location_type",
        "country",
        "sponsored",
        "priority",
        "publish_start",
        "publish_end",
        "description",
    )
    _clone_m2m = ("keywords", "majors", "location")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        source = get_object_or_404(Job, pk=self.kwargs["pk"])
        if source.created_by != request.user and not request.user.is_admin:
            messages.error(request, "You can only clone jobs you created.")
            return redirect("jobs:detail", pk=source.pk, slug=source.slug)
        self._source_job = source
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        source = getattr(self, "_source_job", None) or get_object_or_404(Job, pk=self.kwargs["pk"])
        for name in self._clone_fields:
            if name in form.fields:
                form.fields[name].initial = getattr(source, name)
        form.fields["title"].initial = f"{source.title} (Copy)"
        for m2m_name in self._clone_m2m:
            if m2m_name not in form.fields:
                continue
            values = getattr(source, m2m_name).all()
            if not values:
                continue
            form.fields[m2m_name].initial = [str(v) for v in values]
            form.fields[m2m_name].choices = [(str(v), str(v)) for v in values.order_by("name")]
        return form


class JobRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("jobs:list")


class JobSearchUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = JobSearch
    form_class = JobSearchForm
    template_name = "jobs/jobsearch_create_form.html"
    success_message = "Your job search was updated."

    def get_success_url(self):
        return reverse("jobs:search")


class JobUpdateView(
    LoginRequiredMixin,
    SuccessMessageMixin,
    UpdateView,
):
    form_class = JobForm
    model = Job
    success_message = "Job posting '%(title)s' was updated."

    def get_success_url(self):
        return reverse("jobs:list")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.created_by != request.user:
            messages.error(request, "You are not allowed to edit the job.")
            return redirect("jobs:detail", pk=obj.pk, slug=obj.slug)
        return super().dispatch(request, *args, **kwargs)

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
            if pk == "0" or pk == 0:
                self.search_object = "user"
            else:
                self.search_object = JobSearch.objects.get(pk=pk)
        return super().get(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        self.queryset = self.model.get_live_jobs(request=self.request)
        queryset = super().get_queryset(**kwargs)
        if self.search_object == "user":
            # "My Jobs" shows the requesting user everything they created,
            # including postings that were reported or soft-deleted, so they
            # can open the detail page and see the audit reasons.
            own = self.model.objects.filter(created_by=self.request.user)
            queryset = super().get_queryset(other_qs=own, **kwargs)
        elif self.search_object is not None:
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
        context["user_is_banned"] = JobPostingBan.is_banned(self.request.user)
        return context


class VocabularyAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete for the free-text Keyword/Major vocabularies."""

    vocabulary_model = None
    max_name_length = 100
    validate_create = True

    def has_add_permission(self, request):
        # Any signed-in member may extend these vocabularies. The DAL default
        # requires the add_<model> model permission, which no CMT role grants,
        # so the "Create ..." option never appeared and the create POST 403'd.
        if self.create_field is None:
            return False
        return bool(request.user.is_authenticated)

    def validate(self, text):
        name = (text or "").strip()
        if not name:
            raise ValidationError({self.create_field: ["Enter a value before adding it."]})
        if len(name) > self.max_name_length:
            raise ValidationError({self.create_field: [f"Keep this to {self.max_name_length} characters or fewer."]})

    def create_object(self, text):
        name = text.strip().lower()
        # get_queryset() is search-scoped, so reuse the manager to avoid
        # inserting a duplicate row for a value that already exists.
        existing = self.vocabulary_model.objects.filter(name__iexact=name).first()
        return existing or self.vocabulary_model.objects.create(name=name)

    def get_queryset(self):
        qs = self.vocabulary_model.objects.none()
        # Require >= 2 chars so the endpoint can't be used to enumerate the
        # full list with a single character.
        if self.request.user.is_authenticated and self.q and len(self.q) >= 2:
            qs = self.vocabulary_model.objects.filter(Q(name__icontains=self.q))
        return qs.order_by("name")


class KeywordAutocomplete(VocabularyAutocomplete):
    model = Keyword
    vocabulary_model = Keyword


class MajorAutocomplete(VocabularyAutocomplete):
    model = Major
    vocabulary_model = Major


class JobReportView(LoginRequiredMixin, View):
    """Accept a POST from a signed-in user to report a job to the Central Office.

    Sets the ``reported`` flag on the job (recording who reported and why).
    Approved postings cannot be reported. Only the first report is emailed;
    subsequent reports on an already-flagged posting acknowledge silently.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs["pk"])
        if job.approved:
            messages.info(request, "This posting has already been reviewed and approved.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason before submitting the report.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = reason[:2000]
        if job.reported:
            messages.info(
                request,
                "This posting has already been reported and is pending Central Office review.",
            )
            return redirect("jobs:list")
        detail_path = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
        reporter = request.user
        reporter_name = reporter.get_full_name() or reporter.get_username()
        reporter_chapter = getattr(reporter, "current_chapter", "") or ""
        posted_by = job.created_by
        posted_by_line = f"{posted_by} ({posted_by.email})" if posted_by else "(unknown)"
        message = (
            f"<p>A member has reported a job posting for Central Office review.</p>"
            f"<p><strong>Job:</strong> {job.title}<br>"
            f"<strong>Company:</strong> {job.company}<br>"
            f"<strong>Posted by:</strong> {posted_by_line}<br>"
            f"<strong>Job detail:</strong> {detail_path}<br>"
            f"<strong>Original job link:</strong> {job.url}</p>"
            f"<p><strong>Reported by:</strong> {reporter_name} ({reporter.email})"
            f"{' - ' + str(reporter_chapter) if reporter_chapter else ''}</p>"
            f"<p><strong>Reason:</strong><br>{reason}</p>"
        )
        job.reported = True
        job.reported_at = timezone.now()
        job.reported_by = reporter
        job.reported_reason = reason
        job.save(
            update_fields=[
                "reported",
                "reported_at",
                "reported_by",
                "reported_reason",
                "modified",
            ]
        )
        try:
            CentralOfficeGenericEmail(
                message=message,
                subject=f"[CMT] Reported Job Posting: {job.title}",
            ).send()
        except Exception:
            messages.error(
                request,
                "There was a problem submitting your report. Please try again later.",
            )
        else:
            messages.success(
                request,
                "Thank you. Your report has been sent to the Central Office and the posting is now hidden pending review.",
            )
        return redirect("jobs:list")


class JobDeleteView(LoginRequiredMixin, NatOfficerRequiredMixin, View):
    """Soft-delete a job posting.

    National Officers (natoff group) and superusers can mark any job as
    deleted. The record is retained in the database with ``deleted=True``
    so it can be audited or restored, but is hidden from all listings and
    the detail view. Approved postings cannot be deleted via this action.
    A reason is required and stored for audit.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs["pk"])
        if job.approved:
            messages.info(request, "Approved postings cannot be deleted from this screen.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason before deleting the posting.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = reason[:2000]
        newly_deleted = False
        if not job.deleted:
            job.deleted = True
            job.deleted_at = timezone.now()
            job.deleted_by = request.user
            job.deleted_reason = reason
            job.save(
                update_fields=[
                    "deleted",
                    "deleted_at",
                    "deleted_by",
                    "deleted_reason",
                    "modified",
                ]
            )
            newly_deleted = True
        if newly_deleted:
            notify_job_deleted(job)
        messages.success(request, f'Job posting "{job.title}" was removed.')
        return redirect("jobs:list")


class JobApproveView(LoginRequiredMixin, NatOfficerRequiredMixin, View):
    """Approve a reported job posting.

    Only National Officers (natoff group) and superusers can approve a
    posting. Once approved, the posting is treated as reviewed and
    legitimate: the Report and Delete actions are no longer offered on
    the detail page, and the posting is visible in all listings again
    even if it was previously reported. A reason is required and stored
    for audit.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs["pk"])
        if job.approved:
            messages.info(request, f'Job posting "{job.title}" is already approved.')
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason before approving the posting.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = reason[:2000]
        job.approved = True
        job.approved_at = timezone.now()
        job.approved_by = request.user
        job.approved_reason = reason
        job.save(
            update_fields=[
                "approved",
                "approved_at",
                "approved_by",
                "approved_reason",
                "modified",
            ]
        )
        messages.success(request, f'Job posting "{job.title}" was approved.')
        return redirect("jobs:detail", pk=job.pk, slug=job.slug)


class JobBanUserView(LoginRequiredMixin, NatOfficerRequiredMixin, View):
    """Bar a member from creating any new job postings.

    Only National Officers (natoff group) and superusers can ban. Requires
    a reason. Uses the job's ``pk`` to identify the member to ban (that
    is, the ``created_by`` of the posting). A National Officer cannot ban
    themselves. Existing bans are treated as idempotent.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs["pk"])
        target = job.created_by
        if target is None:
            messages.error(request, "This posting has no creator on file, so no ban can be issued.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        if target == request.user:
            messages.error(request, "You cannot ban yourself from posting jobs.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason before banning the member.")
            return redirect("jobs:detail", pk=job.pk, slug=job.slug)
        reason = reason[:2000]
        ban, created = JobPostingBan.objects.get_or_create(
            user=target,
            defaults={
                "banned_at": timezone.now(),
                "banned_by": request.user,
                "reason": reason,
            },
        )
        if created:
            # Soft-delete every existing posting by the banned member so it is
            # removed from the public listing along with the ban. Skip any
            # posting that was already deleted so its original delete audit
            # (deleted_by / deleted_at / deleted_reason) is preserved.
            delete_note = f"User banned by {ban.banned_by} on {ban.banned_at:%Y-%m-%d %H:%M}: {ban.reason}"
            affected = Job.objects.filter(created_by=target, deleted=False).update(
                deleted=True,
                deleted_at=ban.banned_at,
                deleted_by=ban.banned_by,
                deleted_reason=delete_note,
            )
            notify_job_banned(ban, affected_count=affected)
            messages.success(
                request,
                f"{target} has been barred from creating new job postings."
                + (f" {affected} existing posting(s) were removed." if affected else ""),
            )
        else:
            messages.info(request, f"{target} is already barred from creating job postings.")
        return redirect("jobs:detail", pk=job.pk, slug=job.slug)
