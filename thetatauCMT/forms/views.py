import csv
import base64
import datetime
import zipfile
from io import BytesIO
from copy import deepcopy
from pathlib import Path
from django.db import IntegrityError, transaction
from django.db.models import (
    Q,
    F,
    Value,
    CharField,
    Count,
    Exists,
    OuterRef,
    Subquery,
    Case,
    When,
    SmallIntegerField,
)
from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.forms import models as model_forms
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django.http.request import QueryDict
from django.core.files.base import ContentFile
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import render
from django import forms
from django.views.generic import UpdateView, DetailView, TemplateView
from django.views.generic.edit import FormView, CreateView, ModelFormMixin
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from allauth.account.models import EmailAddress
from crispy_forms.layout import Submit
from extra_views import FormSetView, ModelFormSetView
from easy_pdf.views import PDFTemplateResponseMixin
from django_weasyprint import WeasyTemplateResponseMixin
from viewflow.flow.views import CreateProcessView, UpdateProcessView
from viewflow.frontend.viewset import FlowViewSet
from viewflow.models import Task as FlowTask

from core.flows import FilterProcessListView, AutoAssignUpdateProcessView
from core.forms import MultiFormsView
from core.models import (
    semester_encompass_start_end_date,
    TODAY_END,
    current_term,
    current_year,
    current_year_term_slug,
    CHAPTER_OFFICER,
    COL_OFFICER_ALIGN,
    SEMESTER,
)
from core.notifications import GenericEmail
from core.views import (
    OfficerRequiredMixin,
    LoginRequiredMixin,
    RequestConfig,
    PagedFilteredTableView,
    NatOfficerRequiredMixin,
    group_required,
    AssignOfficerFormMixin,
)
from surveys.notifications import DepledgeSurveyEmail, SurveyEmail
from users.tables import RollBookTable
from .forms import (
    InitiationFormSet,
    BylawsForm,
    BylawsListFormHelper,
    InitiationForm,
    InitiationFormHelper,
    InitDeplSelectForm,
    InitDeplSelectFormHelper,
    DepledgeFormSet,
    DepledgeFormHelper,
    StatusChangeSelectForm,
    StatusChangeSelectFormHelper,
    GraduateForm,
    GraduateFormSet,
    CSMTFormSet,
    GraduateFormHelper,
    CSMTFormHelper,
    RoleChangeSelectForm,
    RiskManagementForm,
    RoleChangeNationalSelectForm,
    PledgeProgramForm,
    AuditForm,
    PledgeFormFull,
    PrematureAlumnusForm,
    AuditListFormHelper,
    RiskListFormHelper,
    PledgeProgramFormHelper,
    CompleteFormHelper,
    ConventionForm,
    HSEducationForm,
    HSEducationListFormHelper,
    OSMForm,
    DisciplinaryForm1,
    DisciplinaryForm2,
    CollectionReferralForm,
    ResignationForm,
    ReturnStudentForm,
    AlumniExclusionForm,
    AlumniExclusionReviewForm,
    AlumniExclusionFormHelper,
)
from tasks.models import Task
from scores.models import ScoreType
from submissions.models import Submission
from configs.models import Config
from users.models import User, UserRoleChange
from users.forms import UserForm
from users.notifications import NewOfficers
from chapters.models import Chapter, ChapterCurricula
from regions.models import Region
from trainings.models import Training
from .tables import (
    BadgeTable,
    BylawsListTable,
    InitiationTable,
    DepledgeTable,
    StatusChangeTable,
    PledgeFormTable,
    AuditTable,
    RiskFormTable,
    PledgeProgramTable,
    HSEducationTable,
    HSEducationListTable,
    PrematureAlumnusStatusTable,
    SignTable,
    ConventionListTable,
    OSMListTable,
    DisciplinaryStatusTable,
    CollectionReferralTable,
    AlumniExclusionTable,
    ResignationStatusTable,
    ReturnStudentStatusTable,
    PledgeProgramStatusTable,
)
from .models import (
    Badge,
    Bylaws,
    Depledge,
    StatusChange,
    RiskManagement,
    PledgeProgram,
    Audit,
    HSEducation,
    PrematureAlumnus,
    InitiationProcess,
    Convention,
    PledgeProcess,
    OSM,
    DisciplinaryProcess,
    CollectionReferral,
    ResignationProcess,
    ReturnStudent,
    PledgeProgramProcess,
    AlumniExclusion,
)
from .filters import (
    AuditListFilter,
    BylawsListFilter,
    PledgeProgramListFilter,
    CompleteListFilter,
    RiskListFilter,
    EducationListFilter,
    AlumniExclusionListFilter,
)
from .notifications import (
    EmailRMPSigned,
    EmailPledgeOther,
    EmailPledgeConfirmation,
    EmailPledgeWelcome,
    EmailPledgeOfficer,
    EmailProcessUpdate,
)


