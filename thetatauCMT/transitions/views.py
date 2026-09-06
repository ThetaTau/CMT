"""TRWI-5: compose/submit views. Plain CreateView-style logic + services.py,
matching notes/objectives -- no viewflow (this feature has no approval step).
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from core.views import LoginRequiredMixin

from . import services
from .forms import ComposeReportForm, ReportAttachmentForm
from .models import ReportAttachment, ReportObligation


class TransitionsListView(LoginRequiredMixin, TemplateView):
    """The viewer's own obligations + submission history + reports they're
    entitled to read (TRWI-5, broadened by TRWI-6's access control service).

    ``readable_reports`` uses ``services.get_readable_reports`` -- author,
    successor, Regent, RD, and national-officer/admin access are ALL handled
    there; this view never re-derives a role check. The ``scope`` GET param
    (``"chapter"`` vs. anything else/unset) is the spec's "chapter vs.
    national scope" filter -- only shown when it would narrow anything (RD/
    national officer/admin), since a Regent or successor's readable set is
    already their own chapter only.
    """

    template_name = "transitions/transitions_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        obligations = services.get_my_obligations(user)
        position_choices = sorted({obligation.position_key for obligation in obligations})
        selected = self.request.GET.get("position_key", "")
        if selected:
            obligations = obligations.filter(position_key=selected)

        readable_reports = services.get_readable_reports(user)
        if selected:
            readable_reports = readable_reports.filter(position_key=selected)
        scope = self.request.GET.get("scope", "")
        if scope == "chapter" and user.current_chapter is not None:
            readable_reports = readable_reports.filter(chapter=user.current_chapter)

        context["obligations"] = obligations
        context["reports"] = services.get_my_reports(user)
        context["position_choices"] = position_choices
        context["selected_position_key"] = selected
        context["vacant_obligations"] = services.get_vacant_obligations_for_closer(user)
        context["readable_reports"] = readable_reports
        context["scope"] = scope
        context["show_scope_filter"] = user.is_admin or user.is_national_officer_group or user.director_regions.exists()
        return context


class ComposeReportView(LoginRequiredMixin, View):
    """Compose/edit/submit the report for one obligation.

    Only the obligation's own assigned officer may compose it -- there is no
    "someone else fills it in for you" path. Author may edit indefinitely
    (decision F15): no lock, no grace window, and editing after submission
    does not change ``status`` back to draft.
    """

    template_name = "transitions/compose_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.obligation = get_object_or_404(ReportObligation, pk=kwargs["pk"])
        if request.user.is_authenticated and request.user != self.obligation.officer:
            messages.error(request, "Only the assigned officer may compose this report.")
            return redirect("transitions:list")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        report = services.get_or_create_report(self.obligation)
        if report.template is None:
            messages.error(request, "No report template is configured for this position yet.")
            return redirect("transitions:list")
        form = ComposeReportForm(template=report.template, initial=ComposeReportForm.initial_from_report(report))
        return self._render(request, report, form)

    def post(self, request, *args, **kwargs):
        report = services.get_or_create_report(self.obligation)
        action = request.POST.get("action")
        if action == "add_attachment":
            return self._handle_attachment(request, report)

        submitting = action == "submit"
        form = ComposeReportForm(request.POST, template=report.template, submitting=submitting)
        if form.is_valid():
            if submitting:
                services.submit_report(report, form.answers_data())
                messages.success(request, "Transition Report submitted. Thank you!")
                return redirect("transitions:list")
            services.save_draft(report, form.answers_data())
            messages.success(request, "Draft saved.")
            return redirect("transitions:compose", pk=self.obligation.pk)
        return self._render(request, report, form)

    def _handle_attachment(self, request, report):
        attachment_form = ReportAttachmentForm(request.POST, request.FILES)
        if attachment_form.is_valid():
            attachment = attachment_form.save(commit=False)
            attachment.report = report
            attachment.uploaded_by = request.user
            attachment.save()
            messages.success(request, "Attachment added.")
        else:
            errors = "; ".join(str(error) for errors in attachment_form.errors.values() for error in errors)
            messages.error(request, f"That file could not be added: {errors}")
        return redirect("transitions:compose", pk=self.obligation.pk)

    def _render(self, request, report, form):
        return render(
            request,
            self.template_name,
            {
                "obligation": self.obligation,
                "report": report,
                "form": form,
                "attachment_form": ReportAttachmentForm(),
            },
        )


class AttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        attachment = get_object_or_404(ReportAttachment, pk=pk)
        if request.user != attachment.report.author:
            messages.error(request, "Only the report's author may remove an attachment.")
        else:
            attachment.file.delete(save=False)
            attachment.delete()
            messages.success(request, "Attachment removed.")
        return redirect("transitions:compose", pk=attachment.report.obligation_id)


class CloseNAVacantView(LoginRequiredMixin, View):
    """Regent/RD-only path that closes an obligation WITHOUT a report."""

    def post(self, request, pk):
        obligation = get_object_or_404(ReportObligation, pk=pk)
        if not services.can_close_na_vacant(request.user, obligation):
            messages.error(request, "Only the chapter Regent or a Regional Director can close this as vacant.")
        else:
            services.close_as_na_vacant(obligation)
            messages.success(request, "Closed as vacant -- no report required.")
        return redirect("transitions:list")
