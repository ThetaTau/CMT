import base64
import csv
import datetime
import logging
import zipfile
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from allauth.account.models import EmailAddress
from crispy_forms.layout import Submit
from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.postgres.aggregates import StringAgg
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Case, CharField, Count, Exists, F, OuterRef, Q, SmallIntegerField, Subquery, Value, When
from django.forms import models as model_forms
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.http.request import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, TemplateView, UpdateView
from django.views.generic.edit import CreateView, FormView, ModelFormMixin
from django_weasyprint import WeasyTemplateResponseMixin
from easy_pdf.views import PDFTemplateResponseMixin
from extra_views import FormSetView
from viewflow.activation import STATUS
from viewflow.flow.views import CreateProcessView, UpdateProcessView
from viewflow.frontend.viewset import FlowViewSet
from viewflow.models import Task as FlowTask

from core.flows import AutoAssignUpdateProcessView, FilterProcessListView, cancel_process, complete_activation
from core.forms import MultiFormsView
from core.models import (
    CHAPTER_OFFICER,
    CHAPTER_ROLES,
    COL_OFFICER_ALIGN,
    NAT_OFFICERS,
    SEMESTER,
    TODAY_END,
    current_term,
    current_year,
    current_year_term_slug,
    semester_encompass_start_end_date,
)
from core.notifications import GenericEmail
from core.utils import retry_google_api, retry_on_deadlock
from core.views import (
    ActiveMemberRequiredMixin,
    AssignOfficerFormMixin,
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    OfficerRequiredMixin,
    PagedFilteredTableView,
    RequestConfig,
    SuperuserRequiredMixin,
    group_required,
)
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.configs.models import Config
from thetatauCMT.forms.notifications import CentralOfficeGenericEmail, TreasurerTermException
from thetatauCMT.guides import services as guide_services
from thetatauCMT.regions.models import Region
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.submissions.models import Submission
from thetatauCMT.surveys.notifications import DepledgeSurveyEmail, SurveyEmail
from thetatauCMT.tasks.models import Task
from thetatauCMT.trainings.models import Training
from thetatauCMT.users.forms import UserForm
from thetatauCMT.users.models import User, UserRoleChange
from thetatauCMT.users.notifications import NewOfficers
from thetatauCMT.users.tables import RollBookTable

from .filters import (
    AlumniExclusionListFilter,
    AuditListFilter,
    BylawsListFilter,
    CompleteListFilter,
    EducationListFilter,
    GraduationListFilter,
    PledgeProgramListFilter,
    RiskListFilter,
    RoleChangeListFilter,
    RoleChangeNationalListFilter,
    StatusChangeListFilter,
)
from .forms import (
    AlumniExclusionForm,
    AlumniExclusionFormHelper,
    AlumniExclusionReviewForm,
    AuditForm,
    AuditListFormHelper,
    BylawsForm,
    BylawsListFormHelper,
    CollectionReferralForm,
    CompleteFormHelper,
    ConventionForm,
    DepledgeFormHelper,
    DepledgeFormSet,
    DisciplinaryForm1,
    DisciplinaryForm2,
    GraduateFormHelper,
    GraduateFormSet,
    GraduateSelectForm,
    HSEducationForm,
    HSEducationListFormHelper,
    InitDeplSelectForm,
    InitDeplSelectFormHelper,
    InitiationForm,
    InitiationFormHelper,
    InitiationFormSet,
    NationalOfficerAddForm,
    OfficerAddForm,
    OfficerRoleEditForm,
    OSMForm,
    PledgeFormFull,
    PledgeProgramForm,
    PledgeProgramFormHelper,
    PrematureAlumnusForm,
    ResignationForm,
    ReturnStudentForm,
    RiskListFormHelper,
    RiskManagementForm,
    RitualProficiencyForm,
    RoleChangeListFormHelper,
    RoleChangeNationalListFormHelper,
    SingleStatusChangeForm,
    SingleStatusChangeFormHelper,
    StatusChangeListFormHelper,
    treasurer_term_violation,
)
from .models import (
    OSM,
    AlumniExclusion,
    Audit,
    Badge,
    Bylaws,
    CollectionReferral,
    Convention,
    Depledge,
    DisciplinaryProcess,
    Employer,
    HSEducation,
    InitiationProcess,
    OtherSchool,
    PledgeProcess,
    PledgeProgram,
    PledgeProgramProcess,
    PrematureAlumnus,
    ResignationProcess,
    ReturnStudent,
    RiskManagement,
    RitualProficiency,
    StatusChange,
    employer_from_text,
)
from .notifications import EmailPledgeConfirmation, EmailPledgeOfficer, EmailProcessUpdate, EmailRMPSigned
from .tables import (
    AlumniExclusionTable,
    AuditTable,
    BadgeTable,
    BylawsListTable,
    CollectionReferralTable,
    ConventionListTable,
    CoopStatusChangeTable,
    DepledgeTable,
    DisciplinaryStatusTable,
    GraduateStatusChangeTable,
    HSEducationListTable,
    HSEducationTable,
    InitiationTable,
    MilitaryStatusChangeTable,
    NationalOfficerRoleTable,
    OfficerRoleTable,
    OSMListTable,
    PledgeFormTable,
    PledgeProgramStatusTable,
    PledgeProgramTable,
    PrematureAlumnusStatusTable,
    ResignationStatusTable,
    ResignedCCStatusChangeTable,
    ReturnStudentStatusTable,
    RiskFormTable,
    RitualProficiencyTable,
    SignTable,
    TransferStatusChangeTable,
    WithdrawStatusChangeTable,
)

logger = logging.getLogger(__name__)


# Registry of the per-reason member status-change forms. Each split form has its
# own landing row, a chapter-scoped filterable history table, and a submission
# page — all driven from this one place (configuration over hard-coded per-reason
# branching). ``multi`` marks graduation (select several members, fill one row
# each); ``candidate_only`` marks reasons offered only to candidate chapters.
STATUS_CHANGE_TYPES = {
    "graduate": {
        "label": "Graduation",
        "description": (
            "Report members who are graduating. Select several at once and fill " "one graduation row for each."
        ),
        "table": GraduateStatusChangeTable,
        "filter": GraduationListFilter,
        "multi": True,
        "candidate_only": False,
    },
    "coop": {
        "label": "Co-op / Study Abroad",
        "description": "Report a member leaving temporarily for a co-op, internship, or study abroad.",
        "table": CoopStatusChangeTable,
        "filter": StatusChangeListFilter,
        "multi": False,
        "candidate_only": False,
    },
    "military": {
        "label": "Military Deployment",
        "description": "Report a member being deployed on active or reserve military duty.",
        "table": MilitaryStatusChangeTable,
        "filter": StatusChangeListFilter,
        "multi": False,
        "candidate_only": False,
    },
    "withdraw": {
        "label": "Withdraw from School",
        "description": "Report a member withdrawing from school.",
        "table": WithdrawStatusChangeTable,
        "filter": StatusChangeListFilter,
        "multi": False,
        "candidate_only": False,
    },
    "transfer": {
        "label": "Transfer to Another School",
        "description": "Report a member transferring to another school.",
        "table": TransferStatusChangeTable,
        "filter": StatusChangeListFilter,
        "multi": False,
        "candidate_only": False,
    },
    "resignedCC": {
        "label": "Resign from Candidate Chapter",
        "description": "Report a candidate-chapter member resigning from the candidate chapter.",
        "table": ResignedCCStatusChangeTable,
        "filter": StatusChangeListFilter,
        "multi": False,
        "candidate_only": True,
    },
}


# Purpose groups for the forms landing (TWI-9b). Configuration, not markup: the
# copy for each row lives in the feature registry, and this only says which
# registry entries belong together and in what order. Everything visible in the
# `forms-workflows` area that no group claims still renders, under "Everything
# else", so adding a registry entry can never make a form disappear from here.
# ``chip`` is the short form of ``label`` used by the filter buttons, which need
# to sit on one line.
FORM_GROUPS = [
    {
        "key": "membership",
        "label": "Members joining, changing and leaving",
        "chip": "Membership",
        "description": (
            "Anything that changes who is on your roster. These drive what the chapter is invoiced, "
            "so file them promptly rather than in a batch at the end of term."
        ),
        "features": [
            "pledge-form",
            "pledge-pins",
            "new-member-education-program",
            "all-nme-programs",
            "initiation-report",
            "roll-book-page",
            "status-change-graduate",
            "status-change-coop",
            "status-change-military",
            "status-change-withdraw",
            "status-change-transfer",
            "premature-alumnus",
            "return-student",
            "resignation",
            "resignations-list",
            "alumni-exclusion",
            "alumni-exclusion-list",
        ],
    },
    {
        "key": "administration",
        "label": "Officer and chapter administration",
        "chip": "Administration",
        "description": "Who holds office, what the chapter's governing documents say, and reporting to headquarters.",
        "features": [
            "chapter-officers",
            "submit-chapter-officers",
            "national-officers-directory",
            "chapter-bylaws",
            "all-bylaws",
            "convention-form",
            "all-convention-forms",
            "gear-article",
            "all-gear-articles",
        ],
    },
    {
        "key": "risk",
        "label": "Risk and compliance",
        "chip": "Risk",
        "description": "The obligations the fraternity's insurance and its standards depend on. None of these is optional.",
        "features": [
            "risk-management-policies",
            "all-rmp-signatures",
            "hs-education-program",
            "all-hs-education-reports",
            "disciplinary-process",
            "bill-of-rights",
            "ritual-proficiency",
        ],
    },
    {
        "key": "money",
        "label": "Money",
        "chip": "Money",
        "description": "The chapter's finances, and what to do when a member will not pay.",
        "features": [
            "chapter-audit-form",
            "all-audits",
            "collection-referral",
        ],
    },
    {
        "key": "recognition",
        "label": "Recognition and voting",
        "chip": "Recognition",
        "description": "Putting members forward, and the ballots the chapter casts.",
        "features": [
            "osm-form",
            "all-osm-forms",
            "award-nomination",
            "award-catalog",
            "award-winners-directory",
            "grant-an-award",
            "nominate-for-national-office",
            "all-volunteer-nominations",
            "my-ballots",
        ],
    },
    {
        "key": "national",
        "label": "National administration",
        "chip": "National",
        "description": "Bulk tools for national events. Only National Officers see this section.",
        "features": [
            "national-attendance-upload",
            "attendance-match-queue",
        ],
    },
]


class FormLanding(LoginRequiredMixin, TemplateView):
    """The forms landing, rebuilt from the feature registry (TWI-9b).

    The old page was one alphabetical table that users described as useless. This
    one groups by what you are trying to get done, pins the forms your own office
    owns, and shows live due dates from the same ``tasks.Task`` rows the home page
    reads -- so it answers "what do I owe" rather than "what forms exist".

    Nothing about it is hand-maintained: rows, copy, audiences and feature flags
    all come from ``guides/fixtures/feature_registry.json``.
    """

    template_name = "forms/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
        context["groups"] = groups
        context["duty_roles"] = sorted(guide_services.get_duty_roles(user))
        # "For your role" is a pinned view of rows already on the page rather than
        # a second query: the same entry object appears in both places.
        context["mine"] = [entry for group in groups for entry in group["entries"] if entry["duty_roles"]]
        return context


class PledgePinsView(ActiveMemberRequiredMixin, TemplateView):
    template_name = "forms/pledge_pins.html"


class InitDeplSelectView(LoginRequiredMixin, FormSetView):
    form_class = InitDeplSelectForm
    template_name = "forms/init-depl-select.html"
    factory_kwargs = {"extra": 0}
    officer_edit = "pledge status"

    def get_initial(self):
        pledges = self.request.user.current_chapter.pledges()
        initial = [{"user": user.pk} for user in pledges]
        return initial

    def get_formset(self):
        pledges = self.request.user.current_chapter.pledges()
        formset = super().get_formset()
        formset.form.base_fields["user"].queryset = pledges
        formset.empty_form = []
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        helper = InitDeplSelectFormHelper()
        helper.add_input(Submit("submit", "Next"))
        context["helper"] = helper
        processes = InitiationProcess.objects.filter(chapter__name=self.request.user.current_chapter)
        initiation_data = []
        for process in processes:
            active_task = process.active_tasks().first()
            status = active_task
            if active_task:
                if active_task.flow_task:
                    status = active_task.flow_task.task_description
            else:
                status = "Initiation Process Complete"
            members = ", ".join(list(process.initiations.values_list("user__name", flat=True)))
            initiation_data.append(
                {
                    "initiation": process.initiations.first().date,
                    "submitted": process.created,
                    "status": status,
                    "member_names": members,
                }
            )
        pledgeprocesses = PledgeProcess.objects.filter(chapter__name=self.request.user.current_chapter)
        pledge_data = []
        for process in pledgeprocesses:
            active_task = process.active_tasks().first()
            if active_task:
                status = active_task.flow_task.task_description
            else:
                status = "Pledge Process Complete"
            pledges = ", ".join(process.pledges.values_list("user__name", flat=True))
            last_pledge = process.pledges.last()
            pledge_created = None
            if last_pledge:
                pledge_created = last_pledge.created
            pledge_data.append(
                {
                    "last_pledge": pledge_created,
                    "first_pledge": process.created,
                    "status": status,
                    "pledge_names": pledges,
                }
            )
        pledges = PledgeFormTable(data=pledge_data, order_by="-submitted")
        inits = InitiationTable(data=initiation_data, order_by="-submitted")
        depledges = DepledgeTable(
            Depledge.objects.filter(user__chapter=self.request.user.current_chapter).order_by("-date")
        )
        RequestConfig(self.request).configure(inits)
        RequestConfig(self.request).configure(depledges)
        context["pledges_table"] = pledges
        context["init_table"] = inits
        context["depledge_table"] = depledges
        return context

    def formset_valid(self, formset):
        cleaned_data = deepcopy(formset.cleaned_data)
        selections = {"Initiate": [], "Depledge": [], "Defer": [], "Roll": []}
        for info in cleaned_data:
            user = info["user"]
            selections[info["state"]].append(user.pk)
        self.request.session["init-selection"] = selections
        return super().formset_valid(formset)

    def get_success_url(self):
        # This needs to redirect to the next step in the process
        return reverse("forms:initiation")


