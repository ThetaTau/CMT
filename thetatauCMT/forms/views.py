from copy import deepcopy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.shortcuts import redirect
from crispy_forms.layout import Submit
from extra_views import FormSetView
from .forms import InitiationForm, InitiationFormHelper, InitDeplSelectForm,\
    InitDeplSelectFormHelper


class InitDeplSelectView(LoginRequiredMixin, FormSetView):
    form_class = InitDeplSelectForm
    template_name = "forms/init-depl-select.html"
    factory_kwargs = {'extra': 0}

    def get_initial(self):
        pledges = self.request.user.chapter.get_pledges()
        initial = [{'user': user.pk} for user in pledges]
        return initial

    def get_formset(self):
        pledges = self.request.user.chapter.get_pledges()
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


class InitiationView(LoginRequiredMixin, FormSetView):
    form_class = InitiationForm
    template_name = "forms/initiation.html"
    factory_kwargs = {'extra': 0}
    to_initiate = []
    to_depledge = []
    to_defer = []

    def get(self, request, *args, **kwargs):
        initiate = request.session.get('init-selection', None)
        if initiate is None:
            return redirect('forms:init_selection')
        else:
            pledges = self.request.user.chapter.get_pledges()
            self.to_initiate = pledges.filter(pk__in=initiate['Initiate'])
            self.to_depledge = pledges.filter(pk__in=initiate['Depledge'])
            self.to_defer = pledges.filter(pk__in=initiate['Defer'])
            return super().get(request, *args, **kwargs)

    def get_formset(self):
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = self.to_initiate
        formset.empty_form = []
        return formset

    def get_initial(self):
        initial = [{'user': user.pk} for user in self.to_initiate]
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        helper = InitiationFormHelper()
        helper.add_input(Submit("submit", "Save"))
        context['helper'] = helper
        return context
