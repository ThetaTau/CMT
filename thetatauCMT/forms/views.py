from django.contrib.auth.mixins import LoginRequiredMixin
from crispy_forms.layout import Submit
from extra_views import FormSetView
from .forms import InitiationForm, InitiationFormHelper


class InitiationView(LoginRequiredMixin, FormSetView):
    form_class = InitiationForm
    template_name = "forms/initiation.html"
    factory_kwargs = {'extra': 0}

    def get_formset(self,):
        formset = super().get_formset()
        formset.form.base_fields['user'].queryset = self.request.user.chapter.get_pledges()
        formset.empty_form = []
        return formset

    def get_initial(self):
        pledges = self.request.user.chapter.get_pledges()
        initial = [{'user': user.pk} for user in pledges]
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        helper = InitiationFormHelper()
        helper.add_input(Submit("submit", "Save"))
        context['helper'] = helper
        return context