@group_required("officer")
@csrf_exempt
def set_init_date(request):
    init_date = request.POST.get("init_date")
    request.session["init_date"] = init_date
    return HttpResponse(f"Initiation date set to: {init_date}")


@group_required("officer")
@csrf_exempt
def download_all_rollbook(request):
    time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"RollBookPages_{time_name}.zip"
    initiate = request.session.get("init-selection", None)
    pledges = request.user.current_chapter.pledges()
    to_roll = pledges.filter(pk__in=initiate["Roll"])
    zip_io = BytesIO()
    with zipfile.ZipFile(zip_io, "w") as zf:
        for user in to_roll:
            new_request = HttpRequest()
            new_request.method = "GET"
            new_request.user = request.user
            new_request.session = request.session
            new_request.META = request.META
            view = RollBookPDFDownload.as_view()
            roll_view = view(new_request, pk=user.pk)
            roll_file = roll_view.rendered_content
            zf.writestr(f"RollBookPage_{user.chapter.slug}_{user.id}.pdf", roll_file)
    response = HttpResponse(zip_io.getvalue(), content_type="application/x-zip-compressed")
    response["Cache-Control"] = "no-cache"
    response["Content-Disposition"] = f"attachment; filename={zip_filename}"
    return response


class InitiationView(LoginRequiredMixin, OfficerRequiredMixin, FormView):
    form_class = InitiationForm
    template_name = "forms/initiation.html"
    to_initiate = []
    to_depledge = []
    to_defer = []
    next_badge = 999999
    officer_edit = "pledge status"

    def initial_info(self, initiate):
        pledges = self.request.user.current_chapter.pledges()
        self.to_initiate = pledges.filter(pk__in=initiate["Initiate"])
        self.to_depledge = pledges.filter(pk__in=initiate["Depledge"])
        self.to_defer = pledges.filter(pk__in=initiate["Defer"])
        self.to_roll = pledges.filter(pk__in=initiate["Roll"])
        self.next_badge = self.request.user.current_chapter.next_badge_number()

    def get(self, request, *args, **kwargs):
        initiate = request.session.get("init-selection", None)
        if initiate is None:
            return redirect("forms:init_selection")
        else:
            self.initial_info(initiate)
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.to_roll:
            data = self.to_roll.values(
                "pk",
                "name",
                "email",
                "graduation_year",
                "phone_number",
                "birth_date",
                address_formatted=F("address__formatted"),
                rollbook=Value("Link", output_field=CharField()),
                major_name=F("major__major"),
                birth_place=F("pledge_form__birth_place"),
                other_degrees=F("pledge_form__other_degrees"),
            )
            context["roll_table"] = RollBookTable(data=data)
        else:
            formset = kwargs.get("formset", None)
            if formset is None:
                formset = InitiationFormSet(prefix="initiates")
            formset.initial = [
                {"user": user, "roll": self.next_badge + num} for num, user in enumerate(self.to_initiate)
            ]
            chapter = self.request.user.current_chapter
            if chapter.candidate_chapter:
                formset.form.base_fields["badge"].queryset = Badge.objects.filter(
                    Q(name__icontains="Candidate Chapter")
                )
            else:
                formset.form.base_fields["badge"].queryset = Badge.objects.filter(
                    ~Q(name__icontains="Candidate Chapter")
                )
            context["formset"] = formset
            context["helper"] = InitiationFormHelper()
            depledge_formset = kwargs.get("depledge_formset", None)
            if depledge_formset is None:
                depledge_formset = DepledgeFormSet(prefix="depledges")
            depledge_formset.initial = [{"user": user.name} for user in self.to_depledge]
            context["depledge_formset"] = depledge_formset
            context["depledge_helper"] = DepledgeFormHelper()
            context["form_show_errors"] = True
            context["error_text_inline"] = True
            context["help_text_inline"] = True
            badges = BadgeTable(Badge.objects.all().order_by("name"))
            RequestConfig(self.request).configure(badges)
            context["badge_table"] = badges
        return context

    def post(self, request, *args, **kwargs):
        initiate = request.session.get("init-selection", None)
        self.initial_info(initiate)
        formset = InitiationFormSet(request.POST, request.FILES, prefix="initiates")
        formset.initial = [
            {"user": user.pk, "roll": self.next_badge + num} for num, user in enumerate(self.to_initiate)
        ]
        depledge_formset = DepledgeFormSet(request.POST, request.FILES, prefix="depledges")
        depledge_formset.initial = [{"user": user.name} for user in self.to_depledge]
        if not formset.is_valid() or not depledge_formset.is_valid():
            return self.render_to_response(self.get_context_data(formset=formset, depledge_formset=depledge_formset))
        update_list = []
        depledge_list = []
        initiations = []
        for form in formset:
            # ``Initiation.user`` is a OneToOneField, so a concurrent double
            # submit of the initiation report (two requests processing the same
            # selection) makes the second INSERT violate
            # ``forms_initiation_user_id_key``. Skip the already-initiated member
            # instead of 500-ing the whole report (mirrors the depledge guard
            # below; same double-submit class as #782).
            form.instance.chapter = self.request.user.current_chapter
            member = form.instance.user
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"{member} was already initiated; skipped the duplicate initiation.",
                )
                continue
            update_list.append(member)
            initiations.append(form.instance)
        for form in depledge_formset:
            # ``Depledge.user`` is a OneToOneField. A rapid double submit (or
            # re-depledging a PNM who was re-added after a prior depledge) tries
            # to insert a second Depledge for the same member and raises
            # ``IntegrityError: forms_depledge_user_id_key`` (#782). Skip the
            # duplicate instead of 500-ing the whole initiation report.
            member = form.instance.user
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"{member} was already depledged; skipped the duplicate depledge.",
                )
                continue
            depledge_list.append(member)
        Task.mark_complete(name="Initiation Report", chapter=self.request.user.current_chapter)
        if update_list:
            messages.add_message(
                request,
                messages.INFO,
                "You successfully submitted initiation report for:\n" f"{update_list}",
            )
        if depledge_list:
            messages.add_message(
                request,
                messages.INFO,
                "You successfully submitted depledge report for:\n" f"{depledge_list}",
            )
            for depledge in depledge_list:
                DepledgeSurveyEmail(depledge).send()
                depledge.set_no_contact()
                Training.deactivate_user(depledge, request=request)

        from .flows import InitiationProcessFlow

        ceremony = request.POST.get("initiates-__prefix__-ceremony", "normal")
        if initiations:
            InitiationProcessFlow.start.run(initiations=initiations, ceremony=ceremony, request=request)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:init_selection")


class StatusChangeTypeMixin:
    """Shared per-reason setup for the split member status-change views.

    Reads the ``reason`` URL kwarg, resolves it against ``STATUS_CHANGE_TYPES``
    (404 on an unknown reason), and keeps candidate-chapter-only reasons off
    chartered chapters.
    """

    officer_edit = "member status"

    def setup(self, request, *args, **kwargs):
        # Resolve the reason in setup() — before the OfficerRequired group check
        # runs in dispatch — so ``get_success_url`` still works on a
        # permission-denied redirect for a non-officer.
        super().setup(request, *args, **kwargs)
        self.reason = kwargs.get("reason")
        self.type_info = STATUS_CHANGE_TYPES.get(self.reason)

    def dispatch(self, request, *args, **kwargs):
        if self.type_info is None:
            raise Http404("Unknown member status change type.")
        if request.user.is_authenticated and self.type_info["candidate_only"]:
            chapter = request.user.current_chapter
            if not (chapter and chapter.candidate_chapter):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"The {self.type_info['label']} form is only for candidate chapters.",
                )
                return redirect("forms:landing")
        return super().dispatch(request, *args, **kwargs)


class StatusChangeHistoryListView(
    LoginRequiredMixin, OfficerRequiredMixin, StatusChangeTypeMixin, PagedFilteredTableView
):
    """Chapter-scoped history of submitted status changes for one reason, with a
    button to submit a new one."""

    model = StatusChange
    context_object_name = "status_changes"
    template_name = "forms/statuschange_list.html"
    filter_user_chapter = True
    formhelper_class = StatusChangeListFormHelper

    @property
    def filter_class(self):
        return self.type_info["filter"]

    @property
    def table_class(self):
        return self.type_info["table"]

    def get_queryset(self, **kwargs):
        qs = super().get_queryset(**kwargs)
        return qs.filter(reason=self.reason).order_by("-created")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["type_label"] = self.type_info["label"]
        context["reason"] = self.reason
        context["is_multi"] = self.type_info["multi"]
        if self.type_info["multi"]:
            context["create_url"] = reverse("forms:status_graduate_select")
        else:
            context["create_url"] = reverse("forms:status_new", kwargs={"reason": self.reason})
        return context


class StatusChangeCreateView(LoginRequiredMixin, OfficerRequiredMixin, StatusChangeTypeMixin, CreateView):
    """Submit a single-member status change (co-op, military, withdraw, transfer,
    resign-from-candidate-chapter). Graduation uses its own multi-member flow."""

    model = StatusChange
    form_class = SingleStatusChangeForm
    template_name = "forms/statuschange_form.html"

    def dispatch(self, request, *args, **kwargs):
        info = STATUS_CHANGE_TYPES.get(self.kwargs.get("reason"))
        if info is not None and info["multi"]:
            # Graduation is multi-member; send the officer to its select step.
            return redirect("forms:status_graduate_select")
        return super().dispatch(request, *args, **kwargs)

    def get_actives(self):
        return self.request.user.current_chapter.actives().exclude(pk=self.request.user.pk).order_by("name")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        kwargs["reason"] = self.reason
        kwargs["actives"] = self.get_actives()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["helper"] = SingleStatusChangeFormHelper()
        context["type_label"] = self.type_info["label"]
        context["reason"] = self.reason
        context["history_url"] = reverse("forms:status_history", kwargs={"reason": self.reason})
        return context

    def form_valid(self, form):
        chapter = self.request.user.current_chapter
        form.instance.reason = self.reason
        if self.reason == "coop":
            # Preserve the prior rule: a COOP (away) status must not overlap a
            # member's current officer term.
            member = form.cleaned_data.get("user")
            officers = chapter.get_current_officers_council()[0]
            if member in officers:
                date_start = form.cleaned_data.get("date_start")
                date_end = form.cleaned_data.get("date_end")
                role_info = member.roles.filter(
                    role__in=member.current_roles + list(CHAPTER_OFFICER),
                ).values("role", "start", "end")
                for role in role_info:
                    latest_start = max(date_start, role["start"])
                    earliest_end = min(date_end, role["end"])
                    delta = (earliest_end - latest_start).days + 1
                    if max(0, delta) > 0:
                        role_message = f"{role['role'].title()}:  start: {role['start']} end: {role['end']}"
                        messages.add_message(
                            self.request,
                            messages.ERROR,
                            mark_safe(
                                f"{member} is a current officer. COOP status must not overlap "
                                f"with officer term.<br>{role_message}"
                            ),
                        )
                        return self.form_invalid(form)
        response = super().form_valid(form)
        Task.mark_complete(name="Member Updates", chapter=chapter)
        messages.add_message(
            self.request,
            messages.INFO,
            f"You successfully submitted the {self.type_info['label']} status change for {form.instance.user}.",
        )
        return response

    def get_success_url(self):
        return reverse("forms:status_history", kwargs={"reason": self.reason})


class GraduateSelectView(LoginRequiredMixin, OfficerRequiredMixin, FormView):
    """Step 1 of graduation: pick the graduating members."""

    form_class = GraduateSelectForm
    template_name = "forms/graduate_select.html"
    officer_edit = "member status"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actives"] = (
            self.request.user.current_chapter.actives().exclude(pk=self.request.user.pk).order_by("name")
        )
        return kwargs

    def form_valid(self, form):
        members = form.cleaned_data["members"]
        self.request.session["graduate-selection"] = [member.pk for member in members]
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("forms:status_graduate")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history_url"] = reverse("forms:status_history", kwargs={"reason": "graduate"})
        return context