class FormLanding(LoginRequiredMixin, TemplateView):
    template_name = "forms/landing.html"


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
        processes = InitiationProcess.objects.filter(
            chapter__name=self.request.user.current_chapter
        )
        initiation_data = []
        for process in processes:
            active_task = process.active_tasks().first()
            status = active_task
            if active_task:
                if active_task.flow_task:
                    status = active_task.flow_task.task_description
            else:
                status = "Initiation Process Complete"
            members = ", ".join(
                list(process.initiations.values_list("user__name", flat=True))
            )
            initiation_data.append(
                {
                    "initiation": process.initiations.first().date,
                    "submitted": process.created,
                    "status": status,
                    "member_names": members,
                }
            )
        pledgeprocesses = PledgeProcess.objects.filter(
            chapter__name=self.request.user.current_chapter
        )
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
            Depledge.objects.filter(
                user__chapter=self.request.user.current_chapter
            ).order_by("-date")
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
    response = HttpResponse(
        zip_io.getvalue(), content_type="application/x-zip-compressed"
    )
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
                {"user": user, "roll": self.next_badge + num}
                for num, user in enumerate(self.to_initiate)
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
            depledge_formset.initial = [
                {"user": user.name} for user in self.to_depledge
            ]
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
            {"user": user.pk, "roll": self.next_badge + num}
            for num, user in enumerate(self.to_initiate)
        ]
        depledge_formset = DepledgeFormSet(
            request.POST, request.FILES, prefix="depledges"
        )
        depledge_formset.initial = [{"user": user.name} for user in self.to_depledge]
        if not formset.is_valid() or not depledge_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    formset=formset, depledge_formset=depledge_formset
                )
            )
        update_list = []
        depledge_list = []
        initiations = []
        for form in formset:
            form.instance.chapter = self.request.user.current_chapter
            form.save()
            update_list.append(form.instance.user)
            initiations.append(form.instance)
        for form in depledge_formset:
            form.save()
            depledge_list.append(form.instance.user)
        Task.mark_complete(
            name="Initiation Report", chapter=self.request.user.current_chapter
        )
        if update_list:
            messages.add_message(
                request,
                messages.INFO,
                f"You successfully submitted initiation report for:\n" f"{update_list}",
            )
        if depledge_list:
            messages.add_message(
                request,
                messages.INFO,
                f"You successfully submitted depledge report for:\n" f"{depledge_list}",
            )
            for depledge in depledge_list:
                DepledgeSurveyEmail(depledge).send()
                depledge.set_no_contact()
                Training.deactivate_user(depledge, request=request)

        from .flows import InitiationProcessFlow

        ceremony = request.POST.get("initiates-__prefix__-ceremony", "normal")
        if initiations:
            InitiationProcessFlow.start.run(
                initiations=initiations, ceremony=ceremony, request=request
            )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:init_selection")


