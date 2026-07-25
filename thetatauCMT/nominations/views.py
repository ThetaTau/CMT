from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from viewflow.flow.views import CreateProcessView, UpdateProcessView
from viewflow.models import Task

from core.views import NationalOfficerRequiredMixin

from .forms import NominationForm, NomineeConsentForm
from .models import REVIEWER_APPOINTMENT, REVIEWER_CENTRAL_OFFICE, REVIEWER_TRAINING, Nomination, get_reviewer_for
from .providers import REQUIRED_TRAINING_KEYS, TRAININGS, get_training_provider
from .services import (
    add_to_natoff_lists,
    appointment_checklist,
    chapter_notification_recipients,
    complete_consent_task,
    has_active_appointment_task,
    has_active_consent_task,
    has_active_denial_task,
    has_active_training_task,
    mark_training_complete,
    try_complete_appointment,
    try_complete_denial,
)
from .tokens import get_nomination_by_token


class NominationCreateView(LoginRequiredMixin, CreateProcessView):
    """Start node: the volunteer recommendation form.

    One submission == one :class:`Nomination` process.  The submitting member
    is recorded as the ``nominator``.  On success the submitter is returned to
    the nominee's profile (regular members have no access to the workflow site).
    """

    template_name = "nominations/nomination_form.html"
    model = Nomination
    form_class = NominationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        nominee_pk = self.request.GET.get("nominee")
        if nominee_pk:
            initial["nominee"] = nominee_pk
        return initial

    def form_valid(self, form, *args, **kwargs):
        # The recommender is always the submitting member.
        form.instance.nominator = self.request.user
        if form.is_self_nomination():
            # The member is expressing their own interest -> clear any prior decline.
            Nomination.objects.filter(nominee=self.request.user, not_interested=True).update(not_interested=False)
        return super().form_valid(form, *args, **kwargs)

    def get_success_url(self):
        nominee = getattr(self.object, "nominee", None)
        if nominee is not None:
            return reverse("users:profile", kwargs={"username": nominee.username})
        return reverse("home")

    def activation_done(self, *args, **kwargs):
        """Finish task activation."""
        self.activation.done()
        nominee = getattr(self.object, "nominee", None)
        name = nominee.name if nominee else "The nominee"
        self.success(f"{name} has been submitted for consideration. " "They will be emailed to confirm their interest.")


class NomineeConsentView(View):
    """Tokenized, no-login landing page where a nominee responds.

    The nominee is an external actor, so this view sits OUTSIDE viewflow's task
    URLs: it resolves the nomination from the unguessable token, records the
    response, and completes the waiting ``nominee_consent`` task, which routes
    the flow to vetting / follow-up / closed.
    """

    template_name = "nominations/nominee_consent.html"

    def _state(self, nomination):
        if nomination is None:
            return "invalid"
        # Already acted on (or the process moved past consent) -> no active task.
        if not has_active_consent_task(nomination):
            return "responded"
        if nomination.consent_token_expired:
            return "expired"
        return "ok"

    def _render(self, request, nomination, state, form=None, response=None):
        context = {
            "nomination": nomination,
            "state": state,
            "form": form,
            "response": response,
        }
        return render(request, self.template_name, context)

    def get(self, request, token):
        nomination = get_nomination_by_token(token)
        state = self._state(nomination)
        form = NomineeConsentForm() if state == "ok" else None
        return self._render(request, nomination, state, form=form)

    def post(self, request, token):
        nomination = get_nomination_by_token(token)
        state = self._state(nomination)
        if state != "ok":
            return self._render(request, nomination, state)
        form = NomineeConsentForm(request.POST)
        if not form.is_valid():
            return self._render(request, nomination, "ok", form=form)
        response = self._apply(nomination, form)
        return self._render(request, nomination, "done", response=response)

    def _apply(self, nomination, form):
        response = form.cleaned_data["response"]
        nomination.consent_status = response
        nomination.consent_notes = form.cleaned_data.get("note", "")
        nomination.last_activity = timezone.now()
        if response == NomineeConsentForm.INTERESTED:
            nomination.interested_positions = form.cleaned_data.get("interested_positions", [])
            nomination.interested_level = form.cleaned_data.get("interested_level", "")
        elif response == NomineeConsentForm.NOT_INTERESTED:
            nomination.not_interested = True
        nomination.save()
        # Advance the flow past nominee_consent (check_consent routes on status).
        complete_consent_task(nomination)
        return response


