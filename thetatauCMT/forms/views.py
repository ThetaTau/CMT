from copy import deepcopy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone
from django import forms
from django.views.generic.edit import FormView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from crispy_forms.layout import Submit
from extra_views import FormSetView
from core.views import OfficerMixin, OfficerRequiredMixin
from .forms import InitiationFormSet, InitiationForm, InitiationFormHelper, InitDeplSelectForm,\
    InitDeplSelectFormHelper, DepledgeFormSet, DepledgeFormHelper, StatusChangeSelectForm,\
    StatusChangeSelectFormHelper, GraduateForm, GraduateFormSet, CSMTFormSet, GraduateFormHelper, CSMTFormHelper,\
    RoleChangeSelectForm, RoleChangeSelectFormHelper
from tasks.models import TaskChapter, Task


class InitDeplSelectView(OfficerRequiredMixin,
                         LoginRequiredMixin, OfficerMixin,
                         FormSetView):
    form_class = InitDeplSelectForm
    template_name = "forms/init-depl-select.html"
    factory_kwargs = {'extra': 0}
    officer_edit = 'pledge status'

    def get_initial(self):
        pledges = self.request.user.chapter.pledges()
        initial = [{'user': user.pk} for user in pledges]
        return initial

    def get_formset(self):
        pledges = self.request.user.chapter.pledges()
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = pledges
        formset.empty_form = []
        return formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        helper = InitDeplSelectFormHelper()
        helper.add_input(Submit("submit", "Save"))
        context['helper'] = helper
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
        pledges = self.request.user.chapter.pledges()
        self.to_initiate = pledges.filter(pk__in=initiate['Initiate'])
        self.to_depledge = pledges.filter(pk__in=initiate['Depledge'])
        self.to_defer = pledges.filter(pk__in=initiate['Defer'])
        self.next_badge = self.request.user.chapter.next_badge_number()['badge_number__max']

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
        for form in formset:
            form.save()
        for form in depledge_formset:
            form.save()
        task = Task.objects.get(name="Initiation Report")
        chapter = self.request.user.chapter
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            TaskChapter(task=next_date, chapter=chapter,
                        date=timezone.now()).save()
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
        actives = self.request.user.chapter.actives()
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
        actives = self.request.user.chapter.actives()
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
        for form in formset:
            form.save()
        for form in csmt_formset:
            form.save()
        task = Task.objects.get(name="Member Updates")
        chapter = self.request.user.chapter
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            TaskChapter(task=next_date, chapter=chapter,
                        date=timezone.now()).save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('home')


class RoleChangeView(OfficerRequiredMixin,
                     LoginRequiredMixin, OfficerMixin, FormSetView):
    form_class = RoleChangeSelectForm
    template_name = "forms/officer.html"
    factory_kwargs = {'extra': 1}
    prefix = 'selection'
    officer_edit = 'member roles'

    def get_formset_request(self, request, action):
        formset = forms.formset_factory(RoleChangeSelectForm,
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
                state_split.append('role')
                state_name = '-'.join(state_split)
                start_split = deepcopy(split)
                start_split.append('start')
                start_name = '-'.join(start_split)
                end_split = deepcopy(split)
                end_split.append('end')
                end_name = '-'.join(end_split)
                if info[info_name] != "":
                    initial.append({'user': info[info_name],
                                    'role': info[state_name],
                                    'start': info[start_name],
                                    'end': info[end_name]})
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
        actives = self.request.user.chapter.actives()
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = actives
        return formset

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

    def formset_valid(self, formset):
        for form in formset:
            form.save()
        task = Task.objects.get(name="Officer Election Report")
        chapter = self.request.user.chapter
        next_date = task.incomplete_dates_for_task_chapter(chapter).first()
        if next_date:
            TaskChapter(task=next_date, chapter=chapter,
                        date=timezone.now()).save()
        return super().formset_valid(formset)

    def get_success_url(self):
        return reverse('home')