class StatusChangeSelectView(LoginRequiredMixin, FormSetView):
    form_class = StatusChangeSelectForm
    template_name = "forms/status-select.html"
    factory_kwargs = {"extra": 1}
    prefix = "selection"
    officer_edit = "member status"

    def get_formset_kwargs(self):
        kwargs = super().get_formset_kwargs()
        kwargs.update(
            {
                "form_kwargs": {
                    "colony": self.request.user.current_chapter.candidate_chapter
                },
            }
        )
        return kwargs

    def get_formset_request(self, request, action):
        formset = forms.formset_factory(StatusChangeSelectForm, extra=1)
        info = request.POST.copy()
        initial = []
        for info_name in info:
            if "__prefix__" not in info_name and info_name.endswith("-user"):
                split = info_name.split("-")[0:2]
                selected_split = deepcopy(split)
                selected_split.append("selected")
                selected_name = "-".join(selected_split)
                selected = info.get(selected_name, None)
                if selected == "on":
                    continue
                state_split = deepcopy(split)
                state_split.append("state")
                state_name = "-".join(state_split)
                if info[info_name] != "":
                    initial.append(
                        {
                            "user": info[info_name],
                            "state": info[state_name],
                            "selected": "",
                        }
                    )
        if action in ["Add Row", "Delete Selected"]:
            formset = formset(
                prefix="selection",
                initial=initial,
                form_kwargs={
                    "colony": self.request.user.current_chapter.candidate_chapter
                },
            )
        else:
            post_data = deepcopy(request.POST)
            post_data["selection-INITIAL_FORMS"] = str(
                int(post_data["selection-INITIAL_FORMS"]) + 1
            )
            formset = formset(
                post_data,
                request.FILES,
                initial=initial,
                prefix="selection",
                form_kwargs={
                    "colony": self.request.user.current_chapter.candidate_chapter
                },
            )
        return formset

    def post(self, request, *args, **kwargs):
        formset = self.get_formset_request(request, request.POST["action"])
        if (
            request.POST["action"] in ["Add Row", "Delete Selected"]
            or not formset.is_valid()
        ):
            return self.render_to_response(self.get_context_data(formset=formset))
        else:
            return self.formset_valid(formset)

    def get_formset(self):
        actives = self.request.user.current_chapter.actives()
        formset = super().get_formset()
        formset.form.base_fields["user"].queryset = actives.order_by("name")
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = self.construct_formset()
        actives = self.request.user.current_chapter.actives()
        formset.form.base_fields["user"].queryset = actives.order_by("name")
        context["formset"] = formset
        helper = StatusChangeSelectFormHelper()
        context["helper"] = helper
        context["input"] = Submit("action", "Next")
        status = StatusChangeTable(
            StatusChange.objects.filter(
                user__chapter=self.request.user.current_chapter
            ).order_by("-created")
        )
        RequestConfig(self.request).configure(status)
        context["status_table"] = status
        return context

    def formset_valid(self, formset):
        cleaned_data = deepcopy(formset.cleaned_data)
        selections = {
            "graduate": [],
            "coop": [],
            "covid": [],
            "military": [],
            "withdraw": [],
            "transfer": [],
            "resignedCC": [],
        }
        for info in cleaned_data:
            user = info["user"]
            selections[info["state"]].append(user.pk)
        self.request.session["status-selection"] = selections
        return super().formset_valid(formset)

    def get_success_url(self):
        # This needs to redirect to the next step
        return reverse("forms:status")