class GraduateFillView(LoginRequiredMixin, OfficerRequiredMixin, TemplateView):
    """Step 2 of graduation: fill one graduation row per selected member."""

    template_name = "forms/graduate_fill.html"
    officer_edit = "member status"

    def selected_members(self):
        pks = self.request.session.get("graduate-selection", None)
        if not pks:
            return None
        return (
            self.request.user.current_chapter.actives()
            .exclude(pk=self.request.user.pk)
            .filter(pk__in=pks)
            .prefetch_related("major_final")
            .order_by("name")
        )

    def get(self, request, *args, **kwargs):
        if not self.selected_members():
            return redirect("forms:status_graduate_select")
        return super().get(request, *args, **kwargs)

    @staticmethod
    def formset_initial(members):
        return [
            {
                "user": member.name,
                "email_personal": member.email,
                "reason": "graduate",
                # Seeded from the pledge-form major, the officer can correct it.
                "major_final": [str(major) for major in member.major_final.all()],
            }
            for member in members
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        members = self.selected_members() or []
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = GraduateFormSet(prefix="graduates")
        formset.initial = self.formset_initial(members)
        context["formset"] = formset
        context["helper"] = GraduateFormHelper()
        context["combined_media"] = formset.media
        context["form_show_errors"] = True
        context["error_text_inline"] = True
        context["help_text_inline"] = True
        context["history_url"] = reverse("forms:status_history", kwargs={"reason": "graduate"})
        return context

    def post(self, request, *args, **kwargs):
        members = self.selected_members()
        if not members:
            return redirect("forms:status_graduate_select")
        formset = GraduateFormSet(request.POST, request.FILES, prefix="graduates")
        formset.initial = self.formset_initial(members)
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(formset=formset))
        chapter = request.user.current_chapter
        graduates_list = []
        for form in formset:
            form.save()
            graduates_list.append(form.instance.user)
        Task.mark_complete(name="Member Updates", chapter=chapter)
        slug = Config.get_value("GraduationSurvey")
        for user in graduates_list:
            if not slug:
                continue
            if "http" in slug:
                survey_link = slug
            else:
                user_pk = base64.b64encode(str(user.id).encode("utf-8")).decode("utf-8")
                survey_link = settings.CURRENT_URL + reverse(
                    "surveys:survey-detail-member",
                    kwargs={"slug": slug, "user_pk": user_pk},
                )
            SurveyEmail(
                user,
                "Graduation",
                survey_link,
                "An officer from your chapter has reported your upcoming graduation. "
                "Congratulations on your graduation! "
                "We would like to get your thoughts on your Theta Tau experience "
                "so that we can make the Fraternity better for everybody.",
            ).send()
        request.session.pop("graduate-selection", None)
        messages.add_message(
            request,
            messages.INFO,
            "You successfully submitted graduation for members:\n" f"{graduates_list}",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:status_history", kwargs={"reason": "graduate"})


def remove_extra_form(formset, **kwargs):
    tfc = formset.total_form_count()
    del formset.forms[tfc - 1]
    data = formset.data
    total_count_name = "%s-%s" % (formset.management_form.prefix, "TOTAL_FORMS")
    initial_count_name = "%s-%s" % (formset.management_form.prefix, "INITIAL_FORMS")
    formset.management_form.cleaned_data["TOTAL_FORMS"] -= 1
    formset.management_form.cleaned_data["INITIAL_FORMS"] -= 1
    data[total_count_name] = formset.management_form.cleaned_data["TOTAL_FORMS"] - 1
    data[initial_count_name] = formset.management_form.cleaned_data["INITIAL_FORMS"] - 1
    formset.data = data
    return formset


def _officer_status_overlap_errors(request, member, role, start, end):
    """Add an ERROR message for each away/alumni status overlapping a
    chapter-officer term; return True if any overlap was found.

    No-op for non-chapter-officer roles. Shared by the add and edit views so
    both enforce the same "status must not overlap an officer term" rule.
    """
    if role not in CHAPTER_OFFICER:
        return False
    error = False
    for status in member.status.filter(status__in=["away", "alumni"]).values("status", "start", "end"):
        latest_start = max(start, status["start"])
        earliest_end = min(end, status["end"])
        overlap = max(0, (earliest_end - latest_start).days + 1)
        if overlap > 0:
            error = True
            role_message = f"Status {status['status']} start: {status['start']} end: {status['end']}"
            messages.add_message(
                request,
                messages.ERROR,
                mark_safe(
                    f"For member {member}. {status['status'].capitalize()} status (eg. COOP or alumni status) must not overlap with officer term.<br>{role_message}"
                ),
            )
    return error


def _current_officer_emails(user):
    """Comma-joined, de-duplicated emails of the current chapter officers/roles
    for ``user``'s chapter (for the roster's "Copy emails" button).

    Only officers who share their email with ``user`` are listed; chapter
    officers, National Officers and Admins always see everyone.
    """
    emails = []
    seen = set()
    for role_change in UserRoleChange.get_current_roles(user).select_related("user"):
        officer = role_change.user
        if not officer.contact_visible_to(user, officer.email_visibility):
            continue
        email = officer.email or officer.email_school
        if email and email.lower() not in seen:
            seen.add(email.lower())
            emails.append(email)
    return ", ".join(emails)


def _term_is_in_past(start, end):
    """True when both a role's start and end dates are before today — a purely
    historical backfill rather than a new appointment."""
    today = datetime.date.today()
    return start < today and end < today


class DefaultCurrentPeriodMixin:
    """Default the officer roster to *current* on an unfiltered initial load,
    while letting the filter's "Clear" button (which submits ``cancel``) reset
    to showing all.

    The filter no longer defaults ``period`` itself (its empty choice means
    "all"), so this injects ``period=current`` only when the request carries no
    ``period`` and is not a "Clear".
    """

    def get_queryset(self, **kwargs):
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if not cancel and "period" not in request_get:
            request_get["period"] = "current"
        return super().get_queryset(request_get=request_get, **kwargs)


class RoleChangeListView(DefaultCurrentPeriodMixin, LoginRequiredMixin, PagedFilteredTableView):
    """Chapter officer / role roster.

    Replaces the old "+1 extra row then submit" election formset with a table of
    current and past officers plus an "Add Officer" button (mirroring the
    External Organizations table). Any member may view it; it defaults to the
    *current* officers and is filterable by member, role, and start/end date
    buckets. Officers see the add button; each row's Edit control is gated by
    ``UserRoleChange.can_be_edited_by``.
    """

    model = UserRoleChange
    queryset = UserRoleChange.objects.filter(role__in=CHAPTER_ROLES).select_related("user", "user__chapter")
    template_name = "forms/officer_list.html"
    table_class = OfficerRoleTable
    filter_class = RoleChangeListFilter
    formhelper_class = RoleChangeListFormHelper
    filter_user_chapter = True
    ordering = ["user__last_name", "-start"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["email_list"] = _current_officer_emails(self.request.user)
        return context


class RoleChangeCreateView(LoginRequiredMixin, OfficerRequiredMixin, CreateView):
    """Add a single chapter officer / role (officers only).

    Preserves every safeguard and side effect of the old election formset: the
    self-assignment block and Treasurer January-term policy (in the form), the
    away/alumni term-overlap block, the deadlock-safe write, the best-effort
    Vector LMS sync for educator / risk-management roles, the Treasurer
    policy-exception notification, ``Task`` completion, and the ``NewOfficers``
    email. Those new-officer side effects are skipped when the recorded term is
    entirely in the past (a historical backfill).
    """

    officer_edit = "member roles"
    template_name = "forms/officer_form.html"
    model = UserRoleChange
    form_class = OfficerAddForm

    def get_success_url(self):
        return reverse("forms:officer")

    def get_form_kwargs(self):
        # Used by ``OfficerAddForm`` to reject the requesting officer as their
        # own role recipient.
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        member = form.instance.user
        role = form.instance.role
        # Away/alumni status (e.g. COOP or alumni) must not overlap a
        # chapter-officer term. Message per overlapping status, then re-render
        # without saving.
        if _officer_status_overlap_errors(self.request, member, role, form.instance.start, form.instance.end):
            return self.form_invalid(form)

        # Deadlock-safe write: lock the affected member row before saving so
        # concurrent officer updates can never grab member rows in opposite
        # order (issues #825/#858/#859/#982). Side effects below run AFTER the
        # retried write so a retry can never duplicate them.
        def _persist():
            list(User.objects.select_for_update().filter(pk=member.pk))
            form.save()

        retry_on_deadlock(_persist, description="officer role add")

        # A role recorded entirely in the past (both dates before today) is a
        # historical backfill, not a new appointment, so skip the new-officer
        # side effects (Vector LMS sync, Treasurer-policy email, task
        # completion, and the New Officers email).
        if not _term_is_in_past(form.instance.start, form.instance.end):
            role_name = role
            if role_name in [
                "pledge/new member educator",
                "risk management chair",
            ]:
                # Syncing to the external Vector LMS is a best-effort side
                # effect; the officer role change above is already saved. A
                # training-system outage must never turn this into a 500 (see
                # issue #1086), so surface a retry message instead.
                try:
                    Training.add_user(
                        member,
                        extra_group=role_name,
                        request=self.request,
                    )
                except Exception:
                    logger.exception(
                        "Training sync failed during officer add for %s",
                        member,
                    )
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        "The officer role was saved, but the training system "
                        f"could not be updated for {member}. "
                        "Please try again later.",
                    )
            if role_name in COL_OFFICER_ALIGN:
                role_name = COL_OFFICER_ALIGN[role_name]

            # Treasurer terms must run January-to-January per policy. When an
            # officer acknowledged the exception and supplied a reason, notify
            # the Grand Treasurer, regional directors and Central Office.
            exception_reason = (form.cleaned_data.get("treasurer_term_exception_reason") or "").strip()
            if exception_reason and treasurer_term_violation(
                form.instance.role,
                form.instance.start,
                form.instance.end,
            ):
                TreasurerTermException(
                    role_change=form.instance,
                    reason=exception_reason,
                    submitted_by=self.request.user,
                ).send()

            Task.mark_complete(
                name="Officer Election Report",
                chapter=self.request.user.current_chapter,
            )
            if role_name in CHAPTER_OFFICER:
                NewOfficers(new_officers=[member]).send()
        messages.success(self.request, f"{member} was added as {form.instance.role.title()}.")
        return HttpResponseRedirect(self.get_success_url())


class RoleChangeEditView(LoginRequiredMixin, UpdateView):
    """Edit a single officer / role term's start and end dates.

    Replaces the old "Remove" action: a role is never deleted, only its dates
    are adjusted (validated so the term stays meaningful and cannot be
    "effectively deleted"). Serves BOTH the chapter and national tables —
    permission and the return page are derived from the role itself via
    ``UserRoleChange.can_be_edited_by`` (member-self for non-chapter-officer
    roles; otherwise an officer serving the chapter, or a superuser for
    national roles).
    """

    model = UserRoleChange
    form_class = OfficerRoleEditForm
    template_name = "forms/officer_edit_form.html"

    def _list_url(self):
        if getattr(self, "role_change", None) and self.role_change.role in NAT_OFFICERS:
            return reverse("forms:natoff")
        return reverse("forms:officer")

    def setup(self, request, *args, **kwargs):
        # Set the target row in setup() (before any dispatch/permission mixin)
        # so ``get_success_url``/``_list_url`` can safely read it.
        super().setup(request, *args, **kwargs)
        self.role_change = get_object_or_404(UserRoleChange, pk=kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.role_change.can_be_edited_by(request.user):
            messages.error(
                request,
                "You cannot edit this role. Either it is no longer current or "
                "you do not have permission to change it.",
            )
            return HttpResponseRedirect(self._list_url())
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.role_change

    def get_success_url(self):
        return self._list_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_change"] = self.role_change
        context["back_url"] = self._list_url()
        return context

    def form_valid(self, form):
        member = self.role_change.user
        role = self.role_change.role
        # Same away/alumni status-overlap block as the add view.
        if _officer_status_overlap_errors(self.request, member, role, form.instance.start, form.instance.end):
            return self.form_invalid(form)

        # Deadlock-safe write — same rationale as the add views
        # (issues #825/#858/#859/#982).
        def _persist():
            list(User.objects.select_for_update().filter(pk=member.pk))
            form.save()

        retry_on_deadlock(_persist, description="officer role edit")

        # Treasurer terms must run January-to-January; when an officer
        # acknowledged the exception and supplied a reason, notify leadership
        # (parity with the add view).
        exception_reason = (form.cleaned_data.get("treasurer_term_exception_reason") or "").strip()
        if exception_reason and treasurer_term_violation(role, form.instance.start, form.instance.end):
            TreasurerTermException(
                role_change=form.instance,
                reason=exception_reason,
                submitted_by=self.request.user,
            ).send()
        messages.success(
            self.request,
            f"Updated {member}'s {role.title()} term dates.",
        )
        return HttpResponseRedirect(self.get_success_url())


class RoleChangeNationalListView(DefaultCurrentPeriodMixin, LoginRequiredMixin, PagedFilteredTableView):
    """National officer roster — the single national-officer page.

    Consolidates the old assignment table and the separate contacts roster into
    one page: any logged-in member can view the current (and, via the filter,
    past) national officers and copy their emails; national officers also get
    the contact-sync button; and superusers get the "Add" control. Defaults to
    the *current* national officers, filterable by member, role, and start/end
    date buckets.
    """

    model = UserRoleChange
    queryset = UserRoleChange.objects.filter(role__in=NAT_OFFICERS).select_related("user", "user__chapter")
    template_name = "forms/officer_national_list.html"
    table_class = NationalOfficerRoleTable
    filter_class = RoleChangeNationalListFilter
    formhelper_class = RoleChangeNationalListFormHelper
    ordering = ["user__last_name", "-start"]

    def get_context_data(self, **kwargs):
        from thetatauCMT.contact_sync.context import build_sync_modal_context
        from thetatauCMT.contact_sync.officers import NATIONAL_SCOPE, collect_national_officer_contacts

        context = super().get_context_data(**kwargs)
        # Bulk "copy emails" of the current national officers (mirrors the old
        # contacts page); the roster table itself is driven by the filter above.
        # Each officer's own contact-visibility choice decides whether the
        # viewer gets their address.
        officers, _ = collect_national_officer_contacts()
        viewer = self.request.user
        officer_users = User.objects.in_bulk([officer.user_pk for officer in officers])
        emails = []
        seen = set()
        for officer in officers:
            target = officer_users.get(officer.user_pk)
            if target is None or not target.contact_visible_to(viewer, target.email_visibility):
                continue
            for email in officer.emails:
                if email and email.lower() not in seen:
                    seen.add(email.lower())
                    emails.append(email)
        context["email_list"] = ", ".join(emails)
        # Only national officers get the contact-sync button/modal.
        if getattr(self.request, "is_nat_officer", False):
            context.update(build_sync_modal_context(self.request, NATIONAL_SCOPE))
        return context

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()
        kwargs["viewer"] = self.request.user
        return kwargs


class RoleChangeNationalCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Add a single national officer / role (superuser only).

    Preserves the self-assignment block (in the form), the deadlock-safe write,
    and the Vector LMS education-group sync of the old national election
    formset.
    """

    template_name = "forms/officer_national_form.html"
    model = UserRoleChange
    form_class = NationalOfficerAddForm

    def get_success_url(self):
        return reverse("forms:natoff")

    def get_form_kwargs(self):
        # Used by ``NationalOfficerAddForm`` to reject the requesting officer as
        # their own national officer role recipient.
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        member = form.instance.user

        # Deadlock-safe write — same rationale as the chapter view
        # (issues #825/#858/#859/#982). The Vector LMS sync runs afterwards so a
        # retry cannot duplicate it.
        def _persist():
            list(User.objects.select_for_update().filter(pk=member.pk))
            form.save()

        retry_on_deadlock(_persist, description="national officer role add")
        # Skip the Vector LMS enrollment for a purely historical (past) term.
        if not _term_is_in_past(form.instance.start, form.instance.end):
            Training.add_user_ed(member, self.request)
        messages.success(self.request, f"{member} was added as {form.instance.role.title()}.")
        return HttpResponseRedirect(self.get_success_url())


class HSEducationListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = HSEducation
    context_object_name = "chapter_education_list"
    table_class = HSEducationListTable
    filter_class = EducationListFilter
    formhelper_class = HSEducationListFormHelper

    def get_queryset(self, **kwargs):
        qs = HSEducation.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("program_date", [""])
        if not cancel:
            if request_get.get("program_date", "") == "":
                request_get["program_date"] = current_year_term_slug()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_chapters, dates = active_chapters_filter(self.filter)
        alcohol_drugs = self.object_list.filter(category="alcohol_drugs")
        harassment = self.object_list.filter(category="harassment")
        mental = self.object_list.filter(category="mental")
        data = [
            {
                "chapter__name": chapter.name,
                "region": chapter.region.name,
                "alcohol_drugs": [
                    (program.get_approval_display(), program.report)
                    for program in alcohol_drugs.filter(chapter=chapter)
                ],
                "harassment": [
                    (program.get_approval_display(), program.report) for program in harassment.filter(chapter=chapter)
                ],
                "mental": [
                    (program.get_approval_display(), program.report) for program in mental.filter(chapter=chapter)
                ],
            }
            for chapter in active_chapters
        ]
        table = HSEducationListTable(data=data)
        RequestConfig(self.request, paginate={"per_page": 300}).configure(table)
        context["table"] = table
        return context


class HSEducationCreateView(LoginRequiredMixin, CreateProcessView):
    template_name = "forms/chapter_report.html"
    form_class = HSEducationForm
    model = HSEducation

    def get_success_url(self, form_name=None):
        return reverse("viewflow:forms:hseducation:start")

    def activation_done(self, *args, **kwargs):
        self.activation.done()
        EmailProcessUpdate(
            self.activation,
            complete_step="H&S Education Program Submitted",
            next_step="Central Office Review",
            state="Pending Central Office Review",
            message=(
                "Your chapter has submitted a H&S Education Program." " Once the Central Office reviewed the program, "
            ),
            fields=[
                "program_date",
                "category",
                "first_name",
                "last_name",
                "email",
                "phone_number",
            ],
            attachments=["report"],
            email_officers=True,
            extra_emails={
                self.request.user.current_chapter.region.email,
                "central.office@thetatau.org",
            },
            direct_user=self.request.user,
        ).send()
        self.success("You successfully submitted the H&S Education Program")

    def form_valid(self, form):
        report = form
        chapter = self.request.user.current_chapter
        user = self.request.user
        report.instance.user = user
        report.instance.chapter = chapter
        return super().form_valid(form)

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        previous_programs = HSEducation.submitted_this_year(
            self.request.user.current_chapter,
        )
        complete_categories = [
            program.category for program in previous_programs if program.approval not in ["denied", "revisions"]
        ]
        incomplete_categories = [
            category.value[1] for category in HSEducation.CATEGORIES if category.value[0] not in complete_categories
        ]
        table = HSEducationTable(data=previous_programs)
        context["table"] = table
        context["incomplete_categories"] = ", ".join(incomplete_categories)
        return context


class RiskManagementFormView(LoginRequiredMixin, FormView):
    form_class = RiskManagementForm
    template_name = "forms/rmp.html"

    def get(self, request, *args, **kwargs):
        if RiskManagement.user_signed_this_semester(self.request.user):
            messages.add_message(
                self.request,
                messages.INFO,
                "RMP Previously signed this year, see previous submissions.",
            )
            return redirect(reverse("users:detail") + "#submissions")
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # Guard against a duplicate submission (e.g. a double-click or a browser
        # retry). The archived RMP copy is written to cloud storage under a
        # deterministic per-user object name, so Google Cloud Storage rejects a
        # second write to the same object within a second with HTTP 429
        # ("rate limit for object mutation operations", issue #957). The
        # signature for this term is already on file, so treat the repeat as a
        # no-op and send the user to their existing submissions.
        if RiskManagement.user_signed_this_semester(self.request.user):
            messages.add_message(
                self.request,
                messages.INFO,
                "RMP Previously signed this year, see previous submissions.",
            )
            return redirect(reverse("users:detail") + "#submissions")
        current_role = self.request.user.current_roles
        if not current_role:
            # We will use the status as the role
            current_role = self.request.user.current_status.replace(" ", "_")
        else:
            current_role = ", ".join([role.replace(" ", "_") for role in current_role])
        form.instance.user = self.request.user
        form.instance.role = current_role[:250]
        form.save()
        view = RiskManagementDetailView.as_view()
        new_request = self.request
        new_request.path = f"/forms/rmp-complete/{form.instance.id}"
        new_request.method = "GET"
        risk_file = view(new_request, pk=form.instance.id)
        file_name = f"Risk Management Form {self.request.user}"
        score_type = ScoreType.objects.filter(slug="rmp").first()
        submit_obj = Submission(
            user=self.request.user,
            name=file_name,
            type=score_type,
            chapter=self.request.user.current_chapter,
        )
        try:
            retry_google_api(
                lambda: submit_obj.file.save(f"{file_name}.pdf", ContentFile(risk_file.content)),
                description=f"RMP submission upload for {self.request.user}",
            )
        except Exception:
            # The signature itself is already saved above; only the archived PDF
            # copy in cloud storage failed. A storage hiccup must never become a
            # 500 for the signer (issue #957) — keep the signature, skip the
            # attachment, and tell them the copy could not be stored.
            logger.exception(
                "RMP submission upload failed for %s",
                self.request.user,
            )
            submit_obj = None
            messages.add_message(
                self.request,
                messages.WARNING,
                "Your RMP signature was saved, but the archived PDF copy could "
                "not be stored right now. This does not affect your signature.",
            )
        if submit_obj is not None:
            submit_obj.save()
            form.instance.submission = submit_obj
        obj = form.save()
        Task.mark_complete(
            name="Risk Management Form",
            chapter=self.request.user.current_chapter,
            current_roles=self.request.user.current_roles,
            user=self.request.user,
            obj=obj,
        )
        EmailRMPSigned(self.request.user, risk_file.content, file_name).send()
        messages.add_message(
            self.request,
            messages.INFO,
            "You successfully signed the RMP and Agreements of Theta Tau!\n",
        )
        return super().form_valid(form)

    def get_success_url(self):
        # We want this as home because everyone fills this one out
        return reverse("home")


class RiskManagementDetailView(LoginRequiredMixin, PDFTemplateResponseMixin, UpdateView):
    model = RiskManagement
    form_class = RiskManagementForm
    template_name = "forms/rmp_pdf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_officer"] = getattr(self.request, "is_officer", False)
        return context


class BillOfRightsDetailView(DetailView):
    model = Chapter
    template_name = "forms/billofrights.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object = self.object.region
        context["object"] = self.object
        context["regionaldirectors"] = self.object.directors.all()
        return context


class BillOfRightsPDFView(PDFTemplateResponseMixin, BillOfRightsDetailView):
    template_name = "forms/billofrights_pdf.html"


class RollBookPDFView(LoginRequiredMixin, OfficerRequiredMixin, WeasyTemplateResponseMixin, DetailView):
    model = User
    template_name = "forms/rollbook_pdf.html"
    candidate_template_name = "forms/rollbook_candidate_pdf.html"

    def get_template_names(self):
        # Candidate chapters roll their members on a different form than
        # chartered chapters — pick the template from the member's chapter.
        chapter = getattr(self.object, "chapter", None)
        if chapter is not None and chapter.candidate_chapter:
            return [self.candidate_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        init_date = self.request.session.get("init_date", datetime.datetime.today().date())
        if isinstance(init_date, str):
            try:
                init_date = datetime.datetime.strptime(init_date, "%m/%d/%Y")
            except ValueError:
                # A blank or malformed session value (e.g. the officer submitted
                # the initiation-date form empty) must not 500 the roll book
                # download (issues #984/#985); fall back to today.
                init_date = datetime.datetime.today().date()
        with open(r"secrets/short_oath.txt", "r") as file:
            context["short_oath"] = file.read()
        context["init_date"] = init_date
        context["pledge_form"] = self.object.pledge_form.last()
        return context


class RollBookPDFDownload(RollBookPDFView):
    def get_pdf_filename(self):
        return f"RollBookPage_{self.object.chapter.slug}_{self.object.id}.pdf"


def active_chapters_filter(filter_obj):
    chapters_list = Chapter.objects.exclude(active=False)
    region = None
    region_slug = None
    dates = semester_encompass_start_end_date(TODAY_END)
    if filter_obj.is_bound and filter_obj.is_valid():
        year = filter_obj.form.cleaned_data.get("year", current_year())
        term = filter_obj.form.cleaned_data.get("term", current_term())
        dates = semester_encompass_start_end_date(term=term, year=year)
        region_slug = filter_obj.form.cleaned_data.get("region", "national")
        region = Region.objects.filter(slug=region_slug).first()
    active_chapters = Chapter.objects.exclude(active=False)
    if region_slug == "national":
        chapters_list = active_chapters
    elif region:
        chapters_list = active_chapters.filter(region__in=[region])
    elif region_slug == "candidate_chapter":
        chapters_list = active_chapters.filter(candidate_chapter=True)
    return chapters_list, dates


class RiskManagementListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = User
    context_object_name = "risk"
    template_name = "forms/rmp_list.html"
    table_class = RiskFormTable
    filter_class = RiskListFilter
    formhelper_class = RiskListFormHelper

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            context = self.get_context_data()
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauRMPstatus_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            for row in context["table"].as_values():
                writer.writerow(row)
        return response

    def get_queryset(self, **kwargs):
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            request_get = None
        self.filter = self.filter_class(request_get)
        self.filter.form.helper = self.formhelper_class()
        self.chapters_list, dates = active_chapters_filter(self.filter)
        start, end = dates
        qs = User.objects.filter(
            status__status__in=["active", "activepend", "activeCC"],
            status__start__lte=end,
            status__end__gte=start,
        ).filter(chapter__in=self.chapters_list)
        qs = (
            qs.annotate(
                rmp_complete=Exists(
                    RiskManagement.objects.filter(user=OuterRef("pk"), date__gte=start, date__lte=end),
                )
            )
            .values("chapter", "rmp_complete")
            .annotate(count=Count("rmp_complete"))
        ).order_by("chapter")
        return qs

    def get_table_data(self):
        all_forms = self.get_queryset()
        risk_data = all_forms.values("chapter__name", "chapter__region__name", "rmp_complete", "count")
        data = {}
        count_types = {
            True: "complete",
            False: "incomplete",
        }
        for risk in risk_data:
            count_type = count_types[risk["rmp_complete"]]
            if risk["chapter__name"] not in data:
                data[risk["chapter__name"]] = {
                    "chapter": risk["chapter__name"],
                    "region": risk["chapter__region__name"],
                    "complete": 0,
                    "incomplete": 0,
                }
            data[risk["chapter__name"]][count_type] = risk["count"]
        return data.values()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        risk_table = context["table"]
        RequestConfig(self.request, paginate={"per_page": 100}).configure(risk_table)
        context["table"] = risk_table
        return context


class PledgeProgramListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = PledgeProgram
    context_object_name = "pledge_program"
    table_class = PledgeProgramTable
    filter_class = PledgeProgramListFilter
    formhelper_class = PledgeProgramFormHelper

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"PledgeProgram_ThetaTauOfficerExport_{time_name}.csv"
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
                    "All forms are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_queryset(self, **kwargs):
        qs = PledgeProgram.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [""])
            request_get.setlist("term", [""])
        if not cancel:
            if request_get.get("year", "") == "":
                request_get["year"] = datetime.datetime.now().year
            if request_get.get("term", "") == "":
                request_get["term"] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list.prefetch_related("chapter", "process")
        all_forms = all_forms.values(
            "year",
            "term",
            "manual",
            "date_start",
            "date_complete",
            "date_initiation",
            "dues",
            "weeks",
            "weeks_left",
            "term",
            "manual",
            pk=F("process__pk"),
            live_link=F("chapter__nme_file_id"),
            chapter_name=F("chapter__name"),
            region=F("chapter__region__name"),
            school=F("chapter__school"),
            approval=StringAgg("process__approval", ", ", default=""),
        )
        complete = self.filter.form.cleaned_data["complete"]
        if complete in ["0", ""]:
            form_chapters = all_forms.values_list("chapter__id", flat=True)
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(candidate_chapter=True)
            else:
                missing_chapters = active_chapters.exclude(id__in=form_chapters)
            missing_data = [
                {
                    "chapter_name": chapter.name,
                    "school": chapter.school,
                    "region": chapter.region.name,
                    "manual": None,
                    "term": None,
                    "year": None,
                    "date_start": None,
                    "date_complete": None,
                    "date_initiation": None,
                    "live_link": chapter.nme_file_id,
                    "dues": 0,
                    "weeks": 0,
                    "weeks_left": 0,
                    "approval": "not_submitted",
                    "pk": None,
                }
                for chapter in missing_chapters
            ]
            if complete == "0":  # Incomplete
                # These are old forms that did not have approval as an option
                all_forms_no_approval = all_forms.filter(approval__isnull=True)
                all_forms = all_forms.exclude(approval__contains="approved")
                all_forms = all_forms | all_forms_no_approval
                data = list(all_forms)
                data.extend(missing_data)
            else:  # All
                data = list(all_forms)
                data.extend(missing_data)
        else:
            all_forms = all_forms.filter(approval__contains="approved")
            data = list(all_forms)
        chapter_names = list(all_forms.values_list("chapter_name", flat=True))
        chapter_officer_emails = {
            chapter: [user.email for user in Chapter.objects.get(name=chapter).get_current_officers_council()[0]]
            for chapter in chapter_names
        }
        table = PledgeProgramTable(data=data)
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        context["email_list_table"] = chapter_officer_emails
        context["email_list"] = ", ".join(
            [email for chapter_emails in chapter_officer_emails.values() for email in chapter_emails]
        )
        return context


@group_required("natoff")
@require_POST
def pledge_program_request_revision(request, process_pk):
    """Email a chapter's executive board that their NME (New Member Education)
    program has review comments and must be revised and resubmitted.

    The viewflow/Google-sheets notification is unreliable, so this gives a
    national officer a one-click, on-demand reminder from the program list.
    """
    process = PledgeProgramProcess.objects.filter(pk=process_pk).select_related("chapter", "chapter__region").first()
    redirect_to = request.META.get("HTTP_REFERER") or reverse("forms:pledge_program_list")
    if process is None:
        messages.add_message(request, messages.ERROR, "Requested pledge program could not be found.")
        return HttpResponseRedirect(redirect_to)
    chapter = process.chapter
    recipients = chapter.council_emails()
    if not recipients:
        messages.add_message(
            request,
            messages.ERROR,
            f"No executive board emails on file for {chapter}; email could not be sent.",
        )
        return HttpResponseRedirect(redirect_to)
    if chapter.nme_file_id and chapter.nme_file_id != "none":
        program_link = (
            f"<a href='https://docs.google.com/document/d/{chapter.nme_file_id}/edit' "
            "target='_blank'>New Member Education Program</a>"
        )
    else:
        program_link = "your New Member Education program"
    message = (
        "Comments have been added to your NME program, please revise and resubmit.<br><br>" f"Program: {program_link}"
    )
    if process.approval_comments:
        message += f"<br><br>Reviewer comments:<br>{process.approval_comments}"
    GenericEmail(
        emails=recipients,
        cc={"central.office@thetatau.org", chapter.region.email},
        addressee=f"{chapter.full_name} Officers",
        subject=f"[CMT] NME Program Revisions Requested for {chapter}",
        message=mark_safe(message),
    ).send()
    messages.add_message(
        request,
        messages.INFO,
        f"Revision request emailed to the {chapter} executive board.",
    )
    return HttpResponseRedirect(redirect_to)


class AuditFormView(LoginRequiredMixin, OfficerRequiredMixin, UpdateView):
    form_class = AuditForm
    template_name = "forms/audit.html"
    model = Audit
    officer_edit = "audits"
    officer_edit_type = "submit"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complete = False
        if context.get("object") is not None:
            form = context["form"]
            for field_name, field in form.fields.items():
                field.disabled = True
            complete = True
        context["complete"] = complete
        return context

    def get_object(self, queryset=None):
        # Viewing an existing audit by pk: read-only access is scoped to the
        # audit's chapter (plus national officers / superusers). This path does
        # NOT require the viewer to currently hold an executive-officer role —
        # otherwise a former officer or a chapter member navigating to a
        # completed audit is bounced to a blank submission form.
        if "pk" in self.kwargs:
            try:
                audit = Audit.objects.get(pk=self.kwargs["pk"])
            except Audit.DoesNotExist:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "Requested audit could not be found.",
                )
                return None
            audit_chapter = audit.user.chapter
            user = self.request.user
            if audit_chapter == user.current_chapter or user.is_national_officer_group or user.is_admin:
                return audit
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Requested audit is for {audit_chapter} Chapter not your chapter.",
            )
            return None

        # No pk: submission flow. Only executive officers can submit.
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can submit an audit: {*CHAPTER_OFFICER,}\n"
                f"Your current roles are: {*current_roles,}",
            )
            return None
        task = Task.objects.filter(name="Audit", owner__in=current_roles).first()
        chapter = self.request.user.current_chapter
        next_date = None
        if task is not None:
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            messages.add_message(self.request, messages.INFO, "You must submit an updated audit.")
            return None
        return self.request.user.audit_form.last()

    def form_valid(self, form):
        form.instance.year = datetime.datetime.now().year
        form.instance.user = self.request.user
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can submit an audit: {*CHAPTER_OFFICER,}\n"
                f"Your current roles are: {*current_roles,}",
            )
            return super().form_invalid(form)
        else:
            saved_audit = form.save()
            Task.mark_complete(
                name="Audit",
                chapter=self.request.user.current_chapter,
                current_roles=current_roles,
                user=self.request.user,
                obj=saved_audit,
            )
            messages.add_message(
                self.request,
                messages.INFO,
                "You successfully submitted the Audit Form!\n" f"Your current roles are: {*current_roles,}",
            )
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.is_authenticated:
            return reverse("chapters:audit", kwargs={"slug": self.request.user.chapter.slug})
        else:
            return reverse("home")


class AuditListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = Audit
    context_object_name = "audit"
    table_class = AuditTable
    filter_class = AuditListFilter
    formhelper_class = AuditListFormHelper

    def get_queryset(self, **kwargs):
        qs = Audit.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs


def load_majors(request):
    chapter_id = request.GET.get("chapter")
    other = request.GET.get("other")
    majors = []
    if chapter_id:
        majors = list(ChapterCurricula.objects.filter(chapter__pk=chapter_id, approved=True).order_by("major"))
        if other:
            other = ChapterCurricula(pk=-1, major="Other")
            majors.append(other)
    return render(request, "forms/majors_dropdown_list_options.html", {"majors": majors})


class PledgeFormView(CreateView):
    template_name = "forms/pledge_form.html"
    initial = {"demographics": {"gender": "", "sexual": "", "racial": "", "ability": ""}}

    def get_form(self):
        alt_form = self.kwargs.get("alt_form", False)
        return PledgeFormFull(**self.get_form_kwargs(), alt_form=alt_form)

    def form_invalid(self, form):
        messages.add_message(
            self.request,
            messages.ERROR,
            "Error with pledge form, please expand sections and correct error(s).",
        )
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        pledge = form["pledge"]
        user = form["user"]
        demographics = form["demographics"]
        user.instance.badge_number = User.next_pledge_number()
        user.instance.chapter = user.cleaned_data["school_name"]
        try:
            with transaction.atomic():
                user = user.save()
        except IntegrityError:
            user = User.objects.filter(email=user.instance.email).first()
            messages.add_message(
                self.request,
                messages.ERROR,
                mark_safe(
                    f"Pledge form already submitted for {user}!<br>"
                    "If you previously pledged Theta Tau, "
                    "please have a chapter officer contact<br> "
                    "central.office@thetatau.org to restart your pledge process."
                ),
            )
            return HttpResponseRedirect(self.get_success_url())
        demographics.instance.user = user
        demographics.save()
        pledge.instance.user = user
        self.object = pledge.save()
        user.set_current_status(status="pnm")
        user.seed_major_final()
        view = BillOfRightsPDFView.as_view()
        new_request = HttpRequest()
        new_request.method = "GET"
        bill_view = view(new_request, pk=self.object.user.chapter.id)
        bill_file = bill_view.content
        EmailPledgeConfirmation(self.object, bill_file).send()
        # EmailPledgeWelcome(self.object).send()
        EmailPledgeOfficer(self.object).send()
        try:
            EmailAddress.objects.add_email(self.request, user, user.email_school, True)
        except IntegrityError:
            pass
        try:
            EmailAddress.objects.add_email(self.request, user, user.email, True)
        except IntegrityError:
            pass
        processes = PledgeProcess.objects.filter(chapter=user.chapter, finished__isnull=True)
        active_process = None
        for process in processes:
            active_task = process.active_tasks().first()
            if active_task.flow_task.name == "invoice_chapter":
                active_process = process
                break
        if active_process is None:
            from .flows import PledgeProcessFlow

            activation = PledgeProcessFlow.start.run(chapter=user.chapter, request=self.request)
            active_process = activation.process
        active_process.pledges.add(self.object)
        try:
            Training.add_user(user, request=self.request)
        except Exception as e:
            logger.exception("Error adding training for %s %s", user, user.chapter)
            message = f"Error adding training {user=} {user.chapter=} {e}"
            CentralOfficeGenericEmail(message, subject="[CMT] Training Error").send()
        try:
            # Also enroll the new member in the Open edX (ed.thetatau.org)
            # training. Their account is created on first SSO login, so this
            # records a pending enrollment that activates when they log in.
            Training.add_user_ed(user, request=self.request)
        except Exception as e:
            logger.exception("Error adding Open edX training for %s %s", user, user.chapter)
            message = f"Error adding Open edX training {user=} {user.chapter=} {e}"
            CentralOfficeGenericEmail(message, subject="[CMT] Training Error").send()
        messages.add_message(
            self.request,
            messages.INFO,
            "You successfully submitted the Prospective New Member / Pledge Form! "
            "A confirmation email was sent to your school and personal email.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:pledgeform")


class PrematureAlumnusCreateView(LoginRequiredMixin, CreateProcessView):
    template_name = "forms/prematurealumnus_form.html"
    model = PrematureAlumnus
    form_class = PrematureAlumnusForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        # Return the submitting member/officer to the Premature Alumnus form,
        # which shows their submission in the status table. The viewflow default
        # would redirect to the process ``:detail`` page, which requires the
        # ``forms.view_prematurealumnus`` permission (national officers/staff
        # only) and 403s the member who just submitted.
        return reverse("viewflow:forms:prematurealumnus:start")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Premature Alumnus form submitted successfully to Executive Director for review")
        Task.mark_complete(
            name="Premature Alumnus",
            chapter=self.request.user.current_chapter,
            user=self.request.user,
            obj=self.object,
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        processes = PrematureAlumnus.objects.filter(user__chapter=self.request.user.current_chapter)
        for process in processes:
            status = "N/A"
            if process.finished is None:
                active_task = process.active_tasks().first()
                if active_task:
                    status = active_task.flow_task.task_title
                approved = "Pending"
            else:
                status = "Complete"
                approved = process.approved_exec
            data.append(
                {
                    "status": status,
                    "user": process.user,
                    "created": process.created,
                    "approved": approved,
                }
            )
        context["table"] = PrematureAlumnusStatusTable(data=data)
        context["prealumn_charge"] = Config.get_value("prealumn_charge")
        return context


@group_required("natoff")
@csrf_exempt
def badge_shingle_init_csv(request, csv_type, process_pk, response_type="csv"):
    process = get_object_or_404(InitiationProcess, pk=process_pk)
    content_type = "application/json" if response_type == "json" else "text/csv"
    response = HttpResponse(content_type=content_type)
    if csv_type in ["badge", "shingle"]:
        process.generate_badge_shingle_order(response, csv_type, file_type=response_type)
    elif csv_type == "invoice":
        process.generate_blackbaud_update(invoice=True, response=response)
    else:
        process.generate_blackbaud_update(response=response)
    response["Cache-Control"] = "no-cache"
    return response


@group_required("natoff")
@csrf_exempt
def badge_shingle_post(request, process_pk):
    process = get_object_or_404(InitiationProcess, pk=process_pk)
    process.post_shingle_to_webhook(request)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@group_required("natoff")
@csrf_exempt
def badge_shingle_init_sync(request, process_pk, invoice_number):
    process = get_object_or_404(InitiationProcess, pk=process_pk)
    new_invoice_number = process.sync_badge_shingle_invoice(request, invoice_number)
    return JsonResponse({"invoice_number": new_invoice_number})


def get_sign_status_discipline(user, name=False, complete=True):
    data = []
    processes = DisciplinaryProcess.objects.filter(chapter=user.current_chapter)
    for process in processes:
        link = False
        owner = "N/A"
        if process.finished is None:
            task = process.active_tasks().first()
            if task is None:
                # tasks may have all been cancelled and the process was not completed
                if not complete:
                    continue
                task = process.task_set.first()
                if task is None:
                    # A process with no tasks at all (e.g. a start view errored
                    # after creating the process) has nothing to display (#901).
                    continue
                status = task.status
                approved = False
            else:
                flow_task = task.flow_task
                # ``task.flow_task`` is None when the DB task references a node
                # that no longer exists in the current flow definition (#902);
                # fall back to the raw task status instead of crashing.
                status = flow_task.task_title if flow_task else task.status
                owner = task.owner
                approved = "Pending"
                if status and "Submit Form 2" in status and task.owner == user:
                    link = reverse(
                        "viewflow:forms:disciplinaryprocess:submit_form2",
                        kwargs={"process_pk": process.pk, "task_pk": task.pk},
                    )
        elif complete:
            task = process.task_set.first()
            flow_task = task.flow_task if task else None
            status = flow_task.task_title if flow_task else "Complete"
            approved = process.ec_approval
        else:
            continue
        if name:
            obj = {
                "process_name": "Disciplinary Process",
                "member": process.user,
                "owner": owner,
                "role": "Confirmation",
                "status": status,
                "approved": approved,
                "link": link,
            }
        else:
            obj = {
                "status": status,
                "user": process.user,
                "created": process.created,
                "trial_date": process.trial_date,
                "approved": approved,
                "link": link,
            }
        data.append(obj)
    return data


def get_sign_status(user, type_sign="creds", initial=False, name=False, complete=True):
    data = []
    extra_filter = {}
    member_field_names = ["user"]
    if type_sign == "creds":
        model = Convention
        url = "viewflow:forms:convention:assign_"
        signatures = {
            "delegate": "del",
            "alternate": "alt",
            "officer1": "o1",
            "officer2": "o2",
        }
        member_field_names = ["delegate", "alternate"]
        extra_filter = {"year": model.current_year()}
    elif type_sign == "resign":
        model = ResignationProcess
        url = "viewflow:forms:resignation:assign_"
        signatures = {"officer1": "o1", "officer2": "o2"}
    else:
        model = OSM
        url = "viewflow:forms:osm:assign_"
        signatures = {"officer1": "o1", "officer2": "o2"}
        extra_filter = {"year": model.current_year()}
        member_field_names = ["nominate"]
    processes = model.objects.filter(chapter=user.current_chapter, **extra_filter)
    submitted = False
    users = []
    for process in processes:
        submitted = True
        task_ids = {}
        for task in process.task_set.all():
            if task.flow_task.task_title:
                title = task.flow_task.task_title.split(" ")[0].lower()
                task_ids[title] = (task.pk, task.status)
        for signature, abbr in signatures.items():
            task_pk = 0
            task_status = "ASSIGNED"
            if not initial:
                task_pk, task_status = task_ids[signature]
            signer = getattr(process, signature)
            member = ", ".join([str(getattr(process, member_field_name)) for member_field_name in member_field_names])
            users.append(signer)
            link = False
            approved = "N/A"
            status = "Complete"
            if task_status == "ASSIGNED":
                if type_sign == "creds":
                    status = "Needs Signature"
                else:
                    status = "Needs Verification"
                if user == signer:
                    link = reverse(
                        url + abbr,
                        kwargs={"process_pk": process.pk, "task_pk": task_pk},
                    )
            else:
                # If still assigned should be N/A only when complete grab approval
                approved = getattr(process, f"approved_{abbr}", "N/A")
            if user.current_chapter.candidate_chapter:
                if signature in ["delegate", "alternate"]:
                    signature = "representative"
            if status == "Complete" and not complete:
                continue
            obj = {
                "member": member,
                "owner": signer,
                "role": signature,
                "status": status,
                "approved": approved,
                "link": link,
            }
            if name:
                obj["process_name"] = process.flow_class.process_title
            data.append(obj)
    return data, submitted, users


class ConventionCreateView(LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin):
    template_name = "forms/convention_form.html"
    model = Convention
    form_class = ConventionForm
    submitted = False
    data = {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def _active_previous_processes(self, chapter):
        """Return non-cancelled Convention processes for this chapter/year."""
        return Convention.objects.filter(
            chapter=chapter,
            year=Convention.current_year(),
        ).exclude(status=STATUS.CANCELED)

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(self.request.user)
        # An officer may explicitly request the create form (?resubmit=1) to
        # supersede a previous submission — skip the auto-redirect to their
        # own signing link so they can access the form again.
        resubmit = request.GET.get("resubmit") == "1" and getattr(request.user, "is_officer", False)
        if self.submitted and self.request.user in self.signers and not resubmit:
            for sign in self.data:
                link = sign["link"]
                if self.request.user == sign["owner"] and link != "#" and not isinstance(link, bool):
                    return redirect(link)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        """Continue on task or redirect back to task list."""
        return reverse("conventionform")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Convention Credential form submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        del_alt = [form.instance.delegate, form.instance.alternate]
        officers = chapter.get_current_officers_council_specific()
        self.assign_officers_form(del_alt, form, officers)
        # Supersede any prior Convention submission for this chapter/year:
        # cancel the existing process (and any incomplete tasks) and notify
        # the previous delegate/alternate/officer1/officer2 signers.
        for previous in self._active_previous_processes(chapter):
            previous_signers = [
                previous.delegate,
                previous.alternate,
                previous.officer1,
                previous.officer2,
            ]
            recipients = {u.email for u in previous_signers if u and u.email}
            cancel_process(previous)
            if recipients:
                GenericEmail(
                    emails=recipients,
                    cc={"central.office@thetatau.org", chapter.region.email},
                    addressee=f"{chapter.full_name} Convention Credential Signers",
                    subject=f"[CMT] Convention Credential Form Superseded for {chapter}",
                    message=(
                        "This is a notification that the Convention Credential "
                        f"Form previously submitted for {chapter} has been "
                        "cancelled and replaced with a new submission by "
                        f"{self.request.user}. Any pending signature tasks on "
                        "the previous form have been cancelled and no further "
                        "action is required on that submission."
                    ),
                ).send()
            messages.add_message(
                self.request,
                messages.INFO,
                f"Previous Convention Credential Form for {chapter} has been "
                "cancelled and replaced. Previous signers have been notified.",
            )
        Task.mark_complete(
            name="Credentials",
            chapter=chapter,
            user=self.request.user,
            obj=form.instance,
        )
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submitted"] = self.submitted
        context["table"] = SignTable(data=self.data)
        # When resubmitting, expose the flag to the template so it can render
        # the form (with a warning) alongside the existing-submission status.
        context["resubmit"] = self.request.GET.get("resubmit") == "1" and getattr(
            self.request.user, "is_officer", False
        )
        return context


class ConventionSignView(LoginRequiredMixin, UpdateProcessView, MultiFormsView):
    template_name = "forms/convention_sign_form.html"
    form_classes = {
        "process": None,
        "user": UserForm,
    }
    grouped_forms = {"form": ["process", "user"]}
    fields_options = {
        "assign_del": [
            "understand_del",
            "signature_del",
        ],
        "assign_alt": [
            "understand_alt",
            "signature_alt",
        ],
        "assign_o1": [
            "signature_o1",
            "approved_o1",
        ],
        "assign_o2": [
            "signature_o2",
            "approved_o2",
        ],
    }

    def _get_success_url(self, form=None):
        """Continue on task or redirect back to task list."""
        return reverse("conventionform")

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "user":
            kwargs.update(
                {
                    "instance": self.request.user,
                }
            )
        return kwargs

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Convention Credential form signed successfully.")

    def user_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self._get_success_url())

    def process_form_valid(self, *args, **kwargs):
        super().form_valid(*args, **kwargs)
        return HttpResponseRedirect(self._get_success_url())

    def create_process_form(self, *args, **kwargs):
        task_name = self.activation.flow_task.name
        self.fields = self.fields_options[task_name]
        return model_forms.modelform_factory(self.model, fields=self.fields)(**self.get_form_kwargs())

    def get_forms(self, form_classes, form_names=None, bind_all=False):
        forms = super().get_forms(form_classes, form_names, bind_all)
        task_name = self.activation.flow_task.name
        if "del" not in task_name and "alt" not in task_name:
            if "user" in forms:
                del forms["user"]
            if "user" in self.form_classes:
                del self.form_classes["user"]
            if "user" in self.grouped_forms["form"]:
                self.grouped_forms["form"].remove("user")
        return forms

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        task_name = self.activation.flow_task.name
        delegate = False
        if "del" in task_name or "alt" in task_name:
            delegate = True
            if "user" in context["forms"]:
                context["forms"]["user"].fields["phone_number"].required = True
        data, submitted, users = get_sign_status(self.request.user)
        context["submitted"] = submitted
        context["table"] = SignTable(data=data)
        context["delegate"] = delegate
        return context


class ConventionListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = Convention
    context_object_name = "convention_list"
    table_class = ConventionListTable
    filter_class = CompleteListFilter
    formhelper_class = CompleteFormHelper

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauConvention_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            emails = context["email_list"]
            if emails != "":
                writer.writerow(
                    [
                        "Chapter",
                        "Region",
                        "School",
                        "Role",
                        "Name",
                        "Email",
                        "Phone Number",
                        "Address",
                    ]
                )
                for form in self.object_list:
                    for user_type in ["delegate", "alternate"]:
                        user = getattr(form, user_type)
                        writer.writerow(
                            [
                                form.chapter,
                                form.chapter.region,
                                form.chapter.school,
                                user_type,
                                user.name,
                                user.email,
                                user.phone_number,
                                user.address,
                            ]
                        )
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All officers are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_queryset(self, **kwargs):
        qs = Convention.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [""])
            request_get.setlist("term", [""])
        if not cancel:
            if request_get.get("year", "") == "":
                request_get["year"] = datetime.datetime.now().year
            if request_get.get("term", "") == "":
                request_get["term"] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        data = [
            {
                "chapter": form.chapter.name,
                "region": form.chapter.region.name,
                "year": form.year,
                "term": Convention.TERMS.get_value(form.term),
                "delegate": form.delegate,
                "alternate": form.alternate,
            }
            for form in all_forms
        ]
        complete = self.filter.form.cleaned_data["complete"]
        if complete in ["0", ""]:
            form_chapters = all_forms.values_list("chapter__id", flat=True)
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(candidate_chapter=True)
            else:
                missing_chapters = active_chapters.exclude(id__in=form_chapters)
            missing_data = [
                {
                    "chapter": chapter.name,
                    "region": chapter.region.name,
                    "delegate": None,
                    "alternate": None,
                    "term": None,
                    "year": None,
                }
                for chapter in missing_chapters
            ]
            if complete == "0":  # Incomplete
                data = missing_data
            else:  # All
                data.extend(missing_data)
        table = ConventionListTable(data=data)
        all_users = [[x["delegate"].email, x["alternate"].email] for x in data if x["delegate"]]
        flatten = [item for sublist in all_users for item in sublist]
        email_list = ", ".join(flatten)
        context["email_list"] = email_list
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        return context


class FilterProcessInvoiceListView(FilterProcessListView):
    template_name = "forms/initiationprocess/process_list.html"
    list_display = [
        "current_task",
        "chapter",
        "invoice",
        "created",
        "finished",
    ]

    def invoice(self, process):
        invoice = "unknown"
        if hasattr(process, "invoice"):
            invoice = process.invoice
        return invoice

    invoice.short_description = "Invoice"


class FilterableInvoiceFlowViewSet(FlowViewSet):
    process_list_view = [r"^$", FilterProcessInvoiceListView.as_view(), "index"]


@group_required("natoff")
@csrf_exempt
def pledge_process_csvs(request, csv_type, process_pk):
    process = get_object_or_404(PledgeProcess, pk=process_pk)
    response = HttpResponse(content_type="text/csv")
    if csv_type == "crm":
        process.generate_blackbaud_update(response=response)
    elif csv_type == "invoice":
        process.generate_invoice_attachment(response=response)
    response["Cache-Control"] = "no-cache"
    return response


@group_required("natoff")
@csrf_exempt
def pledge_process_sync(request, process_pk, invoice_number):
    process = get_object_or_404(PledgeProcess, pk=process_pk)
    new_invoice_number = process.sync_invoice(request, invoice_number)
    return JsonResponse({"invoice_number": new_invoice_number})


class AlumniExclusionListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = AlumniExclusion
    table_class = AlumniExclusionTable
    filter_class = AlumniExclusionListFilter
    formhelper_class = AlumniExclusionFormHelper

    def get_queryset(self, **kwargs):
        qs = AlumniExclusion.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if request_get:
            regional_director_veto = request_get.get("regional_director_veto", None)
            if regional_director_veto == "None":
                qs = qs.filter(regional_director_veto=None)
                request_get["regional_director_veto"] = ""
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()
        kwargs["natoff"] = True
        return kwargs

    def get_table_data(self):
        task = FlowTask.objects.filter(
            # ~Q(status="DONE"),  # This could be used to exclude tasks
            process_id=OuterRef("id"),
            flow_task__icontains="AlumniExclusionFlow.review",
        )
        qs = self.get_queryset()
        data = qs.annotate(task_pk=Subquery(task.values("pk")[:1])).annotate(
            task_pk=Case(
                When(task_pk=None, then=Value(0)),
                default=F("task_pk"),
                output_field=SmallIntegerField(),
            )
        )
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AlumniExclusionCreateView(LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin):
    template_name = "forms/alumniexclusion_form.html"
    model = AlumniExclusion
    form_class = AlumniExclusionForm
    submitted = False
    data = {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(self.request.user, type_sign="osm")
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                link = sign["link"]
                if self.request.user == sign["owner"] and link != "#" and not isinstance(link, bool):
                    return redirect(link)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        """Continue on task or redirect back to task list."""
        return reverse("alumniexclusion")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Alumni Exclusion form submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        task = FlowTask.objects.filter(
            # ~Q(status="DONE"),  # This could be used to exclude tasks
            process_id=OuterRef("id"),
            flow_task__icontains="AlumniExclusionFlow.review",
        )
        data = (
            AlumniExclusion.objects.filter(chapter=self.request.user.current_chapter)
            .annotate(task_pk=Subquery(task.values("pk")[:1]))
            .annotate(
                task_pk=Case(
                    When(task_pk=None, then=Value(0)),
                    default=F("task_pk"),
                    output_field=SmallIntegerField(),
                )
            )
        )
        table = AlumniExclusionTable(data=data)
        context["table"] = table
        return context


class AlumniExclusionDetailView(LoginRequiredMixin, NatOfficerRequiredMixin, DetailView):
    model = AlumniExclusion
    template_name = "forms/alumniexclusionreview.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["regional_director"] = True
        context["form"] = None
        return context


class AlumniExclusionReview(
    LoginRequiredMixin,
    NatOfficerRequiredMixin,
    AutoAssignUpdateProcessView,
    ModelFormMixin,
):
    template_name = "forms/alumniexclusionreview.html"
    model = AlumniExclusion
    form_class = AlumniExclusionReviewForm

    @property
    def fields(self):
        return None

    def dispatch(self, request, **kwargs):
        """Lock the process, initialize `self.activation`, check permission and execute."""
        result = super().dispatch(request, **kwargs)
        object = self.get_object()
        status = None
        if object:
            status = object.status
        if status == "DONE":
            list(messages.get_messages(request))
            result = HttpResponseRedirect(reverse("forms:alumniexclusion_detail", kwargs={"pk": object.pk}))
        return result

    def get_success_url(self):
        return reverse("alumniexclusion")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Alumni Exclusion updated successfully.")

    @fields.setter
    def fields(self, val):
        # On instantiate of UpdateProcessView tries to get fields and set empty
        # Ignore that
        pass

    def form_valid(self, form, *args, **kwargs):
        form.instance.regional_director = self.request.user
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        rds = self.object.chapter.region.directors.all()
        if self.request.user in rds or self.request.user.is_staff:
            context["regional_director"] = True
        context["rds"] = ", ".join(rds.values_list("name", flat=True))
        return context


class OSMCreateView(LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin):
    template_name = "forms/osm_form.html"
    model = OSM
    form_class = OSMForm
    submitted = False
    data = {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(self.request.user, type_sign="osm")
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                link = sign["link"]
                if self.request.user == sign["owner"] and link != "#" and not isinstance(link, bool):
                    return redirect(link)
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        """Continue on task or redirect back to task list."""
        return reverse("osmform")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Outstanding Student Member form submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        nominate = [form.instance.nominate, self.request.user]
        officers = chapter.get_current_officers_council_specific()
        self.assign_officers_form(nominate, form, officers)
        Task.mark_complete(
            name="Outstanding Student Member",
            chapter=chapter,
            user=self.request.user,
            obj=form.instance,
        )
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submitted"] = self.submitted
        process = OSM.objects.filter(chapter=self.request.user.current_chapter, year=OSM.current_year()).first()
        if process:
            context["nominate"] = process.nominate
        context["table"] = SignTable(data=self.data)
        return context


class OSMVerifyView(LoginRequiredMixin, UpdateProcessView, ModelFormMixin):
    template_name = "forms/osm_verify_form.html"
    model = OSM
    fields_options = {
        "assign_o1": [
            "approved_o1",
        ],
        "assign_o2": [
            "approved_o2",
        ],
    }

    def get_success_url(self):
        return reverse("osmform")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("OSM form signed successfully.")

    @property
    def fields(self):
        if not hasattr(self, "activation"):
            return None
        task_name = self.activation.flow_task.name
        return self.fields_options[task_name]

    @fields.setter
    def fields(self, val):
        # On instantiate of UpdateProcessView tries to get fields and set empty
        # Ignore that
        pass

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data, submitted, users = get_sign_status(self.request.user, type_sign="osm")
        context["submitted"] = submitted
        process = OSM.objects.filter(chapter=self.request.user.current_chapter, year=OSM.current_year()).first()
        if process:
            context["nominate"] = process.nominate
        context["table"] = SignTable(data=data)
        return context


class OSMListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = OSM
    context_object_name = "osm_list"
    table_class = OSMListTable
    filter_class = CompleteListFilter
    formhelper_class = CompleteFormHelper

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.GET.get("csv", "False").lower() == "download csv":
            response = HttpResponse(content_type="text/csv")
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTau_OSM_{time_name}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            emails = context["email_list"]
            if emails != "":
                writer.writerow(
                    [
                        "Chapter",
                        "Region",
                        "School",
                        "Role",
                        "Name",
                        "Email",
                        "Phone Number",
                        "Address",
                    ]
                )
                for form in self.object_list:
                    for user_type in ["nominate"]:
                        user = getattr(form, user_type)
                        writer.writerow(
                            [
                                form.chapter,
                                form.chapter.region,
                                form.chapter.school,
                                user_type,
                                user.name,
                                user.email,
                                user.phone_number,
                                user.address,
                            ]
                        )
                return response
            else:
                messages.add_message(
                    self.request,
                    messages.ERROR,
                    "All forms are filtered! Clear or change filter.",
                )
        return self.render_to_response(context)

    def get_queryset(self, **kwargs):
        qs = OSM.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [""])
            request_get.setlist("term", [""])
        if not cancel:
            if request_get.get("year", "") == "":
                request_get["year"] = datetime.datetime.now().year
            if request_get.get("term", "") == "":
                request_get["term"] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        data = [
            {
                "chapter": form.chapter.name,
                "region": form.chapter.region.name,
                "year": form.year,
                "term": OSM.TERMS.get_value(form.term),
                "nominate": form.nominate,
            }
            for form in all_forms
        ]
        complete = self.filter.form.cleaned_data["complete"]
        if complete in ["0", ""]:
            form_chapters = all_forms.values_list("chapter__id", flat=True)
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(candidate_chapter=True)
            else:
                missing_chapters = active_chapters.exclude(id__in=form_chapters)
            missing_data = [
                {
                    "chapter": chapter.name,
                    "region": chapter.region.name,
                    "nominate": None,
                    "term": None,
                    "year": None,
                }
                for chapter in missing_chapters
            ]
            if complete == "0":  # Incomplete
                data = missing_data
            else:  # All
                data.extend(missing_data)
        table = OSMListTable(data=data)
        all_users = [x["nominate"].email for x in data if x["nominate"]]
        email_list = ", ".join(all_users)
        context["email_list"] = email_list
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        return context


class DisciplinaryCreateView(LoginRequiredMixin, OfficerRequiredMixin, CreateProcessView):
    template_name = "forms/disciplinary_form.html"
    model = DisciplinaryProcess
    form_class = DisciplinaryForm1
    officer_edit = "disciplinary forms"
    officer_edit_type = "submit or view"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        url = reverse("forms:landing")
        if self.request.user.is_authenticated and self.request.user.is_officer_group:
            url = reverse("viewflow:forms:disciplinaryprocess:start")
        return url

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Disciplinary form submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = get_sign_status_discipline(self.request.user)
        context["table"] = DisciplinaryStatusTable(data=data)
        return context


class DisciplinaryForm2View(LoginRequiredMixin, UpdateProcessView, ModelFormMixin):
    template_name = "forms/disciplinary_form2.html"
    model = DisciplinaryProcess
    form_class = DisciplinaryForm2
    officer_edit = "disciplinary referrals"
    officer_edit_type = "submit or view"

    def get_success_url(self):
        url = reverse("forms:landing")
        if self.request.user.is_authenticated and self.request.user.is_officer_group:
            url = reverse("viewflow:forms:disciplinaryprocess:start")
        return url

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        if complete_activation(self.activation):
            self.success("Disciplinary form 2 submitted successfully.")
        else:
            # A concurrent/duplicate submit already advanced this task (#980).
            self.success("Disciplinary form 2 was already submitted.")

    def form_valid(self, form, *args, **kwargs):
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["date"] = datetime.datetime.today().date()
        return context


def get_signature():
    with open(r"secrets/JimGaffney_signature.jpg", "rb") as file:
        image = BytesIO(file.read())
        image_string = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode("utf-8").replace("\n", "")
    return image_string


class DisciplinaryPDFTest(NatOfficerRequiredMixin, PDFTemplateResponseMixin, DetailView, ModelFormMixin):
    model = DisciplinaryProcess
    template_name = "forms/disciplinary_expel_letter.html"
    form_class = DisciplinaryForm1

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        image_string = get_signature()
        context["signature"] = image_string
        all_fields = DisciplinaryForm1._meta.fields[:] + DisciplinaryForm2._meta.fields[:]
        all_fields.extend(["ed_process", "ed_notes", "ec_approval", "ec_notes"])
        info = {}
        for field in all_fields:
            field_obj = self.object._meta.get_field(field)
            if field == "user":
                info[field_obj.verbose_name] = self.object.user
                continue
            try:
                info[field_obj.verbose_name] = self.object._get_FIELD_display(field_obj)
            except TypeError:
                info[field_obj.verbose_name] = field_obj.value_to_string(self.object)
        context["info"] = info
        return context


@group_required("natoff")
@csrf_exempt
def disciplinary_process_files(request, process_pk):
    process = get_object_or_404(DisciplinaryProcess, pk=process_pk)
    zip_filename = f"{process.chapter.slug}_{process.user.id}.zip"
    zip_io = BytesIO()
    files = process.get_all_files()
    forms = process.forms_pdf()
    with zipfile.ZipFile(zip_io, "w") as zf:
        for file in files:
            zf.writestr(Path(file.name).name, file.read())
        zf.writestr(
            f"{process.chapter.slug}_{process.user.id}_disciplinary_forms.pdf",
            forms,
        )
    response = HttpResponse(zip_io.getvalue(), content_type="application/x-zip-compressed")
    response["Cache-Control"] = "no-cache"
    response["Content-Disposition"] = f"attachment; filename={zip_filename}"
    return response


class CollectionReferralFormView(LoginRequiredMixin, OfficerRequiredMixin, MultiFormsView):
    officer_edit = "collection referrals"
    officer_edit_type = "submit or view"
    template_name = "forms/collection.html"
    form_classes = {
        "collection": CollectionReferralForm,
        "user": UserForm,
    }
    grouped_forms = {"collection_referral": ["user", "collection"]}

    def get_success_url(self):
        url = reverse("forms:landing")
        if self.request.user.is_authenticated and self.request.user.is_officer_group:
            url = reverse("forms:collection")
        return url

    def collection_form_valid(self, form, *args, **kwargs):
        if form.has_changed():
            form.instance.created_by = self.request.user
            form.save()
        user = User.objects.get(pk=form.instance.user.pk)
        extra_emails = []
        if user.email != form.instance.user.email:
            extra_emails = [user.email]
        EmailProcessUpdate(
            form.instance,
            "Referral Submitted",
            "Central Office Processing",
            "Submitted",
            "This is a notification that your chapter has"
            " referred you to collections."
            " Please see below for the details of the referral and"
            " attached ledger sheet. If you have questions, please email or call"
            " the Central Office at central.office@thetatau.org //"
            " 512-472-1904.",
            process_title="Collection Referral",
            email_officers=True,
            fields=[
                "balance_due",
                "created",
                {"Member Chapter": user.chapter},
                {"Member Badge Number": user.badge_number},
                {"Member Email": user.email},
                {"Member Phone": user.phone_number},
                {"Member Address": user.address},
            ],
            attachments=["ledger_sheet"],
            extra_emails=extra_emails,
        ).send()
        messages.add_message(
            self.request,
            messages.INFO,
            "Successfully submitted collection referral",
        )
        return HttpResponseRedirect(self.get_success_url())

    def user_form_valid(self, form, *args, **kwargs):
        if form.has_changed():
            form.save()

    def get_collection_kwargs(self):
        return {"request_user": self.request.user}

    def get_user_kwargs(self):
        kwargs = {"verify": True}
        if self.request.method == "POST":
            user_pk = self.request.POST.get("user")
            user = User.objects.get(pk=user_pk)
            kwargs.update({"instance": user})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collections_table = CollectionReferralTable(
            CollectionReferral.objects.filter(user__chapter=self.request.user.current_chapter).order_by("-created")
        )
        RequestConfig(self.request).configure(collections_table)
        context["collections_table"] = collections_table
        return context


class ResignationCreateView(LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin):
    template_name = "forms/resignation_form.html"
    model = ResignationProcess
    form_class = ResignationForm
    data = {}

    def get_success_url(self):
        return reverse("forms:resignation")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Resignation Form submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        user = self.request.user
        exists = ResignationProcess.objects.filter(user=user).first()
        if exists:
            form.add_error(None, f"Resignation already exists for user {user}")
            return self.render_to_response(self.get_context_data(form=form))
        form.instance.user = user
        form.instance.chapter = user.current_chapter
        chapter = user.current_chapter
        officers = chapter.get_current_officers_council_specific()
        self.assign_officers_form([user], form, officers)
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            # ``user`` is a OneToOneField, so the ``exists`` check above is a
            # check-then-create that a rapid double submit can slip past (both
            # requests read no row, then both insert). The loser of that race
            # violates ``forms_resignationprocess_user_id_key`` (#833); treat it
            # as an already-submitted resignation instead of returning a 500.
            form.add_error(None, f"Resignation already exists for user {user}")
            return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        submitted = ResignationProcess.objects.filter(user=self.request.user).first()
        if submitted:
            data = []
            for task in submitted.task_set.all():
                if task.flow_task.task_title:
                    data.append(
                        {
                            "description": task.flow_task.task_title,
                            "owner": task.owner,
                            "started": task.started,
                            "finished": task.finished,
                            "status": task.status,
                        }
                    )
            context["table"] = ResignationStatusTable(data=data)
        context["submitted"] = submitted
        return context


class ResignationSignView(LoginRequiredMixin, UpdateProcessView):
    template_name = "forms/resignation_sign_form.html"
    model = ResignationProcess
    fields_options = {
        "assign_o1": [
            "good_standing",
            "returned",
            "financial",
            "fee_paid",
            "approved_o1",
            "signature_o1",
        ],
        "assign_o2": [
            "approved_o2",
            "signature_o2",
        ],
    }

    def get_success_url(self):
        url = reverse("forms:landing")
        if self.request.user.is_authenticated and self.request.user.is_officer_group:
            url = reverse("forms:resign_list")
        return url

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Resignation form signed successfully.")

    def get_form_class(self, *args, **kwargs):
        task_name = self.activation.flow_task.name
        self.fields = self.fields_options[task_name]
        return model_forms.modelform_factory(self.model, fields=self.fields)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = ResignationForm._meta.fields[:]
        fields.remove("letter")
        info = {}
        model_obj = self.object
        for field in fields:
            if isinstance(field, dict):
                info.update(field)
                continue
            field_obj = model_obj._meta.get_field(field)
            if field == "user":
                info[field_obj.verbose_name] = model_obj.user
                continue
            try:
                info[field_obj.verbose_name] = model_obj._get_FIELD_display(field_obj)
            except TypeError:
                info[field_obj.verbose_name] = field_obj.value_to_string(model_obj)
        context["info"] = info
        return context


class ResignationListView(LoginRequiredMixin, OfficerRequiredMixin, PagedFilteredTableView):
    model = ResignationProcess
    context_object_name = "resign_list"
    table_class = SignTable
    officer_edit = "resignations list"
    officer_edit_type = "view"

    def get_queryset(self, **kwargs):
        qs = self.model.objects.filter(user__chapter=self.request.user.current_chapter)
        return qs

    def get_table_data(self):
        data, submitted, users = get_sign_status(self.request.user, type_sign="resign")
        return data


class ReturnStudentCreateView(LoginRequiredMixin, CreateProcessView):
    template_name = "forms/returnstudent_form.html"
    model = ReturnStudent
    form_class = ReturnStudentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("viewflow:forms:returnstudent:start")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Return Student form submitted successfully")

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        processes = ReturnStudent.objects.filter(user__chapter=self.request.user.current_chapter)
        for process in processes:
            status = "N/A"
            if process.finished is None:
                active_task = process.active_tasks().first()
                if active_task:
                    status = active_task.flow_task.task_title
                approved = "Pending"
            else:
                status = "Complete"
                approved = process.approved_exec
            data.append(
                {
                    "status": status,
                    "user": process.user,
                    "created": process.created,
                    "approved": approved,
                }
            )
        context["table"] = ReturnStudentStatusTable(data=data)
        return context


class PledgeProgramProcessDetailView(LoginRequiredMixin, DetailView):
    model = PledgeProgramProcess

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.request.user.current_chapter
        context["program_link"] = (
            f"https://docs.google.com/document/d/{chapter.nme_file_id}/edit" if chapter.nme_file_id != "none" else None
        )
        return context


class PledgeProgramProcessCreateView(LoginRequiredMixin, CreateProcessView):
    template_name = "forms/pledge_program_process.html"
    model = PledgeProgramProcess
    form_class = PledgeProgramForm

    def get_success_url(self):
        return reverse("viewflow:forms:pledgeprogramprocess:start")

    def get_object(self, queryset=None):
        program = PledgeProgram.objects.filter(
            chapter=self.request.user.current_chapter,
            year=PledgeProgram.current_year(),
            term=PledgeProgram.current_term(),
        ).first()
        return program

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Pledge Program submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        form.instance.year = datetime.datetime.now().year
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can sign submit pledge program: {*CHAPTER_OFFICER,}\n"
                f"Your current roles are: {*current_roles,}",
            )
            return super().form_invalid(form)
        else:
            program = form.save()
            if program.pk is None:
                # ``YearTermModel.save`` swallows the unique constraint IntegrityError
                # raised when a row for this chapter/year/term already exists, which
                # leaves ``program`` unsaved. A rapid double submit slips past the
                # ``get_object`` lookup this way, and the unsaved program then breaks
                # ``activation.done()`` with "save() prohibited to prevent data loss".
                existing = PledgeProgram.objects.filter(chapter=chapter, year=program.year, term=program.term).first()
                if existing is None:
                    form.add_error(None, "The pledge program could not be saved, please try again.")
                    return self.render_to_response(self.get_context_data(form=form))
                form.instance.pk = existing.pk
                form.instance.created = existing.created
                program = form.save()
            Task.mark_complete(
                name="New Member Education Program",
                chapter=chapter,
                user=self.request.user,
                obj=program,
            )
            self.activation.process.program = program
            self.activation.process.chapter = chapter
            return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.request.user.current_chapter
        data = []
        processes = PledgeProgramProcess.objects.filter(program__chapter=chapter)
        for process in processes:
            if process.finished is None:
                task = process.active_tasks().first()
                status = task.flow_task.task_title
                approved = "Pending"
            else:
                status = process.task_set.first().flow_task.task_title
                approved = process.APPROVAL.get_value(process.approval)

            data.append(
                {
                    "status": status,
                    "created": process.created,
                    "approved": approved,
                    "term": f"{process.program.term} {process.program.year}",
                    "pk": process.pk,
                }
            )
        submitted = False
        if self.object:
            if "NEW" in self.object.process.values_list("status", flat=True):
                submitted = "review"
            elif "approved" in self.object.process.values_list("approval", flat=True):
                submitted = "approved"
        context["submitted"] = submitted
        context["program_link"] = (
            f"https://docs.google.com/document/d/{chapter.nme_file_id}/edit" if chapter.nme_file_id != "none" else None
        )
        context["table"] = PledgeProgramStatusTable(data=data)
        return context


class BylawsListView(LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView):
    model = Bylaws
    context_object_name = "bylaws_list"
    table_class = BylawsListTable
    filter_class = BylawsListFilter
    formhelper_class = BylawsListFormHelper

    def get_queryset(self, **kwargs):
        qs = Bylaws.objects.all()
        cancel = self.request.GET.get("cancel", False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict(mutable=True)
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_chapters, dates = active_chapters_filter(self.filter)
        # Filter for the last submitted for each chapter
        # https://stackoverflow.com/questions/2074514/django-query-that-get-most-recent-objects-from-different-categories
        bylaws = (
            Bylaws.objects.order_by("chapter__id", "-created")
            .distinct("chapter__id")
            .filter(chapter__id__in=active_chapters.values_list("id", flat=True))
        )
        bylaws_chapters = bylaws.values_list("chapter__id", flat=True)

        class Missing:
            name = ""

        missing_data = [
            {
                "created": "",
                "bylaws": Missing,
                "changes": "",
                "chapter": chapter.name,
                "chapter.region": chapter.region.name,
            }
            for chapter in active_chapters.exclude(id__in=bylaws_chapters)
        ]
        data = list(bylaws) + missing_data
        table = BylawsListTable(data=data, chapter=True, order_by="chapter")
        context["table"] = table
        return context


class BylawsCreateView(
    LoginRequiredMixin,
    CreateView,
):
    form_class = BylawsForm
    model = Bylaws

    def get_success_url(self):
        if hasattr(self, "object"):
            chapter = self.object.chapter
            GenericEmail(
                emails=chapter.council_emails(),
                cc={"central.office@thetatau.org", chapter.region.email},
                addressee=f"{chapter.full_name} Officers",
                subject=f"{chapter.full_name} Bylaws Update",
                message=f"Updated bylaws were submitted. <br>With the following changes:<br>{self.object.changes} <br><br>Please see attached document.",
                attachments=[self.object.bylaws],
            ).send()
            messages.add_message(
                self.request,
                messages.INFO,
                "You successfully submitted updated chapter bylaws. "
                "An email was sent to the Executive Director and Regional Directors",
            )
        return reverse("forms:bylaws")

    def form_valid(self, form):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        return super().form_valid(form)

    def get_table(self, **kwargs):
        # We do this b/c we create the table ourselves
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = Bylaws.objects.filter(chapter=self.request.user.current_chapter)
        table = BylawsListTable(data=data)
        context["table"] = table
        return context


class RitualProficiencyCreateView(LoginRequiredMixin, NatOfficerRequiredMixin, CreateView):
    model = RitualProficiency
    form_class = RitualProficiencyForm
    template_name = "forms/ritual_proficiency_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.add_message(
            self.request,
            messages.INFO,
            f"Ritual Proficiency record saved for {form.instance.user}.",
        )
        return response

    def get_success_url(self):
        return reverse("forms:ritual_proficiency")


class RitualProficiencyUserTableView(LoginRequiredMixin, NatOfficerRequiredMixin, TemplateView):
    template_name = "forms/ritual_proficiency_table_partial.html"

    def get(self, request, *args, **kwargs):
        user_id = request.GET.get("user_id", "")
        if user_id:
            qs = RitualProficiency.objects.filter(user_id=user_id).order_by("-date")
        else:
            qs = RitualProficiency.objects.none()
        table = RitualProficiencyTable(data=qs)
        return render(request, self.template_name, {"table": table})


class OtherSchoolAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete for `StatusChange.new_school_other`.

    Officers may search existing entries or type a new school name to create
    one on the fly. Names that duplicate an existing `Chapter.school` are
    hidden from search results and refused at create-time.
    """

    def _is_authorized(self):
        user = self.request.user
        return user.is_authenticated and (user.is_officer_group or user.is_admin)

    def get_queryset(self):
        if not self._is_authorized():
            return OtherSchool.objects.none()
        chapter_schools = Chapter.objects.values_list("school", flat=True)
        qs = OtherSchool.objects.exclude(name__in=chapter_schools)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")

    def has_add_permission(self, request):
        user = request.user
        return user.is_authenticated and (user.is_officer_group or user.is_admin)

    def post(self, request, *args, **kwargs):
        if not self.has_add_permission(request):
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            return JsonResponse({"error": "School name is required."}, status=400)
        if Chapter.objects.filter(school__iexact=text).exists():
            return JsonResponse(
                {
                    "error": (
                        f"'{text}' is already a Theta Tau chapter school; "
                        "select it from the New School dropdown instead."
                    )
                },
                status=400,
            )
        obj, _ = OtherSchool.objects.get_or_create(name=text)
        return JsonResponse({"id": obj.pk, "text": str(obj)})


class EmployerAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete for `StatusChange.employer` and `User.employer`.

    Any signed-in member may search existing employer names or type a new one
    to create it inline, because members choose their own employer on their
    member information page.
    """

    def _is_authorized(self):
        return self.request.user.is_authenticated

    def get_queryset(self):
        if not self._is_authorized():
            return Employer.objects.none()
        qs = Employer.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")

    def has_add_permission(self, request):
        return request.user.is_authenticated

    def post(self, request, *args, **kwargs):
        if not self.has_add_permission(request):
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            return JsonResponse({"error": "Employer name is required."}, status=400)
        obj = employer_from_text(text)
        return JsonResponse({"id": obj.pk, "text": str(obj)})
