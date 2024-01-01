from django.urls import reverse
from django.http import Http404
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q, Value, CharField, Count, When, Case
from django.forms.models import modelformset_factory
from django.views.generic import CreateView, DetailView
from django.http.response import HttpResponseRedirect
from core.forms import MultiFormsView
from core.views import (
    LoginRequiredMixin,
    PagedFilteredTableView,
)
from .filters import ObjectiveListFilter
from .forms import ObjectiveListFormHelper, ObjectiveForm, ActionForm
from .models import Objective, Action
from .tables import ObjectiveTable


class ObjectiveDetailView(LoginRequiredMixin, MultiFormsView):
    template_name = "objectives/objective_detail.html"
    model = Objective
    form_classes = {
        "objective": ObjectiveForm,
        "actions": None,
    }

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.restricted_co or self.object.restricted_ec
        ) and not request.user.is_superuser:
            messages.add_message(
                request,
                messages.INFO,
                f"You do not have permission to see this goal.",
            )
            return redirect(reverse("objectives:list"))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        messages.add_message(
            self.request,
            messages.INFO,
            f"Goal successfully update:",
        )
        return reverse("objectives:detail", kwargs={"pk": self.object.pk})

    def _get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "objective":
            kwargs.update(
                {
                    "instance": self.object,
                }
            )
        if form_name == "objective":
            kwargs.update({"owner": self.object.owner == self.request.user})
        return kwargs

    def objective_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url())

    def actions_form_valid(self, formset):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.objective = self.object
            instance.save()
        formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_object(self):
        pk = self.kwargs.get("pk")
        queryset = self.model._default_manager.all()
        if pk is not None:
            queryset = queryset.filter(pk=pk)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(
                f"No {queryset.model._meta.verbose_name}s found matching the query"
            )
        return obj

    def create_actions_form(self, **kwargs):
        actions = self.object.actions.all()
        extra = 0
        if not actions:
            extra = 1
        factory = modelformset_factory(
            Action, form=ActionForm, **{"can_delete": True, "extra": extra}
        )
        formset_kwargs = {
            "queryset": actions,
        }
        if self.request.method in ("POST", "PUT"):
            if self.request.POST.get("action") == "actions":
                formset_kwargs.update(
                    {
                        "data": self.request.POST.copy(),
                    }
                )
        return factory(**formset_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.object
        return context


class ObjectiveCreateView(LoginRequiredMixin, CreateView):
    model = Objective
    form_class = ObjectiveForm

    def get_success_url(self):
        return reverse("objectives:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        user = self.request.user
        instance = form.save(commit=False)
        instance.chapter = user.current_chapter
        instance.save()
        return super().form_valid(form)


class ObjectiveListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Objective
    context_object_name = "objective"
    ordering = ["-date"]
    table_class = ObjectiveTable
    filter_class = ObjectiveListFilter
    formhelper_class = ObjectiveListFormHelper
    filter_chapter = True

    def get_queryset(self, **kwargs):
        qs = super().get_queryset(**kwargs)
        qs = qs.exclude(Q(restricted_ec=True) | Q(restricted_co=True))
        qs = qs.annotate(
            actions_count=Count("actions__complete", filter=Q(actions__complete=False))
        )
        return qs