class StatusChangeView(LoginRequiredMixin, OfficerRequiredMixin, FormView):
    form_class = GraduateForm
    officer_edit = "member status"
    template_name = "forms/status.html"
    to_graduate = []
    to_coop = []
    to_military = []
    to_withdraw = []
    to_transfer = []
    to_csmt = []
    resignedCC = []

    def initial_info(self, status_change):
        chapter = self.request.user.current_chapter
        actives = chapter.actives()
        self.to_graduate = actives.filter(pk__in=status_change["graduate"])
        self.to_coop = actives.filter(pk__in=status_change["coop"])
        self.to_covid = actives.filter(pk__in=status_change["covid"])
        self.to_military = actives.filter(pk__in=status_change["military"])
        self.to_withdraw = actives.filter(pk__in=status_change["withdraw"])
        self.to_transfer = actives.filter(pk__in=status_change["transfer"])
        self.resignedCC = actives.filter(pk__in=status_change["resignedCC"])
        self.to_csmt = (
            self.to_coop
            | self.to_military
            | self.to_withdraw
            | self.to_transfer
            | self.to_covid
            | self.resignedCC
        )

    def get(self, request, *args, **kwargs):
        status_change = request.session.get("status-selection", None)
        if status_change is None:
            return redirect("forms:status_selection")
        else:
            self.initial_info(status_change)
            chapter = self.request.user.current_chapter
            officers = chapter.get_current_officers_council()[0]
            for member in self.to_coop:
                if member in officers:
                    role_info = member.roles.filter(
                        role__in=member.current_roles
                    ).values("role", "start", "end")
                    role_message = "<br>".join(
                        [
                            f"{role['role'].title()}:  start: {role['start']} end: {role['end']}"
                            for role in role_info
                        ]
                    )
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        mark_safe(
                            f"{member} is a current officer. COOP status must not overlap with officer term.<br>{role_message}"
                        ),
                    )
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = GraduateFormSet(prefix="graduates")
        formset.initial = [
            {"user": user.name, "email_personal": user.email, "reason": "graduate"}
            for user in self.to_graduate
        ]
        context["formset"] = formset
        context["helper"] = GraduateFormHelper()
        csmt_formset = kwargs.get("csmt_formset", None)
        if csmt_formset is None:
            csmt_formset = CSMTFormSet(prefix="csmt")
            next_semester = semester_encompass_start_end_date()[1]
            csmt_formset.initial = (
                [
                    {"user": user.name, "reason": "covid", "date_end": next_semester}
                    for user in self.to_covid
                ]
                + [{"user": user.name, "reason": "coop"} for user in self.to_coop]
                + [
                    {"user": user.name, "reason": "military"}
                    for user in self.to_military
                ]
                + [
                    {"user": user.name, "reason": "withdraw"}
                    for user in self.to_withdraw
                ]
                + [
                    {"user": user.name, "reason": "transfer"}
                    for user in self.to_transfer
                ]
                + [
                    {"user": user.name, "reason": "resignedCC"}
                    for user in self.resignedCC
                ]
            )
        context["csmt_formset"] = csmt_formset
        context["csmt_helper"] = CSMTFormHelper()
        context["form_show_errors"] = True
        context["error_text_inline"] = True
        context["help_text_inline"] = True
        # context['html5_required'] = True  #  If on errors do not show up
        return context

    def post(self, request, *args, **kwargs):
        status_change = request.session.get("status-selection", None)
        self.initial_info(status_change)
        formset = GraduateFormSet(request.POST, request.FILES, prefix="graduates")
        formset.initial = [
            {"user": user.name, "email_personal": user.email, "reason": "graduate"}
            for user in self.to_graduate
        ]
        csmt_formset = CSMTFormSet(request.POST, request.FILES, prefix="csmt")
        next_semester = semester_encompass_start_end_date()[1]
        csmt_formset.initial = (
            [
                {"user": user.name, "reason": "covid", "date_end": next_semester}
                for user in self.to_covid
            ]
            + [{"user": user.name, "reason": "coop"} for user in self.to_coop]
            + [{"user": user.name, "reason": "military"} for user in self.to_military]
            + [{"user": user.name, "reason": "withdraw"} for user in self.to_withdraw]
            + [{"user": user.name, "reason": "transfer"} for user in self.to_transfer]
            + [{"user": user.name, "reason": "resignedCC"} for user in self.resignedCC]
        )
        if not formset.is_valid() or not csmt_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(formset=formset, csmt_formset=csmt_formset)
            )
        chapter = self.request.user.current_chapter
        error = False
        officers = chapter.get_current_officers_council()[0]
        for form in csmt_formset:
            if form.instance.reason == "coop":
                member = form.instance.user
                if member in officers:
                    role_info = member.roles.filter(
                        role__in=member.current_roles + list(CHAPTER_OFFICER),
                    ).values("role", "start", "end")
                    for role in role_info:
                        latest_start = max(form.instance.date_start, role["start"])
                        earliest_end = min(form.instance.date_end, role["end"])
                        delta = (earliest_end - latest_start).days + 1
                        overlap = max(0, delta)
                        if overlap > 0:
                            error = True
                            role_message = f"{role['role'].title()}:  start: {role['start']} end: {role['end']}"
                            messages.add_message(
                                self.request,
                                messages.ERROR,
                                mark_safe(
                                    f"{member} is a current officer. COOP status must not overlap with officer term.<br>{role_message}"
                                ),
                            )
        if error:
            return self.render_to_response(
                self.get_context_data(formset=formset, csmt_formset=csmt_formset)
            )
        update_list = []
        graduates_list = []
        for form in formset:
            form.save()
            graduates_list.append(form.instance.user)
        for form in csmt_formset:
            if form.instance.reason == "covid":
                # Because the form field is disabled the value will not carry through
                form.instance.date_end = next_semester
            form.save()
            update_list.append(form.instance.user)
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
        messages.add_message(
            self.request,
            messages.INFO,
            f"You successfully updated the status of members:\n"
            f"{update_list + graduates_list}",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:status_selection")


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


class RoleChangeView(LoginRequiredMixin, ModelFormSetView):
    form_class = RoleChangeSelectForm
    template_name = "forms/officer.html"
    factory_kwargs = {"extra": 1, "can_delete": True}
    officer_edit = "member roles"
    model = UserRoleChange

    def construct_formset(self, initial=False):
        formset = super().construct_formset()
        for field_name in formset.forms[-1].fields:
            formset.forms[-1].fields[field_name].disabled = False
        return formset

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a formset instance with the passed
        POST variables and then checked for validity.
        """
        formset = self.construct_formset()
        for idx, form in enumerate(formset.forms):
            if "user" not in form.initial:
                for field_name in form.fields:
                    formset.forms[idx].fields[field_name].disabled = False
        if not formset.is_valid():
            # Need to check if last extra form is causing issues
            if "user" in formset.extra_forms[-1].errors:
                # We should remove this form
                formset = remove_extra_form(formset)
        if formset.is_valid():
            error = False
            for form in formset:
                try:
                    member = form.instance.user
                except User.DoesNotExist:
                    continue
                role = form.instance.role
                if role in CHAPTER_OFFICER:
                    status_info = member.status.filter(
                        status__in=["away"],
                    ).values("status", "start", "end")
                    for status in status_info:
                        latest_start = max(form.instance.start, status["start"])
                        earliest_end = min(form.instance.end, status["end"])
                        delta = (earliest_end - latest_start).days + 1
                        overlap = max(0, delta)
                        if overlap > 0:
                            error = True
                            role_message = f"Away status start: {status['start']} end: {status['end']}"
                            messages.add_message(
                                self.request,
                                messages.ERROR,
                                mark_safe(
                                    f"For member {member}. Away status (eg. COOP status) must not overlap with officer term.<br>{role_message}"
                                ),
                            )
            if error:
                self.object_list = self.get_queryset()
                return self.formset_invalid(formset)
            else:
                return self.formset_valid(formset)
        else:
            self.object_list = self.get_queryset()
            return self.formset_invalid(formset)

    def get_queryset(self):
        return UserRoleChange.get_current_roles(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = self.construct_formset()
        context["formset"] = formset
        context["input"] = Submit("action", "Submit")
        return context

    def formset_valid(self, formset, delete_only=False):
        delete_list = []
        for obj in formset.deleted_forms:
            # We don't want to delete the value, just make them not current
            # We also do not care about form, just get obj
            instance = None
            try:
                instance = obj.clean()["id"]
            except KeyError:
                continue
            if instance:
                instance.end = timezone.now() - timezone.timedelta(days=2)
                instance.save()
                delete_list.append(instance.user)
        if delete_list:
            messages.add_message(
                self.request,
                messages.INFO,
                f"You successfully removed the officers:\n" f"{delete_list}",
            )
        if not delete_only:
            # instances = formset.save(commit=False)
            update_list = []
            officer_list = []
            for form in formset.forms:
                if form.changed_data and "DELETE" not in form.changed_data:
                    form.save()
                    update_list.append(form.instance.user)
                    role_name = form.instance.role
                    if role_name in [
                        "pledge/new member educator",
                        "risk management chair",
                    ]:
                        Training.add_user(
                            form.instance.user,
                            extra_group=role_name,
                            request=self.request,
                        )
                    if role_name in COL_OFFICER_ALIGN:
                        role_name = COL_OFFICER_ALIGN[role_name]
                    if role_name in CHAPTER_OFFICER:
                        officer_list.append(form.instance.user)
            Task.mark_complete(
                name="Officer Election Report",
                chapter=self.request.user.current_chapter,
            )
            if officer_list:
                NewOfficers(new_officers=officer_list).send()
            if update_list:
                messages.add_message(
                    self.request,
                    messages.INFO,
                    f"You successfully updated the officers:\n" f"{update_list}",
                )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # If this is the same view, login redirect loops
        return reverse("forms:officer")


class RoleChangeNationalView(
    LoginRequiredMixin, NatOfficerRequiredMixin, ModelFormSetView
):
    form_class = RoleChangeNationalSelectForm
    template_name = "forms/officer_national.html"
    factory_kwargs = {"extra": 1, "can_delete": True}
    model = UserRoleChange

    def construct_formset(self, initial=False):
        formset = super().construct_formset()
        for field_name in formset.forms[-1].fields:
            formset.forms[-1].fields[field_name].disabled = False
        return formset

    def get_success_url(self):
        return reverse("forms:natoff")

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a formset instance with the passed
        POST variables and then checked for validity.
        """
        formset = self.construct_formset()
        for idx, form in enumerate(formset.forms):
            if "user" not in form.initial:
                for field_name in form.fields:
                    formset.forms[idx].fields[field_name].disabled = False
        if not formset.is_valid():
            # Need to check if last extra form is causing issues
            if "user" in formset.extra_forms[-1].errors:
                # We should remove this form
                formset = remove_extra_form(formset)
        if formset.is_valid():
            return self.formset_valid(formset)
        else:
            self.object_list = self.get_queryset()
            return self.formset_invalid(formset)

    def get_queryset(self):
        nat_offs = UserRoleChange.get_current_natoff()
        return nat_offs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get("formset", None)
        if formset is None:
            formset = self.construct_formset()
        context["formset"] = formset
        context["input"] = Submit("action", "Submit")
        return context

    def formset_valid(self, formset, delete_only=False):
        delete_list = []
        for obj in formset.deleted_forms:
            # We don't want to delete the value, just make them not current
            # We also do not care about form, just get obj
            instance = None
            try:
                instance = obj.clean()["id"]
            except KeyError:
                continue
            if instance:
                instance.end = timezone.now() - timezone.timedelta(days=2)
                instance.save()
                delete_list.append(instance.user)
        if delete_list:
            messages.add_message(
                self.request,
                messages.INFO,
                f"You successfully removed the officers:\n" f"{delete_list}",
            )
        if not delete_only:
            update_list = []
            for form in formset.forms:
                if form.changed_data and "DELETE" not in form.changed_data:
                    form.save()
                    update_list.append(form.instance.user)
            if update_list:
                for user in update_list:
                    Training.add_user_ed(user, self.request)
                messages.add_message(
                    self.request,
                    messages.INFO,
                    f"You successfully updated the officers:\n" f"{update_list}",
                )
        return HttpResponseRedirect(self.get_success_url())


class HSEducationListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
                    (program.get_approval_display(), program.report)
                    for program in harassment.filter(chapter=chapter)
                ],
                "mental": [
                    (program.get_approval_display(), program.report)
                    for program in mental.filter(chapter=chapter)
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
                "Your chapter has submitted a H&S Education Program."
                " Once the Central Office reviewed the program, "
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
            program.category
            for program in previous_programs
            if program.approval not in ["denied", "revisions"]
        ]
        incomplete_categories = [
            category.value[1]
            for category in HSEducation.CATEGORIES
            if category.value[0] not in complete_categories
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
        submit_obj.file.save(f"{file_name}.pdf", ContentFile(risk_file.content))
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


class RiskManagementDetailView(
    LoginRequiredMixin, PDFTemplateResponseMixin, UpdateView
):
    model = RiskManagement
    form_class = RiskManagementForm
    template_name = "forms/rmp_pdf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_officer"] = self.request.user.is_officer
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


