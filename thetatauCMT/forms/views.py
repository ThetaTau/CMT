import csv
import json
import datetime
from copy import deepcopy
from django.db.models import Q
from django.core.mail import send_mail
from django.forms import models as model_forms
from django.forms.models import modelformset_factory
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.http.request import QueryDict
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import render
from django import forms
from django.views.generic import UpdateView
from django.views.generic.edit import FormView, CreateView
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from crispy_forms.layout import Submit
from extra_views import FormSetView, ModelFormSetView
from easy_pdf.views import PDFTemplateResponseMixin
from viewflow.compat import _
from viewflow.flow.views import CreateProcessView, UpdateProcessView
from viewflow.frontend.viewset import FlowViewSet
from viewflow.frontend.views import ProcessListView
from viewflow.flow.views.mixins import FlowListMixin
from material.frontend import frontend_url
from core.forms import MultiFormsView
from core.models import TODAY_START, forever
from core.views import OfficerMixin, OfficerRequiredMixin, RequestConfig,\
    PagedFilteredTableView, NatOfficerRequiredMixin
from .forms import InitiationFormSet, InitiationForm, InitiationFormHelper, InitDeplSelectForm,\
    InitDeplSelectFormHelper, DepledgeFormSet, DepledgeFormHelper, StatusChangeSelectForm,\
    StatusChangeSelectFormHelper, GraduateForm, GraduateFormSet, CSMTFormSet, GraduateFormHelper, CSMTFormHelper,\
    RoleChangeSelectForm, RiskManagementForm, RoleChangeNationalSelectForm,\
    PledgeProgramForm, AuditForm, PledgeFormFull, ChapterReport, PrematureAlumnusForm,\
    AuditListFormHelper, RiskListFilter, PledgeProgramFormHelper,\
    ChapterInfoReportForm, ChapterReportFormHelper, ConventionForm, ConventionFormHelper
from tasks.models import TaskChapter, Task
from scores.models import ScoreType
from submissions.models import Submission
from users.models import User, UserStatusChange
from core.models import CHAPTER_OFFICER, COL_OFFICER_ALIGN, SEMESTER,\
    NAT_OFFICERS_CHOICES, CHAPTER_ROLES_CHOICES
from users.models import UserRoleChange
from users.forms import ExternalUserForm, UserForm
from users.notifications import NewOfficers
from chapters.models import Chapter, ChapterCurricula
from regions.models import Region
from .tables import GuardTable, BadgeTable, InitiationTable, DepledgeTable, \
    StatusChangeTable, PledgeFormTable, AuditTable, RiskFormTable,\
    PledgeProgramTable, ChapterReportTable, PrematureAlumnusStatusTable,\
    ConventionTable, ConventionListTable
from .models import Guard, Badge, Initiation, Depledge, StatusChange, RiskManagement,\
    PledgeForm, PledgeProgram, Audit, PrematureAlumnus, InitiationProcess, Convention,\
    PledgeProcess
from .filters import AuditListFilter, PledgeProgramListFilter,\
    ChapterReportListFilter, ConventionListFilter
from .notifications import EmailRMPSigned, EmailPledgeOther, EmailRMPReport,\
    EmailAdvisorWelcome, EmailPledgeConfirmation, EmailPledgeWelcome


sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters('password', 'password1', 'password2'))


@require_POST
@csrf_exempt
def pledge_form(request):
    if 'rawRequest' not in request.POST:
        return HttpResponseBadRequest('POST must contain right information')
    data = json.loads(request.POST['rawRequest'])
    name = f"{data['q35_name']['first']} {data['q35_name']['middle']} {data['q35_name']['last']}"
    email = data['q36_schoolEmail']
    school = data['q37_schoolName']
    chapter = Chapter.get_school_chapter(school)
    if chapter is not None:
        PledgeForm.objects.get_or_create(
            name=name,
            email=email,
            chapter=chapter
        )
    else:
        send_mail(
            '[CMT] New Pledge Form Chapter',
            f'There is a new school {school}',
            'cmt@thetatau.org',
            ['cmt@thetatau.org'],
            fail_silently=False,
        )
    return HttpResponse('Webhook received', status=200)


