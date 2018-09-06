from copy import deepcopy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django import forms
from django.views.generic.edit import FormView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from crispy_forms.layout import Submit
from extra_views import FormSetView, ModelFormSetView
from core.views import OfficerMixin, OfficerRequiredMixin, RequestConfig
from .forms import InitiationFormSet, InitiationForm, InitiationFormHelper, InitDeplSelectForm,\
    InitDeplSelectFormHelper, DepledgeFormSet, DepledgeFormHelper, StatusChangeSelectForm,\
    StatusChangeSelectFormHelper, GraduateForm, GraduateFormSet, CSMTFormSet, GraduateFormHelper, CSMTFormHelper,\
    RoleChangeSelectForm, RoleChangeSelectFormHelper, RiskManagementForm
from tasks.models import TaskChapter, Task
from core.models import CHAPTER_OFFICER, COL_OFFICER_ALIGN
from users.models import UserRoleChange
from .tables import GuardTable, BadgeTable, InitiationTable, DepledgeTable, \
    StatusChangeTable
from .models import Guard, Badge, Initiation, Depledge, StatusChange


sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters('password', 'password1', 'password2'))


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
        inits = InitiationTable(Initiation.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-date'))
        depledges = DepledgeTable(Depledge.objects.filter(
            user__chapter=self.request.user.current_chapter).order_by('-date'))
        RequestConfig(self.request).configure(inits)
        RequestConfig(self.request).configure(depledges)
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
        for form in formset:
            form.save()
            update_list.append(form.instance.user)
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


class RoleChangeView(OfficerRequiredMixin,
                     LoginRequiredMixin, OfficerMixin, ModelFormSetView):
    form_class = RoleChangeSelectForm
    template_name = "forms/officer.html"
    factory_kwargs = {'extra': 1, 'can_delete': True}
    prefix = 'selection'
    officer_edit = 'member roles'
    model = UserRoleChange

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        formset = self.construct_formset()
        action = request.POST['action']
        for form in formset.forms:
            form.fields['id'].required = False
            form.empty_permitted = True
        if action != 'Add Row' and not formset.is_valid():
            # Need to check if last extra form is causing issues
            if 'user' in formset.extra_forms[-1].errors:
                # We should remove this form
                formset = self.remove_extra_form(formset)
        # formset = self.remove_id_field(formset)
        if action == 'Add Row' or not formset.is_valid():
            if action == 'Add Row':
                formset = self.add_form(formset)
            return self.render_to_response(self.get_context_data(formset=formset))
        elif action == 'Delete Selected':
            return self.formset_valid(formset, delete_only=True)
        else:
            return self.formset_valid(formset)

    def get_queryset(self):
        return UserRoleChange.get_current_roles(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset = kwargs.get('formset', None)
        if formset is None:
            formset = self.construct_formset()
        context['formset'] = formset
        helper = RoleChangeSelectFormHelper()
        helper.add_input(Submit("submit", "Save"))
        context['helper'] = helper
        context['input'] = Submit("action", "Submit")
        context['delete'] = Submit("action", "Delete Selected")
        context['add'] = Submit("action", "Add Row")
        return context

    def add_form(self, formset, **kwargs):
        # add the form
        tfc = formset.total_form_count()
        formset.forms.append(formset._construct_form(tfc, **kwargs))
        formset.forms[tfc].is_bound = False
        formset.forms[tfc].empty_permitted = True
        data = formset.data
        # increase hidden form counts
        total_count_name = '%s-%s' % (formset.management_form.prefix, 'TOTAL_FORMS')
        initial_count_name = '%s-%s' % (formset.management_form.prefix, 'INITIAL_FORMS')
        data[total_count_name] = formset.management_form.cleaned_data['TOTAL_FORMS'] + 1
        data[initial_count_name] = formset.management_form.cleaned_data['INITIAL_FORMS'] + 1
        formset.data = data
        return formset

    def remove_extra_form(self, formset, **kwargs):
        # add the form
        tfc = formset.total_form_count()
        del formset.forms[tfc - 1]
        data = formset.data
        # increase hidden form counts
        total_count_name = '%s-%s' % (formset.management_form.prefix, 'TOTAL_FORMS')
        initial_count_name = '%s-%s' % (formset.management_form.prefix, 'INITIAL_FORMS')
        formset.management_form.cleaned_data['TOTAL_FORMS'] -= 1
        formset.management_form.cleaned_data['INITIAL_FORMS'] -= 1
        data[total_count_name] = formset.management_form.cleaned_data['TOTAL_FORMS'] - 1
        data[initial_count_name] = formset.management_form.cleaned_data['INITIAL_FORMS'] - 1
        formset.data = data
        return formset

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
            for form in formset.forms:
                if form.changed_data and 'DELETE' not in form.changed_data:
                    form.save()
                    update_list.append(form.instance.user)
            task = Task.objects.get(name="Officer Election Report")
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                TaskChapter(task=next_date, chapter=chapter,
                            date=timezone.now()).save()
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully updated the officers:\n"
                f"{update_list}")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("forms:officer")


class RiskManagementFormView(OfficerRequiredMixin,
                             LoginRequiredMixin, OfficerMixin,
                             FormView):
    form_class = RiskManagementForm
    template_name = "forms/rmp.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.save()
        current_role = self.request.user.get_current_role()
        if current_role.role not in CHAPTER_OFFICER:
            messages.add_message(
                self.request, messages.ERROR,
                f"Only executive officers can sign RMP: {CHAPTER_OFFICER}\n"
                f"Your current role is: {current_role}")
        else:
            if current_role in COL_OFFICER_ALIGN:
                current_role = COL_OFFICER_ALIGN[current_role]
            task = Task.objects.get(name="Risk Management Form",
                                    owner=current_role)
            chapter = self.request.user.current_chapter
            next_date = task.incomplete_dates_for_task_chapter(chapter).first()
            if next_date:
                task_obj = TaskChapter(task=next_date, chapter=chapter,
                                date=timezone.now(),)
                task_obj.submission_object = form.instance
                task_obj.save()
            messages.add_message(
                self.request, messages.INFO,
                f"You successfully signed the RMP!\n"
                f"Your current role is: {current_role}")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('home')