class RollBookPDFView(
    LoginRequiredMixin, OfficerRequiredMixin, WeasyTemplateResponseMixin, DetailView
):
    model = User
    template_name = "forms/rollbook_pdf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        init_date = self.request.session.get(
            "init_date", datetime.datetime.today().date()
        )
        if isinstance(init_date, str):
            init_date = datetime.datetime.strptime(init_date, "%m/%d/%Y")
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


class RiskManagementListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
                    RiskManagement.objects.filter(
                        user=OuterRef("pk"), date__gte=start, date__lte=end
                    ),
                )
            )
            .values("chapter", "rmp_complete")
            .annotate(count=Count("rmp_complete"))
        ).order_by("chapter")
        return qs

    def get_table_data(self):
        all_forms = self.get_queryset()
        risk_data = all_forms.values(
            "chapter__name", "chapter__region__name", "rmp_complete", "count"
        )
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


class PledgeProgramListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
            approval=StringAgg("process__approval", ", "),
        )
        complete = self.filter.form.cleaned_data["complete"]
        if complete in ["0", ""]:
            form_chapters = all_forms.values_list("chapter__id", flat=True)
            region_slug = self.filter.form.cleaned_data["region"]
            region = Region.objects.filter(slug=region_slug).first()
            active_chapters = Chapter.objects.exclude(active=False)
            if region:
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    region__in=[region]
                )
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    candidate_chapter=True
                )
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
            chapter: [
                user.email
                for user in Chapter.objects.get(
                    name=chapter
                ).get_current_officers_council()[0]
            ]
            for chapter in chapter_names
        }
        table = PledgeProgramTable(data=data)
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