class InitDeplSelectView(OfficerRequiredMixin,
                         LoginRequiredMixin, OfficerMixin,
                         FormSetView):
    form_class = InitDeplSelectForm
    template_name = "forms/init-depl-select.html"
    factory_kwargs = {'extra': 0}
    officer_edit = 'pledge status'

    def get_initial(self):
        pledges = self.request.user.current_chapter.pledges()
        inits = Initiation.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-date')
        inits = [init.user.pk for init in inits]
        depledges = Depledge.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-date')
        depledges = [depledge.user.pk for depledge in depledges]
        init_depl = inits + depledges
        initial = [{'user': user.pk} for user in pledges if user.pk not in init_depl]
        return initial

    def get_formset(self):
        pledges = self.request.user.current_chapter.pledges()
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = pledges
        formset.empty_form = []
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        helper = InitDeplSelectFormHelper()
        helper.add_input(Submit("submit", "Next"))
        context['helper'] = helper
        processes = InitiationProcess.objects.filter(
            chapter__name=self.request.user.current_chapter)
        data = []
        for process in processes:
            active_task = process.active_tasks().first()
            if active_task:
                status = active_task.flow_task.task_description
            else:
                status = "Initiation Process Complete"
            members = ', '.join(list(
                process.initiations.values_list('user__name', flat=True)))
            data.append({
                'initiation': process.initiations.first().date,
                'submitted': process.created,
                'status': status,
                'member_names': members,
            })
        pledges = PledgeFormTable(PledgeForm.objects.filter(
            chapter=self.request.user.current_chapter).order_by('-created'))
        inits = InitiationTable(data=data, order_by='-submitted')
        depledges = DepledgeTable(Depledge.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-date'))
        RequestConfig(self.request).configure(inits)
        RequestConfig(self.request).configure(depledges)
        context['pledges_table'] = pledges
        context['init_table'] = inits
        context['depledge_table'] = depledges
        return context

    def formset_valid(self, formset):
        cleaned_data = deepcopy(formset.cleaned_data)
        selections = {'Initiate': [], 'Depledge': [], 'Defer': []}
        for info in cleaned_data:
            user = info['user']
            selections[info['state']].append(user.pk)
        self.request.session['init-selection'] = selections
        return super().formset_valid(formset)

    def get_success_url(self):
        return reverse('forms:initiation')


class InitiationView(OfficerRequiredMixin,
                     LoginRequiredMixin, OfficerMixin, FormView):
    form_class = InitiationForm
    template_name = "forms/initiation.html"
    to_initiate = []
    to_depledge = []
    to_defer = []
    next_badge = 999999
    officer_edit = 'pledge status'

    def initial_info(self, initiate):
        pledges = self.request.user.current_chapter.pledges()
        self.to_initiate = pledges.filter(pk__in=initiate['Initiate'])
        self.to_depledge = pledges.filter(pk__in=initiate['Depledge'])
        self.to_defer = pledges.filter(pk__in=initiate['Defer'])
        self.next_badge = self.request.user.current_chapter.next_badge_number()['badge_number__max']
        if self.next_badge is None:
            self.next_badge = 0
        self.next_badge += 1

    def get(self, request, *args, **kwargs):
        initiate = request.session.get('init-selection', None)
        if initiate is None:
            return redirect('forms:init_selection')
        else:
            self.initial_info(initiate)
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = InitiationFormSet(prefix='initiates')
        formset.initial = [{'user': user.name,
                            'roll': self.next_badge+num} for num, user in enumerate(self.to_initiate)]
        chapter = self.request.user.current_chapter
        if chapter.colony:
            formset.form.base_fields['badge'].queryset = \
                Badge.objects.filter(Q(name__icontains='Colony'))
        else:
            formset.form.base_fields['badge'].queryset = \
                Badge.objects.filter(~Q(name__icontains='Colony'))
        context['formset'] = formset
        context['helper'] = InitiationFormHelper()
        depledge_formset = kwargs.get('depledge_formset', None)
        if depledge_formset is None:
            depledge_formset = DepledgeFormSet(prefix='depledges')
        depledge_formset.initial = [{'user': user.name} for user in self.to_depledge]
        context['depledge_formset'] = depledge_formset
        context['depledge_helper'] = DepledgeFormHelper()
        context['form_show_errors'] = True
        context['error_text_inline'] = True
        context['help_text_inline'] = True
        guards = GuardTable(Guard.objects.all().order_by('name'))
        badges = BadgeTable(Badge.objects.all().order_by('name'))
        RequestConfig(self.request).configure(guards)
        RequestConfig(self.request).configure(badges)
        context['guard_table'] = guards
        context['badge_table'] = badges
        return context

    def post(self, request, *args, **kwargs):
        initiate = request.session.get('init-selection', None)
        self.initial_info(initiate)
        formset = InitiationFormSet(request.POST, request.FILES, prefix='initiates')
        formset.initial = [{'user': user.name,
                            'roll': self.next_badge+num} for num, user in enumerate(self.to_initiate)]
        depledge_formset = DepledgeFormSet(request.POST, request.FILES, prefix='depledges')
        depledge_formset.initial = [{'user': user.name} for user in self.to_depledge]
        if not formset.is_valid() or not depledge_formset.is_valid():
            return self.render_to_response(self.get_context_data(formset=formset,
                                                                 depledge_formset=depledge_formset
                                                                 ))
        update_list = []
        depledge_list = []
        initiations = []
        for form in formset:
            form.save()
            update_list.append(form.instance.user)
            initiations.append(form.instance)
        for form in depledge_formset:
            form.save()
            depledge_list.append(form.instance.user)
        task = Task.objects.get(name="Initiation Report")
        chapter = self.request.user.current_chapter
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            TaskChapter(task=next_date, chapter=chapter,
                        date=timezone.now()).save()
        if update_list:
            messages.add_message(
                request, messages.INFO,
                f"You successfully submitted initiation report for:\n"
                f"{update_list}")
        if depledge_list:
            messages.add_message(
                request, messages.INFO,
                f"You successfully submitted depledge report for:\n"
                f"{depledge_list}")
        from .flows import InitiationProcessFlow
        if initiations:
            InitiationProcessFlow.start.run(initiations=initiations, request=request)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('home')


class StatusChangeSelectView(OfficerRequiredMixin,
                             LoginRequiredMixin, OfficerMixin, FormSetView):
    form_class = StatusChangeSelectForm
    template_name = "forms/status-select.html"
    factory_kwargs = {'extra': 1}
    prefix = 'selection'
    officer_edit = 'member status'

    def get_formset_request(self, request, action):
        formset = forms.formset_factory(StatusChangeSelectForm,
                                        extra=1)
        info = request.POST.copy()
        initial = []
        for info_name in info:
            if '__prefix__' not in info_name and info_name.endswith('-user'):
                split = info_name.split('-')[0:2]
                selected_split = deepcopy(split)
                selected_split.append('selected')
                selected_name = '-'.join(selected_split)
                selected = info.get(selected_name, None)
                if selected == 'on':
                    continue
                state_split = deepcopy(split)
                state_split.append('state')
                state_name = '-'.join(state_split)
                if info[info_name] != "":
                    initial.append({'user': info[info_name],
                                    'state': info[state_name],
                                    'selected': ''})
        if action in ['Add Row', 'Delete Selected']:
            formset = formset(prefix='selection', initial=initial)
        else:
            post_data = deepcopy(request.POST)
            post_data['selection-INITIAL_FORMS'] = str(int(post_data['selection-INITIAL_FORMS']) + 1)
            formset = formset(post_data, request.FILES,
                              initial=initial, prefix='selection')
        return formset

    def post(self, request, *args, **kwargs):
        formset = self.get_formset_request(request, request.POST['action'])
        if request.POST['action'] in ['Add Row', 'Delete Selected'] or not formset.is_valid():
            return self.render_to_response(self.get_context_data(formset=formset))
        else:
            return self.formset_valid(formset)

    def get_formset(self):
        actives = self.request.user.current_chapter.actives()
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = actives
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = self.construct_formset()
        actives = self.request.user.current_chapter.actives()
        formset.form.base_fields['user'].queryset = actives
        context['formset'] = formset
        helper = StatusChangeSelectFormHelper()
        context['helper'] = helper
        context['input'] = Submit("action", "Next")
        status = StatusChangeTable(StatusChange.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-created'))
        RequestConfig(self.request).configure(status)
        context['status_table'] = status
        return context

    def formset_valid(self, formset):
        cleaned_data = deepcopy(formset.cleaned_data)
        selections = {'graduate': [], 'coop': [], 'military': [],
                      'withdraw': [], 'transfer': []}
        for info in cleaned_data:
            user = info['user']
            selections[info['state']].append(user.pk)
        self.request.session['status-selection'] = selections
        return super().formset_valid(formset)

    def get_success_url(self):
        return reverse('forms:status')


class StatusChangeView(OfficerRequiredMixin,
                       LoginRequiredMixin, OfficerMixin, FormView):
    form_class = GraduateForm
    officer_edit = 'member status'
    template_name = "forms/status.html"
    to_graduate = []
    to_coop = []
    to_military = []
    to_withdraw = []
    to_transfer = []
    to_csmt = []

    def initial_info(self, status_change):
        actives = self.request.user.current_chapter.actives()
        self.to_graduate = actives.filter(pk__in=status_change['graduate'])
        self.to_coop = actives.filter(pk__in=status_change['coop'])
        self.to_military = actives.filter(pk__in=status_change['military'])
        self.to_withdraw = actives.filter(pk__in=status_change['withdraw'])
        self.to_transfer = actives.filter(pk__in=status_change['transfer'])
        self.to_csmt = self.to_coop | self.to_military | self.to_withdraw | self.to_transfer

    def get(self, request, *args, **kwargs):
        status_change = request.session.get('status-selection', None)
        if status_change is None:
            return redirect('forms:status_selection')
        else:
            self.initial_info(status_change)
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = GraduateFormSet(prefix='graduates')
        formset.initial = [{'user': user.name,
                            'email_personal': user.email,
                            'reason': 'graduate'} for user in self.to_graduate]
        context['formset'] = formset
        context['helper'] = GraduateFormHelper()
        csmt_formset = kwargs.get('csmt_formset', None)
        if csmt_formset is None:
            csmt_formset = CSMTFormSet(prefix='csmt')
            csmt_formset.initial = \
                [{'user': user.name, 'reason': 'coop'} for user in self.to_coop] + \
                [{'user': user.name, 'reason': 'military'} for user in self.to_military] + \
                [{'user': user.name, 'reason': 'withdraw'} for user in self.to_withdraw] + \
                [{'user': user.name, 'reason': 'transfer'} for user in self.to_transfer]
        context['csmt_formset'] = csmt_formset
        context['csmt_helper'] = CSMTFormHelper()
        context['form_show_errors'] = True
        context['error_text_inline'] = True
        context['help_text_inline'] = True
        # context['html5_required'] = True  #  If on errors do not show up
        return context

    def post(self, request, *args, **kwargs):
        status_change = request.session.get('status-selection', None)
        self.initial_info(status_change)
        formset = GraduateFormSet(request.POST, request.FILES, prefix='graduates')
        formset.initial = [{'user': user.name,
                            'email_personal': user.email,
                            'reason': 'graduate'} for user in self.to_graduate]
        csmt_formset = CSMTFormSet(request.POST, request.FILES, prefix='csmt')
        csmt_formset.initial = \
                [{'user': user.name, 'reason': 'coop'} for user in self.to_coop] + \
                [{'user': user.name, 'reason': 'military'} for user in self.to_military] + \
                [{'user': user.name, 'reason': 'withdraw'} for user in self.to_withdraw] + \
                [{'user': user.name, 'reason': 'transfer'} for user in self.to_transfer]
        if not formset.is_valid() or not csmt_formset.is_valid():
            return self.render_to_response(self.get_context_data(formset=formset,
                                                                 csmt_formset=csmt_formset
                                                                 ))
        update_list = []
        for form in formset:
            form.save()
            update_list.append(form.instance.user)
        for form in csmt_formset:
            form.save()
            update_list.append(form.instance.user)
        task = Task.objects.get(name="Member Updates")
        chapter = self.request.user.current_chapter
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            TaskChapter(task=next_date, chapter=chapter,
                        date=timezone.now()).save()
        messages.add_message(
            self.request, messages.INFO,
            f"You successfully updated the status of members:\n"
            f"{update_list}")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('home')


def remove_extra_form(formset, **kwargs):
    tfc = formset.total_form_count()
    del formset.forms[tfc - 1]
    data = formset.data
    total_count_name = '%s-%s' % (formset.management_form.prefix, 'TOTAL_FORMS')
    initial_count_name = '%s-%s' % (formset.management_form.prefix, 'INITIAL_FORMS')
    formset.management_form.cleaned_data['TOTAL_FORMS'] -= 1
    formset.management_form.cleaned_data['INITIAL_FORMS'] -= 1
    data[total_count_name] = formset.management_form.cleaned_data['TOTAL_FORMS'] - 1
    data[initial_count_name] = formset.management_form.cleaned_data['INITIAL_FORMS'] - 1
    formset.data = data
    return formset


class RoleChangeView(OfficerRequiredMixin,
                     LoginRequiredMixin, OfficerMixin, ModelFormSetView):
    form_class = RoleChangeSelectForm
    template_name = "forms/officer.html"
    factory_kwargs = {'extra': 1, 'can_delete': True}
    officer_edit = 'member roles'
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
            if 'user' not in form.initial:
                for field_name in form.fields:
                    formset.forms[idx].fields[field_name].disabled = False
        if not formset.is_valid():
            # Need to check if last extra form is causing issues
            if 'user' in formset.extra_forms[-1].errors:
                # We should remove this form
                formset = remove_extra_form(formset)
        if formset.is_valid():
            return self.formset_valid(formset)
        else:
            self.object_list = self.get_queryset()
            return self.formset_invalid(formset)

    def get_queryset(self):
        return UserRoleChange.get_current_roles(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = self.construct_formset()
        context['formset'] = formset
        context['input'] = Submit("action", "Submit")
        return context

    def formset_valid(self, formset, delete_only=False):
        delete_list = []
        for obj in formset.deleted_forms:
            # We don't want to delete the value, just make them not current
            # We also do not care about form, just get obj
            instance = None
            try:
                instance = obj.clean()['id']
            except KeyError:
                continue
            if instance:
                instance.end = timezone.now() - timezone.timedelta(days=2)
                instance.save()
                delete_list.append(instance.user)
        if delete_list:
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully removed the officers:\n"
                f"{delete_list}")
        if not delete_only:
            # instances = formset.save(commit=False)
            update_list = []
            officer_list = []
            for form in formset.forms:
                if form.changed_data and 'DELETE' not in form.changed_data:
                    form.save()
                    update_list.append(form.instance.user)
                    role_name = form.instance.role
                    if role_name in COL_OFFICER_ALIGN:
                        role_name = COL_OFFICER_ALIGN[role_name]
                    if role_name in CHAPTER_OFFICER:
                        officer_list.append(form.instance.user)
            task = Task.objects.get(name="Officer Election Report")
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                TaskChapter(task=next_date, chapter=chapter,
                            date=timezone.now()).save()
            if officer_list:
                NewOfficers(new_officers=officer_list).send()
            if update_list:
                messages.add_message(
                    self.request, messages.INFO,
                    f"You successfully updated the officers:\n"
                    f"{update_list}")
        return HttpResponseRedirect(reverse("forms:officer"))

    def get_success_url(self):
        return reverse("home")  # If this is the same view, login redirect loops


class RoleChangeNationalView(NatOfficerRequiredMixin,
                             LoginRequiredMixin, OfficerMixin, ModelFormSetView):
    form_class = RoleChangeNationalSelectForm
    template_name = "forms/officer_national.html"
    factory_kwargs = {'extra': 1, 'can_delete': True}
    model = UserRoleChange

    def construct_formset(self, initial=False):
        formset = super().construct_formset()
        for field_name in formset.forms[-1].fields:
            formset.forms[-1].fields[field_name].disabled = False
        return formset

    def get_success_url(self):
        return self.request.get_full_path()

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a formset instance with the passed
        POST variables and then checked for validity.
        """
        formset = self.construct_formset()
        for idx, form in enumerate(formset.forms):
            if 'user' not in form.initial:
                for field_name in form.fields:
                    formset.forms[idx].fields[field_name].disabled = False
        if not formset.is_valid():
            # Need to check if last extra form is causing issues
            if 'user' in formset.extra_forms[-1].errors:
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
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = self.construct_formset()
        context['formset'] = formset
        context['input'] = Submit("action", "Submit")
        return context

    def formset_valid(self, formset, delete_only=False):
        delete_list = []
        for obj in formset.deleted_forms:
            # We don't want to delete the value, just make them not current
            # We also do not care about form, just get obj
            instance = None
            try:
                instance = obj.clean()['id']
            except KeyError:
                continue
            if instance:
                instance.end = timezone.now() - timezone.timedelta(days=2)
                instance.save()
                delete_list.append(instance.user)
        if delete_list:
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully removed the officers:\n"
                f"{delete_list}")
        if not delete_only:
            update_list = []
            for form in formset.forms:
                if form.changed_data and 'DELETE' not in form.changed_data:
                    form.save()
                    update_list.append(form.instance.user)
            if update_list:
                messages.add_message(
                    self.request, messages.INFO,
                    f"You successfully updated the officers:\n"
                    f"{update_list}")
        return HttpResponseRedirect(reverse("forms:natoff"))


class ChapterReportListView(NatOfficerRequiredMixin, LoginRequiredMixin,
                            OfficerMixin, PagedFilteredTableView):
    model = ChapterReport
    context_object_name = 'chapter_report_list'
    table_class = ChapterReportTable
    filter_class = ChapterReportListFilter
    formhelper_class = ChapterReportFormHelper

    def get_queryset(self, **kwargs):
        qs = ChapterReport.objects.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [''])
            request_get.setlist("term", [''])
        if not cancel:
            if request_get['year'] == '':
                request_get['year'] = datetime.datetime.now().year
            if request_get['term'] == '':
                request_get['term'] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        data = [
            {
                'chapter': form.chapter.name,
                'region': form.chapter.region.name,
                'year': form.year,
                'term': ChapterReport.TERMS.get_value(form.term),
                'report': form.report
            } for form in all_forms
        ]
        complete = self.filter.form.cleaned_data['complete']
        if complete in ['0', '']:
            form_chapters = all_forms.values_list('chapter__id', flat=True)
            region_slug = self.filter.form.cleaned_data['region']
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == 'colony':
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(colony=True)
            else:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters)
            missing_data = [{
                 'chapter': chapter.name, 'region': chapter.region.name,
                 'report': None, 'term': None, 'year': None,
             } for chapter in missing_chapters]
            if complete == '0':  # Incomplete
                data = missing_data
            else:  # All
                data.extend(missing_data)
        table = ChapterReportTable(data=data)
        RequestConfig(self.request, paginate={'per_page': 100}).configure(table)
        context['table'] = table
        return context


class ChapterInfoReportView(LoginRequiredMixin, OfficerMixin, MultiFormsView):
    template_name = 'forms/chapter_report.html'
    form_classes = {
        'report': ChapterInfoReportForm,
        'faculty': ExternalUserForm,
    }
    grouped_forms = {
        'chapter_report': ['report', 'faculty']
    }

    def get_success_url(self, form_name=None):
        return reverse('forms:report')

    def faculty_form_valid(self, formset):
        if formset.has_changed():
            for form in formset.forms:
                if form.changed_data and 'DELETE' not in form.changed_data:
                    chapter = self.request.user.current_chapter
                    if form.instance.badge_number == 999999999:
                        form.instance.chapter = chapter
                        form.instance.badge_number = chapter.next_advisor_number
                    try:
                        # This is either a previous faculty or alumni
                        user = User.objects.get(username=form.instance.email)
                    except User.DoesNotExist:
                        user = form.save()
                    try:
                        status = UserStatusChange.objects.get(user=user)
                    except UserStatusChange.DoesNotExist:
                        UserStatusChange(
                            user=user,
                            status='advisor',
                            start=TODAY_START,
                            end=forever(),
                        ).save()
                        EmailAdvisorWelcome(user).send()
                elif form.changed_data and 'DELETE' in form.changed_data:
                    user = form.instance
                    try:
                        status = UserStatusChange.objects.get(user=user)
                    except UserStatusChange.DoesNotExist:
                        continue
                    else:
                        status.end = TODAY_START
                        status.save()
        return HttpResponseRedirect(self.get_success_url())

    def create_faculty_form(self, **kwargs):
        chapter = self.request.user.current_chapter
        facultys = chapter.advisors_external
        extra = 0
        min_num = 0
        if not facultys:
            extra = 0
            min_num = 1
        factory = modelformset_factory(
            User,
            form=ExternalUserForm,
            **{
                'can_delete': True,
                'extra': extra,
                'min_num': min_num,
                'validate_min': True,
            })
        # factory.form.base_fields['chapter'].queryset = chapter
        formset_kwargs = {
            'queryset': facultys,
            'form_kwargs': {
                'initial': {'chapter': chapter}
            }
        }
        if self.request.method in ('POST', 'PUT'):
            # if self.request.POST.get('action') == 'faculty': Not needed b/c grouped forms
            formset_kwargs.update({
                'data': self.request.POST.copy(),
            })
        return factory(**formset_kwargs)

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        kwargs.update(instance={
            'info': self.get_object(),
            # 'report': self.object.current_report,
        })
        return kwargs

    def report_form_valid(self, form):
        report = form['report']
        info = form['info']
        if report.has_changed():
            report.instance.user = self.request.user
            report.instance.chapter = self.request.user.current_chapter
            report.save()
            file_name = f"Risk Management Form {self.request.user}"
            score_type = ScoreType.objects.filter(slug="rmp").first()
            submit_obj = Submission(
                user=self.request.user,
                name=file_name,
                type=score_type,
                chapter=self.request.user.current_chapter,
                file=report.instance.report.file
            )
            submit_obj.save()
            EmailRMPReport(
                self.request.user, report.instance.report.file).send()
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully submitted the RMP and Agreements of Theta Tau!\n")
        if info.has_changed():
            info.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"object": self.get_object(), })
        return context

    def get_object(self):
        return self.request.user.current_chapter


class RiskManagementFormView(LoginRequiredMixin, OfficerMixin,
                             FormView):
    form_class = RiskManagementForm
    template_name = "forms/rmp.html"

    def get(self, request, *args, **kwargs):
        if RiskManagement.user_signed_this_year(self.request.user):
            messages.add_message(
                self.request, messages.INFO,
                f"RMP Previously signed this year, see previous submissions.")
            return redirect(reverse('users:detail')
                            + '#submissions')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        current_role = self.request.user.get_current_role()
        if not current_role:
            current_role = self.request.user.get_current_status()
            current_role = current_role.status
        else:
            current_role = current_role.role
        form.instance.user = self.request.user
        form.instance.role = current_role.replace(' ', '_')
        form.save()
        view = RiskManagementDetailView.as_view()
        new_request = self.request
        new_request.path = f'/forms/rmp-complete/{form.instance.id}'
        new_request.method = 'GET'
        risk_file = view(new_request, pk=form.instance.id)
        file_name = f"Risk Management Form {self.request.user}"
        score_type = ScoreType.objects.filter(slug="rmp").first()
        submit_obj = Submission(
            user=self.request.user,
            name=file_name,
            type=score_type,
            chapter=self.request.user.current_chapter,
        )
        submit_obj.file.save(f"{file_name}.pdf",
                             ContentFile(risk_file.content))
        submit_obj.save()
        form.instance.submission = submit_obj
        form.save()
        EmailRMPSigned(self.request.user, risk_file.content, file_name).send()
        messages.add_message(
            self.request, messages.INFO,
            f"You successfully signed the RMP and Agreements of Theta Tau!\n")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('home')


class RiskManagementDetailView(LoginRequiredMixin, OfficerMixin,
                               PDFTemplateResponseMixin, UpdateView):
    model = RiskManagement
    form_class = RiskManagementForm
    template_name = "forms/rmp_pdf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_officer'] = self.request.user.is_officer
        return context


class RiskManagementListView(NatOfficerRequiredMixin,
                             LoginRequiredMixin, OfficerMixin,
                             PagedFilteredTableView):
    model = RiskManagement
    context_object_name = 'risk'
    template_name = "forms/rmp_list.html"
    table_class = RiskFormTable
    filter_class = RiskListFilter

    def get_queryset(self, **kwargs):
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            request_get = None
        self.filter = self.filter_class(request_get)
        self.all_complete_status = 0
        self.chapters_list = Chapter.objects.all()
        if self.filter.is_bound and self.filter.is_valid():
            qs = RiskManagement.risk_forms_year(self.filter.cleaned_data['year'])
            region_slug = self.filter.cleaned_data['region']
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                self.chapters_list = Chapter.objects.filter(region__in=[region])
            elif region_slug == 'colony':
                self.chapters_list = Chapter.objects.filter(colony=True)
            qs = qs.filter(user__chapter__in=self.chapters_list)
            self.all_complete_status = int(self.filter.cleaned_data['all_complete_status'])
        else:
            qs = RiskManagement.risk_forms_year('2019')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        roles = ['regent', 'vice_regent', 'corresponding_secretary',
                 'treasurer', 'scribe', ]
        start_dic = {role: '' for role in roles}
        start_dic.update({f'{role}_pk': 0 for role in roles})
        chapter_risk_form_data = {
            chapter.name:
                {'chapter': chapter.name, 'region': chapter.region.name,
                 'all_complete': False, **start_dic}
            for chapter in self.chapters_list}
        risk_form_values = all_forms.values('pk', 'user__chapter__name', 'role', 'submission')
        # {
        #     'chapter': 'Chi',
        #     'all_complete': True,
        #     'corresponding_secretary': 'Complete',
        #     'treasurer': 'Complete',
        #     'scribe': 'Complete',
        #     'vice_regent': 'Complete',
        #     'regent': 'Complete',
        # }
        for risk_form in risk_form_values:
            chapter_risk_form_data[risk_form['user__chapter__name']][risk_form['role']] = 'Complete'
            chapter_risk_form_data[
                risk_form['user__chapter__name']][risk_form['role'] + "_pk"] = risk_form['pk']
        risk_data = []
        for chapter in chapter_risk_form_data:
            test = list(chapter_risk_form_data[chapter].values())
            if test.count('Complete') == 5:
                chapter_risk_form_data[chapter]['all_complete'] = True
                if self.all_complete_status == 1:
                    # We want only complete so keep this
                    risk_data.append(chapter_risk_form_data[chapter])
            else:
                if self.all_complete_status == 2:
                    # We want only incomplete so keep this
                    risk_data.append(chapter_risk_form_data[chapter])
            if self.all_complete_status == 0:
                # We want to keep everything
                risk_data.append(chapter_risk_form_data[chapter])
        risk_table = RiskFormTable(data=risk_data)
        RequestConfig(self.request, paginate={'per_page': 100}).configure(risk_table)
        context['table'] = risk_table
        return context


class PledgeProgramListView(NatOfficerRequiredMixin,
                            LoginRequiredMixin, OfficerMixin,
                            PagedFilteredTableView):
    model = PledgeProgram
    context_object_name = 'pledge_program'
    table_class = PledgeProgramTable
    filter_class = PledgeProgramListFilter
    formhelper_class = PledgeProgramFormHelper

    def get_queryset(self, **kwargs):
        qs = PledgeProgram.objects.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [''])
            request_get.setlist("term", [''])
        if not cancel:
            if request_get['year'] == '':
                request_get['year'] = datetime.datetime.now().year
            if request_get['term'] == '':
                request_get['term'] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        data = list(all_forms.values('chapter__name', 'chapter__region__name',
                                     'year', 'term', 'manual', 'remote',
                                     'date_complete', 'date_initiation'))
        for dat in data:
            dat['chapter'] = dat['chapter__name']
            del dat['chapter__name']
            dat['region'] = dat['chapter__region__name']
            del dat['chapter__region__name']
            dat['term'] = PledgeProgram.TERMS.get_value(dat['term'])
            dat['manual'] = PledgeProgram.MANUALS.get_value(dat['manual'])
        complete = self.filter.form.cleaned_data['complete']
        if complete in ['0', '']:
            form_chapters = all_forms.values_list('chapter__id', flat=True)
            region_slug = self.filter.form.cleaned_data['region']
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == 'colony':
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(colony=True)
            else:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters)
            missing_data = [{
                 'chapter': chapter.name, 'region': chapter.region.name,
                 'manual': None, 'term': None, 'year': None, 'remote': None,
                'date_complete': None, 'date_initiation': None,
             } for chapter in missing_chapters]
            if complete == '0':  # Incomplete
                data = missing_data
            else:  # All
                data.extend(missing_data)
        table = PledgeProgramTable(data=data)
        RequestConfig(self.request, paginate={'per_page': 100}).configure(table)
        context['table'] = table
        return context


class PledgeProgramFormView(OfficerRequiredMixin,
                            LoginRequiredMixin, OfficerMixin,
                            FormView):
    form_class = PledgeProgramForm
    template_name = "forms/pledge_program.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # program = PledgeProgram.form_chapter_term(
        #     chapter=self.request.user.current_chapter)
        program = PledgeProgram.objects.filter(
            chapter=self.request.user.current_chapter,
            year=PledgeProgram.current_year(),
            term=PledgeProgram.current_term(),
            ).first()
        context['current_program'] = program
        return context

    def form_valid(self, form):
        form.instance.chapter = self.request.user.current_chapter
        form.instance.year = datetime.datetime.now().year
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {''}:
            messages.add_message(
                self.request, messages.ERROR,
                f"Only executive officers can sign submit pledge program: {CHAPTER_OFFICER}\n"
                f"Your current roles are: {current_roles}")
            return super().form_invalid(form)
        else:
            form.save()
            task = Task.objects.get(name="Pledge Program")
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                task_obj = TaskChapter(task=next_date, chapter=chapter,
                                       date=timezone.now(),)
                score_type = ScoreType.objects.filter(
                    slug="pledge-program").first()
                submit_obj = Submission(
                    user=self.request.user,
                    file="forms:pledge_program",
                    name="Pledge program",
                    type=score_type,
                    chapter=self.request.user.current_chapter,
                )
                submit_obj.save(
                    extra_info={'unmodified': form.instance.manual != 'other'})
                task_obj.submission_object = submit_obj
                task_obj.save()
                if form.instance.manual == 'other':
                    EmailPledgeOther(
                        self.request.user, form.instance.other_manual.file).send()
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully submitted the Pledge Program!\n"
                f"Your current roles are: {current_roles}")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('home')


class AuditFormView(OfficerRequiredMixin, LoginRequiredMixin, OfficerMixin,
                    UpdateView):
    form_class = AuditForm
    template_name = "forms/audit.html"
    model = Audit

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complete = False
        if 'object' in context:
            form = context['form']
            for field_name, field in form.fields.items():
                field.disabled = True
            complete = True
        context['complete'] = complete
        return context

    def get_object(self, queryset=None):
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {''}:
            messages.add_message(
                self.request, messages.ERROR,
                f"Only executive officers can submit an audit: {CHAPTER_OFFICER}\n"
                f"Your current roles are: {current_roles}")
            return None
        else:
            if 'pk' in self.kwargs:
                try:
                    audit = Audit.objects.get(pk=self.kwargs['pk'])
                except Audit.DoesNotExist:
                    return Audit.objects.last()
                audit_chapter = audit.user.chapter
                if audit_chapter == self.request.user.chapter:
                    return audit
                else:
                    messages.add_message(
                        self.request, messages.ERROR,
                        f"Requested audit is for {audit_chapter} Chapter not your chapter."
                    )
            task = Task.objects.filter(name="Audit",
                                       owner__in=current_roles).first()
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                messages.add_message(
                    self.request, messages.INFO,
                    "You must submit an updated audit."
                )
                return None
            else:
                return self.request.user.audit_form.last()

    def form_valid(self, form):
        form.instance.year = datetime.datetime.now().year
        form.instance.user = self.request.user
        current_roles = self.request.user.chapter_officer()
        if not current_roles or current_roles == {''}:
            messages.add_message(
                self.request, messages.ERROR,
                f"Only executive officers can submit an audit: {CHAPTER_OFFICER}\n"
                f"Your current roles are: {current_roles}")
            return super().form_invalid(form)
        else:
            saved_audit = form.save()
            task = Task.objects.filter(name="Audit",
                                       owner__in=current_roles).first()
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                task_obj = TaskChapter(task=next_date, chapter=chapter,
                                       date=timezone.now(),)
                score_type = ScoreType.objects.filter(
                    slug="audit").first()
                submit_obj = Submission(
                    user=self.request.user,
                    file=f"forms:audit_complete {saved_audit.pk}",
                    name=f"Audit by {task.owner}",
                    type=score_type,
                    chapter=self.request.user.current_chapter,
                )
                submit_obj.save()
                task_obj.submission_object = submit_obj
                task_obj.save()
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully submitted the Audit Form!\n"
                f"Your current roles are: {current_roles}")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('home')


class AuditListView(NatOfficerRequiredMixin,
                    LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    model = Audit
    context_object_name = 'audit'
    table_class = AuditTable
    filter_class = AuditListFilter
    formhelper_class = AuditListFormHelper

    def get_queryset(self, **kwargs):
        qs = Audit.objects.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs


def load_majors(request):
    chapter_id = request.GET.get('chapter')
    majors = ChapterCurricula.objects.filter(
        chapter__pk=chapter_id).order_by('major')
    return render(request, 'forms/majors_dropdown_list_options.html', {'majors': majors})


class PledgeFormView(CreateView):
    form_class = PledgeFormFull
    template_name = "forms/pledge_form.html"

    def form_invalid(self, form):
        messages.add_message(
            self.request, messages.ERROR,
            f"Error with pledge form, please expand sections and correct error. "
            f"Error fields: {' '.join(form.errors.keys())}")
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        response = super().form_valid(form)
        EmailPledgeConfirmation(self.object).send()
        EmailPledgeWelcome(self.object).send()
        # EmailPledgeOfficer(self.object).send()
        processes = PledgeProcess.objects.filter(
            chapter__name=self.object.school_name, finished__isnull=True)
        active_process = None
        for process in processes:
            active_task = process.active_tasks().first()
            if active_task.flow_task.name == 'invoice_chapter':
                active_process = process
                break
        if active_process is None:
            from .flows import PledgeProcessFlow
            activation = PledgeProcessFlow.start.run(
                chapter=self.object.school_name, request=self.request)
            active_process = activation.process
        active_process.pledges.add(self.object)
        return response

    def get_success_url(self):
        messages.add_message(
            self.request, messages.INFO,
            f"You successfully submitted the Prospective New Member / Pledge Form! "
            f"A confirmation email was sent to your school and personal email.")
        return reverse('forms:pledgeform')


class PrematureAlumnusCreateView(OfficerRequiredMixin, LoginRequiredMixin,
                                 OfficerMixin, CreateProcessView):
    template_name = "forms/prematurealumnus_form.html"
    model = PrematureAlumnus
    form_class = PrematureAlumnusForm

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success('Premature Alumnus form submitted successfully to Executive Director for review')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        processes = PrematureAlumnus.objects.filter(user__chapter=self.request.user.current_chapter)
        for process in processes:
            if process.finished is None:
                status = process.active_tasks().first().flow_task.task_title
                approved = "Pending"
            else:
                status = "Complete"
                approved = process.approved_exec
            data.append({
                'status': status,
                'user': process.user,
                'created': process.created,
                'approved': approved,
            })
        context['table'] = PrematureAlumnusStatusTable(data=data)
        return context


@csrf_exempt
def badge_shingle_init_csv(request, csv_type, process_pk):
    process = InitiationProcess.objects.get(pk=process_pk)
    response = HttpResponse(content_type='text/csv')
    if csv_type in ['badge', 'shingle']:
        process.generate_badge_shingle_order(response, csv_type)
    elif csv_type == 'invoice':
        process.generate_blackbaud_update(invoice=True, response=response)
    else:
        process.generate_blackbaud_update(response=response)
    response['Cache-Control'] = 'no-cache'
    return response


def get_credential_status(user):
    data = []
    process = Convention.objects.filter(
        chapter=user.current_chapter,
        year=Convention.current_year()).first()
    submitted = False
    users = []
    if process:
        submitted = True
        signatures = {
            'delegate': 'del',
            'alternate': 'alt',
            'officer1': 'o1',
            'officer2': 'o2'
        }
        task_ids = {}
        for task in process.task_set.all():
            if task.flow_task.task_title:
                title = task.flow_task.task_title.split(' ')[0].lower()
                task_ids[title] = task.pk
        for signature, abbr in signatures.items():
            signed = getattr(process, f"signature_{abbr}", False)
            approved = "N/A"
            signer = getattr(process, signature)
            link = "#"
            if signed == '' or not signed:
                status = "Needs Signature"
                if user == signer and signature in task_ids:
                    link = reverse(
                        f'viewflow:forms:convention:assign_{abbr}',
                        kwargs={'process_pk': process.pk,
                                'task_pk': task_ids[signature]})
            else:
                status = "Signed"
                link = "#"
                approved = getattr(process, f"approved_{abbr}", "N/A")
            users.append(signer)
            if user.current_chapter.colony:
                if signature in ['delegate', 'alternate']:
                    signature = 'representative'
            data.append({
                'owner': signer,
                'role': signature,
                'status': status,
                'approved': approved,
                'link': link
            })
    return data, submitted, users


class ConventionCreateView(LoginRequiredMixin,
                           OfficerMixin, CreateProcessView):
    template_name = "forms/convention_form.html"
    model = Convention
    form_class = ConventionForm
    submitted = False
    data = {}

    def get(self, request, *args, **kwargs):
        self.data, self.submitted, self.signers = get_credential_status(self.request.user)
        officers = self.get_council_officers(request.user.current_chapter)
        if not all(officers):
            missing = [['regent', 'scribe', 'vice regent', 'treasurer'][ind]
                       for ind, miss in enumerate(officers) if not miss]
            messages.add_message(
                self.request, messages.ERROR,
                f"You must update the officers list! Missing officers: {missing}")
            return redirect(reverse('forms:officer'))
        if self.submitted and self.request.user in self.signers:
            for sign in self.data:
                if self.request.user == sign['owner'] and sign['status'] != 'Signed':
                    return redirect(sign['link'])
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        """Continue on task or redirect back to task list."""
        return reverse('conventionform')

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success('Convention Credential form submitted successfully.')

    def get_council_officers(self, chapter):
        officers = chapter.get_current_officers_council(combine=False)[0]
        regent = officers.filter(role='regent').first()
        scribe = officers.filter(role='scribe').first()
        vice = officers.filter(role='vice regent').first()
        treasurer = officers.filter(role='treasurer').first()
        return regent, scribe, vice, treasurer

    def form_valid(self, form, *args, **kwargs):
        chapter = self.request.user.current_chapter
        form.instance.chapter = chapter
        del_alt = [form.instance.delegate, form.instance.alternate]
        regent, scribe, vice, treasurer = self.get_council_officers(chapter)
        officer1 = officer2 = False
        if regent not in del_alt:
            form.instance.officer1 = regent
            officer1 = True
        if scribe not in del_alt:
            form.instance.officer2 = scribe
            officer2 = True
        if not officer1:
            if vice not in del_alt:
                form.instance.officer1 = vice
                del_alt.append(vice)
            else:
                form.instance.officer1 = treasurer
        if not officer2:
            if vice not in del_alt:
                form.instance.officer2 = vice
            else:
                form.instance.officer2 = treasurer
        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['submitted'] = self.submitted
        context['table'] = ConventionTable(data=self.data)
        return context


class ConventionSignView(LoginRequiredMixin, OfficerMixin,
                         UpdateProcessView, MultiFormsView):
    template_name = "forms/convention_sign_form.html"
    form_classes = {
        'process': None,
        'user': UserForm,
    }
    grouped_forms = {
        'form': ['process', 'user']
    }
    fields_options = {
        'assign_del': ['understand_del', 'signature_del', ],
        'assign_alt': ['understand_alt', 'signature_alt', ],
        'assign_o1': ['signature_o1', 'approved_o1', ],
        'assign_o2': ['signature_o2', 'approved_o2', ],
    }

    def _get_success_url(self, form=None):
        """Continue on task or redirect back to task list."""
        return reverse('conventionform')

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == 'user':
            kwargs.update(
                {'instance': self.request.user,
                 }
            )
        return kwargs

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        self.success('Convention Credential form signed successfully.')

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
        if 'del' not in task_name and 'alt' not in task_name:
            if 'user' in forms:
                del forms['user']
            if 'user' in self.form_classes:
                del self.form_classes['user']
            if 'user' in self.grouped_forms['form']:
                self.grouped_forms['form'].remove('user')
        return forms

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        task_name = self.activation.flow_task.name
        delegate = False
        if 'del' in task_name or 'alt' in task_name:
            delegate = True
            if 'user' in context['forms']:
                context['forms']['user'].fields['phone_number'].required = True
        data, submitted, users = get_credential_status(self.request.user)
        context['submitted'] = submitted
        context['table'] = ConventionTable(data=data)
        context['delegate'] = delegate
        return context


class ConventionListView(NatOfficerRequiredMixin, LoginRequiredMixin,
                         OfficerMixin, PagedFilteredTableView):
    model = Convention
    context_object_name = 'convention_list'
    table_class = ConventionListTable
    filter_class = ConventionListFilter
    formhelper_class = ConventionFormHelper

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.GET.get('csv', 'False').lower() == 'download csv':
            response = HttpResponse(content_type='text/csv')
            time_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ThetaTauConvention_{time_name}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            emails = context['email_list']
            if emails != "":
                writer.writerow([
                    'Chapter', 'Region', 'Role', 'Email',
                    'Phone Number', 'Address'
                ])
                for form in self.object_list:
                    for user_type in ['delegate', 'alternate']:
                        user = getattr(form, user_type)
                        writer.writerow(
                            [
                                form.chapter,
                                form.chapter.region,
                                user_type,
                                user.email,
                                user.phone_number,
                                user.address,

                            ]
                        )
                return response
            else:
                messages.add_message(
                    self.request, messages.ERROR,
                    f"All officers are filtered! Clear or change filter.")
        return self.render_to_response(context)

    def get_queryset(self, **kwargs):
        qs = Convention.objects.all()
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        if not request_get:
            # Create a mutable QueryDict object, default is immutable
            request_get = QueryDict(mutable=True)
            request_get.setlist("year", [''])
            request_get.setlist("term", [''])
        if not cancel:
            if request_get['year'] == '':
                request_get['year'] = datetime.datetime.now().year
            if request_get['term'] == '':
                request_get['term'] = SEMESTER[datetime.datetime.now().month]
        self.filter = self.filter_class(request_get,
                                        queryset=qs)
        self.filter.request = self.request
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_forms = self.object_list
        data = [
            {
                'chapter': form.chapter.name,
                'region': form.chapter.region.name,
                'year': form.year,
                'term': ChapterReport.TERMS.get_value(form.term),
                'delegate': form.delegate,
                'alternate': form.alternate
            } for form in all_forms
        ]
        complete = self.filter.form.cleaned_data['complete']
        if complete in ['0', '']:
            form_chapters = all_forms.values_list('chapter__id', flat=True)
            region_slug = self.filter.form.cleaned_data['region']
            region = Region.objects.filter(slug=region_slug).first()
            if region:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(region__in=[region])
            elif region_slug == 'colony':
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters).filter(colony=True)
            else:
                missing_chapters = Chapter.objects.exclude(id__in=form_chapters)
            missing_data = [{
                 'chapter': chapter.name, 'region': chapter.region.name,
                 'delegate': None, 'alternate': None, 'term': None, 'year': None,
             } for chapter in missing_chapters]
            if complete == '0':  # Incomplete
                data = missing_data
            else:  # All
                data.extend(missing_data)
        table = ConventionListTable(data=data)
        all_users = [[x['delegate'].email, x['alternate'].email] for x in data if x['delegate']]
        flatten = [item for sublist in all_users for item in sublist]
        email_list = ', '.join(flatten)
        context['email_list'] = email_list
        RequestConfig(self.request, paginate={'per_page': 100}).configure(table)
        context['table'] = table
        return context


class FilterProcessListView(ProcessListView, FlowListMixin):
    list_display = [
        'current_task', 'chapter', 'created', 'finished',
    ]
    datatable_config = {'searching': True}

    def chapter(self, process):
        return process.chapter
    chapter.short_description = 'Chapter'

    def get_object_list(self):
        """Create prepared queryset for datatables view."""
        queryset = self.get_queryset()
        search = self.request.GET.get('datatable-search[value]', False)
        if search:
            search_chapter = search
            search_status = False
            if ',' in search:
                search_chapter, search_status = search.split(',', 1)
                search_chapter = search_chapter.strip()
                search_status = search_status.strip().lower()
            if not search_chapter:
                search_chapter = False
            if not search_status:
                search_status = False
            if search_chapter:
                if '-' in search_chapter:
                    search_chapter = search_chapter.replace('-', '')
                    queryset = queryset.filter(Q(chapter__name__iexact=search_chapter))
                else:
                    queryset = queryset.filter(Q(chapter__name__icontains=search_chapter))
            if search_status:
                processes = []
                for process in queryset:
                    summary = 'complete'
                    active_tasks = process.active_tasks()
                    if active_tasks:
                        summary = active_tasks.first().summary().lower()
                    if search_status in summary:
                        processes.append(process.pk)
                queryset = queryset.model.objects.filter(pk__in=processes)
        return queryset

    def current_task(self, process):
        if process.finished is None:
            task = process.active_tasks().first()
            if task:
                summary = task.summary()
                if not summary:
                    summary = task.flow_task
                task_url = frontend_url(self.request, self.get_task_url(task), back_link='here')
                return mark_safe('<a href="{}">{}</a>'.format(task_url, summary))
        return 'Complete'
    current_task.short_description = _('Current Task')

    def get_task_url(self, task, url_type=None):
        namespace = self.request.resolver_match.namespace
        return task.flow_task.get_task_url(
            task, url_type=url_type if url_type else 'guess',
            user=self.request.user,
            namespace=namespace)


class FilterableFlowViewSet(FlowViewSet):
    process_list_view = [
        r'^$',
        FilterProcessListView.as_view(),
        'index'
    ]


@csrf_exempt
def pledge_process_csvs(request, csv_type, process_pk):
    process = PledgeProcess.objects.get(pk=process_pk)
    response = HttpResponse(content_type='text/csv')
    if csv_type == 'crm':
        process.generate_blackbaud_update(response=response)
    elif csv_type == 'invoice':
        process.generate_invoice_attachment(response=response)
    response['Cache-Control'] = 'no-cache'
    return response