class TrainingView(LoginRequiredMixin, View):
    """Manual training mark-complete screen (VWI-7).

    Surfaces the nominee and the two required trainings so the configured
    TrainingAdministrator can enrol them and mark each complete. Completion goes
    through ``services.mark_training_complete`` (the same seam a future LMS /
    Vector webhook uses), which advances the flow only once BOTH are complete.
    """

    template_name = "nominations/training.html"

    def _can_manage(self, request, nomination):
        user = request.user
        if user.is_superuser or user.is_national_officer_group:
            return True
        reviewer = get_reviewer_for(REVIEWER_TRAINING)
        return reviewer is not None and reviewer.pk == user.pk

    def _context(self, nomination):
        provider = get_training_provider()
        trainings = [
            {
                "key": key,
                "label": label,
                "complete": provider.is_complete(nomination, key),
            }
            for key, label in TRAININGS
        ]
        return {
            "nomination": nomination,
            "trainings": trainings,
            "at_training": has_active_training_task(nomination),
            "all_complete": provider.all_required_complete(nomination),
        }

    def get(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        return render(request, self.template_name, self._context(nomination))

    def post(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        key = request.POST.get("training_key")
        if key in REQUIRED_TRAINING_KEYS and has_active_training_task(nomination):
            mark_training_complete(nomination, key, completed_by=request.user)
            label = dict(TRAININGS).get(key, key)
            messages.success(request, f"Marked '{label}' complete for {nomination.nominee_display}.")
        return redirect("nominations:training", process_pk=process_pk)


class ConfirmationView(UpdateProcessView):
    """Confirmation review screen (VWI-8), gated to the configured Confirmer.

    Shows who nominated (linked to their profile), level + recommended
    positions, vetting + interview outcomes, training completion, and the
    process history, then lets the Confirmer confirm or deny.
    """

    template_name = "nominations/confirmation.html"

    def get_success_url(self):
        # The confirmation task is assigned to a config-driven Confirmer who may
        # not be a national officer, so the natoff-only review list and the
        # viewflow default ``:detail`` page (requires ``nominations.view_nomination``)
        # would both 403 them. Send them home, matching the safe landing used by
        # the nomination entry view.
        return reverse("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        process = self.activation.process
        context["nomination"] = process
        context["history_tasks"] = list(Task.objects.filter(process=process).order_by("created"))
        return context


class AppointmentView(LoginRequiredMixin, View):
    """Appointment processing checklist (VWI-9), gated to the AppointmentProcessor.

    Checklist: upload the appointment letter, email it to the nominee (records a
    timestamp), notify the affected chapter(s)/region, order the PPM, and add the
    appointee to the natoff lists. When every item is done the flow ends
    (appointed).
    """

    template_name = "nominations/appointment.html"

    def _can_manage(self, request, nomination):
        user = request.user
        if user.is_superuser or user.is_national_officer_group:
            return True
        reviewer = get_reviewer_for(REVIEWER_APPOINTMENT)
        return reviewer is not None and reviewer.pk == user.pk

    def _context(self, nomination):
        return {
            "nomination": nomination,
            "checklist": appointment_checklist(nomination),
            "at_appointment": has_active_appointment_task(nomination),
        }

    def get(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        return render(request, self.template_name, self._context(nomination))

    def post(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        if has_active_appointment_task(nomination):
            self._handle_action(request, nomination)
            try_complete_appointment(nomination)
        return redirect("nominations:appointment", process_pk=process_pk)

    def _handle_action(self, request, nomination):
        from .notifications import AppointmentLetterNotification, ChapterAppointmentNotification

        action = request.POST.get("action")
        if action == "upload_letter" and request.FILES.get("appointment_letter"):
            nomination.appointment_letter = request.FILES["appointment_letter"]
            nomination.save(update_fields=["appointment_letter"])
            messages.success(request, "Appointment letter uploaded.")
        elif action == "email_letter":
            AppointmentLetterNotification(nomination).send()
            nomination.appointment_letter_sent_at = timezone.now()
            nomination.save(update_fields=["appointment_letter_sent_at"])
            nomination.log_contact(
                kind="email",
                subject="Appointment letter emailed",
                recipient=nomination.nominee_email_address or "",
            )
            messages.success(request, f"Appointment letter emailed to {nomination.nominee_display}.")
        elif action == "notify_chapters":
            recipients = chapter_notification_recipients(nomination)
            if recipients:
                ChapterAppointmentNotification(nomination, recipients).send()
            nomination.chapters_notified = True
            nomination.save(update_fields=["chapters_notified"])
            nomination.log_contact(
                kind="chapter_notice",
                subject="Chapter/region notified of appointment",
                recipient=", ".join(recipients),
            )
            messages.success(request, "Chapter/region notified of the appointment.")
        elif action == "order_ppm":
            nomination.ppm_ordered = True
            nomination.save(update_fields=["ppm_ordered"])
            messages.success(request, "Marked the PPM as ordered.")
        elif action == "add_natoff":
            add_to_natoff_lists(nomination)
            messages.success(request, f"Added {nomination.nominee_display} to the national officer lists.")


class DenialCentralOfficeView(LoginRequiredMixin, View):
    """Central Office denial screen (VWI-10), gated to the configured CentralOffice.

    On a confirmation deny the CO uploads a denial letter and emails it to the
    nominee (recording the sent timestamp). Once both are done the flow ends
    (denied); the record is retained for possible future re-review.
    """

    template_name = "nominations/denial.html"

    def _can_manage(self, request, nomination):
        user = request.user
        if user.is_superuser or user.is_national_officer_group:
            return True
        reviewer = get_reviewer_for(REVIEWER_CENTRAL_OFFICE)
        return reviewer is not None and reviewer.pk == user.pk

    def _context(self, nomination):
        return {
            "nomination": nomination,
            "letter_uploaded": bool(nomination.denial_letter),
            "letter_emailed": nomination.denial_letter_sent_at is not None,
            "at_denial": has_active_denial_task(nomination),
        }

    def get(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        return render(request, self.template_name, self._context(nomination))

    def post(self, request, process_pk):
        nomination = get_object_or_404(Nomination, pk=process_pk)
        if not self._can_manage(request, nomination):
            raise PermissionDenied
        if has_active_denial_task(nomination):
            self._handle_action(request, nomination)
            try_complete_denial(nomination)
        return redirect("nominations:denial", process_pk=process_pk)

    def _handle_action(self, request, nomination):
        from .notifications import DenialLetterNotification

        action = request.POST.get("action")
        if action == "upload_letter" and request.FILES.get("denial_letter"):
            nomination.denial_letter = request.FILES["denial_letter"]
            nomination.denial_reason = request.POST.get("denial_reason", nomination.denial_reason)
            nomination.save(update_fields=["denial_letter", "denial_reason"])
            messages.success(request, "Denial letter uploaded.")
        elif action == "email_letter":
            DenialLetterNotification(nomination).send()
            nomination.denial_letter_sent_at = timezone.now()
            nomination.save(update_fields=["denial_letter_sent_at"])
            nomination.log_contact(
                kind="email",
                subject="Denial letter emailed",
                recipient=nomination.nominee_email_address or "",
            )
            messages.success(request, f"Denial letter emailed to {nomination.nominee_display}.")


class NominationListView(NationalOfficerRequiredMixin, ListView):
    """Natoff review page: every nomination + its current status, with a link
    out to nominate someone else (#10)."""

    template_name = "nominations/nomination_list.html"
    context_object_name = "nominations"
    paginate_by = 50

    def get_queryset(self):
        return Nomination.objects.select_related("nominee", "nominee__chapter", "nominator").order_by("-created")