class AuditFormView(LoginRequiredMixin, OfficerRequiredMixin, UpdateView):
    form_class = AuditForm
    template_name = "forms/audit.html"
    model = Audit
    officer_edit = "audits"
    officer_edit_type = "submit"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complete = False
        if "object" in context:
            form = context["form"]
            for field_name, field in form.fields.items():
                field.disabled = True
            complete = True
        context["complete"] = complete
        return context

    def get_object(self, queryset=None):
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {""}:
            messages.add_message(
                self.request,
                messages.ERROR,
                f"Only executive officers can submit an audit: {*CHAPTER_OFFICER,}\n"
                f"Your current roles are: {*current_roles,}",
            )
            return None
        else:
            if "pk" in self.kwargs:
                try:
                    audit = Audit.objects.get(pk=self.kwargs["pk"])
                except Audit.DoesNotExist:
                    return Audit.objects.last()
                audit_chapter = audit.user.chapter
                if audit_chapter == self.request.user.current_chapter:
                    return audit
                else:
                    messages.add_message(
                        self.request,
                        messages.ERROR,
                        f"Requested audit is for {audit_chapter} Chapter not your chapter.",
                    )
            task = Task.objects.filter(name="Audit", owner__in=current_roles).first()
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                messages.add_message(
                    self.request, messages.INFO, "You must submit an updated audit."
                )
                return None
            else:
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
                f"You successfully submitted the Audit Form!\n"
                f"Your current roles are: {*current_roles,}",
            )
        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.is_authenticated:
            return (
                reverse(
                    "chapters:detail", kwargs={"slug": self.request.user.chapter.slug}
                )
                + "#audit"
            )
        else:
            return reverse("home")


class AuditListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
        majors = list(
            ChapterCurricula.objects.filter(
                chapter__pk=chapter_id, approved=True
            ).order_by("major")
        )
        if other:
            other = ChapterCurricula(pk=-1, major="Other")
            majors.append(other)
    return render(
        request, "forms/majors_dropdown_list_options.html", {"majors": majors}
    )


class PledgeFormView(CreateView):
    template_name = "forms/pledge_form.html"
    initial = {
        "demographics": {"gender": "", "sexual": "", "racial": "", "ability": ""}
    }

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
                    f"If you previously pledged Theta Tau, "
                    f"please have a chapter officer contact<br> "
                    f"central.office@thetatau.org to restart your pledge process."
                ),
            )
            return HttpResponseRedirect(self.get_success_url())
        demographics.instance.user = user
        demographics.save()
        pledge.instance.user = user
        self.object = pledge.save()
        user.set_current_status(status="pnm")
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
        processes = PledgeProcess.objects.filter(
            chapter=user.chapter, finished__isnull=True
        )
        active_process = None
        for process in processes:
            active_task = process.active_tasks().first()
            if active_task.flow_task.name == "invoice_chapter":
                active_process = process
                break
        if active_process is None:
            from .flows import PledgeProcessFlow

            activation = PledgeProcessFlow.start.run(
                chapter=user.chapter, request=self.request
            )
            active_process = activation.process
        active_process.pledges.add(self.object)
        Training.add_user(user, request=self.request)
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

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success(
            "Premature Alumnus form submitted successfully to Executive Director for review"
        )
        Task.mark_complete(
            name="Premature Alumnus",
            chapter=self.request.user.current_chapter,
            user=self.request.user,
            obj=self.object,
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        processes = PrematureAlumnus.objects.filter(
            user__chapter=self.request.user.current_chapter
        )
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
def badge_shingle_init_csv(request, csv_type, process_pk):
    process = InitiationProcess.objects.get(pk=process_pk)
    response = HttpResponse(content_type="text/csv")
    if csv_type in ["badge", "shingle"]:
        process.generate_badge_shingle_order(response, csv_type)
    elif csv_type == "invoice":
        process.generate_blackbaud_update(invoice=True, response=response)
    else:
        process.generate_blackbaud_update(response=response)
    response["Cache-Control"] = "no-cache"
    return response


@group_required("natoff")
@csrf_exempt
def badge_shingle_init_sync(request, process_pk, invoice_number):
    process = InitiationProcess.objects.get(pk=process_pk)
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
                status = task.status
                approved = False
            else:
                status = task.flow_task.task_title
                owner = task.owner
                approved = "Pending"
                if "Submit Form 2" in status and task.owner == user:
                    link = reverse(
                        "viewflow:forms:disciplinaryprocess:submit_form2",
                        kwargs={"process_pk": process.pk, "task_pk": task.pk},
                    )
        elif complete:
            status = process.task_set.first().flow_task.task_title
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
            member = ", ".join(
                [
                    str(getattr(process, member_field_name))
                    for member_field_name in member_field_names
                ]
            )
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


class ConventionCreateView(
    LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin
):
    template_name = "forms/convention_form.html"
    model = Convention
    form_class = ConventionForm
    submitted = False
    data = {}

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(self.request.user)
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                link = sign["link"]
                if (
                    self.request.user == sign["owner"]
                    and link != "#"
                    and not isinstance(link, bool)
                ):
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
        return model_forms.modelform_factory(self.model, fields=self.fields)(
            **self.get_form_kwargs()
        )

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


class ConventionListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    region__in=[region]
                )
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    candidate_chapter=True
                )
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
        all_users = [
            [x["delegate"].email, x["alternate"].email] for x in data if x["delegate"]
        ]
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
    process = PledgeProcess.objects.get(pk=process_pk)
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
    process = PledgeProcess.objects.get(pk=process_pk)
    new_invoice_number = process.sync_invoice(request, invoice_number)
    return JsonResponse({"invoice_number": new_invoice_number})


class AlumniExclusionListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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


class AlumniExclusionCreateView(
    LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin
):
    template_name = "forms/alumniexclusion_form.html"
    model = AlumniExclusion
    form_class = AlumniExclusionForm
    submitted = False
    data = {}

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(
            self.request.user, type_sign="osm"
        )
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                link = sign["link"]
                if (
                    self.request.user == sign["owner"]
                    and link != "#"
                    and not isinstance(link, bool)
                ):
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


class AlumniExclusionDetailView(
    LoginRequiredMixin, NatOfficerRequiredMixin, DetailView
):
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
    fields = None

    def dispatch(self, request, **kwargs):
        """Lock the process, initialize `self.activation`, check permission and execute."""
        result = super().dispatch(request, **kwargs)
        object = self.get_object()
        status = None
        if object:
            status = object.status
        if status == "DONE":
            list(messages.get_messages(request))
            result = HttpResponseRedirect(
                reverse("forms:alumniexclusion_detail", kwargs={"pk": object.pk})
            )
        return result

    def get_success_url(self):
        return reverse("alumniexclusion")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Alumni Exclusion updated successfully.")

    @property
    def fields(self):
        return None

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

    def get(self, request, *args, **kwargs):
        officers = request.user.current_chapter.get_current_officers_council_specific()
        if not self.check_officers(officers):
            return redirect(reverse("forms:officer"))
        self.data, self.submitted, self.signers = get_sign_status(
            self.request.user, type_sign="osm"
        )
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                link = sign["link"]
                if (
                    self.request.user == sign["owner"]
                    and link != "#"
                    and not isinstance(link, bool)
                ):
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
        process = OSM.objects.filter(
            chapter=self.request.user.current_chapter, year=OSM.current_year()
        ).first()
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
        process = OSM.objects.filter(
            chapter=self.request.user.current_chapter, year=OSM.current_year()
        ).first()
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
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    region__in=[region]
                )
            elif region_slug == "candidate_chapter":
                missing_chapters = active_chapters.exclude(id__in=form_chapters).filter(
                    candidate_chapter=True
                )
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


class DisciplinaryCreateView(
    LoginRequiredMixin, OfficerRequiredMixin, CreateProcessView
):
    template_name = "forms/disciplinary_form.html"
    model = DisciplinaryProcess
    form_class = DisciplinaryForm1
    officer_edit = "disciplinary forms"
    officer_edit_type = "submit or view"

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
        self.activation.done()
        self.success("Disciplinary form 2 submitted successfully.")

    def form_valid(self, form, *args, **kwargs):
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["date"] = datetime.datetime.today().date()
        return context


def get_signature():
    with open(r"secrets/JimGaffney_signature.jpg", "rb") as file:
        image = BytesIO(file.read())
        image_string = "data:image/png;base64," + base64.b64encode(
            image.getvalue()
        ).decode("utf-8").replace("\n", "")
    return image_string


class DisciplinaryPDFTest(
    NatOfficerRequiredMixin, PDFTemplateResponseMixin, DetailView, ModelFormMixin
):
    model = DisciplinaryProcess
    template_name = "forms/disciplinary_expel_letter.html"
    form_class = DisciplinaryForm1

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        image_string = get_signature()
        context["signature"] = image_string
        all_fields = (
            DisciplinaryForm1._meta.fields[:] + DisciplinaryForm2._meta.fields[:]
        )
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
    process = DisciplinaryProcess.objects.get(pk=process_pk)
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
    response = HttpResponse(
        zip_io.getvalue(), content_type="application/x-zip-compressed"
    )
    response["Cache-Control"] = "no-cache"
    response["Content-Disposition"] = f"attachment; filename={zip_filename}"
    return response


class CollectionReferralFormView(
    LoginRequiredMixin, OfficerRequiredMixin, MultiFormsView
):
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
            CollectionReferral.objects.filter(
                user__chapter=self.request.user.current_chapter
            ).order_by("-created")
        )
        RequestConfig(self.request).configure(collections_table)
        context["collections_table"] = collections_table
        return context


class ResignationCreateView(
    LoginRequiredMixin, CreateProcessView, AssignOfficerFormMixin
):
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
        return super().form_valid(form)

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


class ResignationListView(
    LoginRequiredMixin, OfficerRequiredMixin, PagedFilteredTableView
):
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

    def get_success_url(self):
        return reverse("viewflow:forms:returnstudent:start")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success("Return Student form submitted successfully")

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        processes = ReturnStudent.objects.filter(
            user__chapter=self.request.user.current_chapter
        )
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
            f"https://docs.google.com/document/d/{chapter.nme_file_id}/edit"
            if chapter.nme_file_id != "none"
            else None
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
            f"https://docs.google.com/document/d/{chapter.nme_file_id}/edit"
            if chapter.nme_file_id != "none"
            else None
        )
        context["table"] = PledgeProgramStatusTable(data=data)
        return context


class BylawsListView(
    LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView
):
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
                f"You successfully submitted updated chapter bylaws. "
                f"An email was sent to the Executive Director and Regional Directors",
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
