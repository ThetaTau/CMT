"""TRWI-5: compose/submit views. Plain CreateView-style logic + services.py,
matching notes/objectives -- no viewflow (this feature has no approval step).
"""

from dal import autocomplete
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms.models import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from core.views import LoginRequiredMixin, RequestConfig
from thetatauCMT.chapters.models import Chapter

from . import services
from .filters import ComplianceRateFilter, NationalComplianceRateFilter, NationalSearchFilter, SearchFilter, TrendFilter
from .forms import (
    ComplianceRateFilterFormHelper,
    ComposeReportForm,
    ReportAttachmentForm,
    ReportContactForm,
    ReportKeyDateForm,
    SearchFilterFormHelper,
    TrendFilterFormHelper,
)
from .models import (
    POSITION_KEY_TO_TYPE,
    ReportAttachment,
    ReportContact,
    ReportKeyDate,
    ReportObligation,
    TransitionReport,
    TransitionTag,
)
from .tables import ChapterRateTable, ReportRowTable, TagFrequencyTable


class TransitionsListView(LoginRequiredMixin, TemplateView):
    """The viewer's own reports plus everything else, all on one page
    (2026-09 second merge): reports owed, submission history, handoff
    packets, and (inline, via the module-level ``_search_context`` helper
    shared with ``ReportSearchView``) the combined search/browse + chapter
    obligations table (TRWI-6/TRWI-9/TRWI-11), if they can see one. There is
    no more separate "Reports you can read" section, chapter compliance
    table, or "Dashboard & search reports" page for the viewer's own
    chapter -- an RD/National Officer/Admin inspecting a DIFFERENT chapter
    still uses the dedicated ``transitions:chapter-dashboard`` URL
    (``ReportSearchView``).
    """

    template_name = "transitions/transitions_list.html"

    def dispatch(self, request, *args, **kwargs):
        self.chapter = None
        if request.user.is_authenticated and request.user.chapter_id:
            # current_chapter, so a CSS (and a National Officer using the switcher)
            # sees the chapter they are viewing.
            chapter = request.user.current_chapter
            if services.can_view_chapter_dashboard(request.user, chapter):
                self.chapter = chapter
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        obligations = services.get_my_obligations(user)
        upcoming_reports = services.get_upcoming_reports(user)
        position_choices = sorted(
            {obligation.position_key for obligation in obligations}
            | {upcoming.position_key for upcoming in upcoming_reports}
        )
        no_obligations_reason = None if position_choices else services.get_no_obligations_reason(user)
        # "my_position_key", not "position_key": the search section below
        # (_search_context) has its own bare "position_key" filter field on
        # the same page, so this must not collide with it.
        selected = self.request.GET.get("my_position_key", "")
        if selected:
            obligations = obligations.filter(position_key=selected)
            upcoming_reports = [upcoming for upcoming in upcoming_reports if upcoming.position_key == selected]

        context["obligations"] = obligations
        context["upcoming_reports"] = upcoming_reports
        context["no_obligations_reason"] = no_obligations_reason
        context["reports"] = services.get_my_reports(user)
        context["position_choices"] = position_choices
        context["selected_position_key"] = selected
        context["vacant_obligations"] = services.get_vacant_obligations_for_closer(user)
        context["my_packets"] = [
            {"position_key": position_key, "chapter": user.chapter}
            for position_key in sorted(set(user.current_roles or []) & set(POSITION_KEY_TO_TYPE))
        ]
        context["show_rates_dashboard_link"] = services.can_view_compliance_rates(user)
        context["show_trends_link"] = services.can_view_trends(user)

        context.update(_search_context(self.request, chapter=self.chapter))
        return context


def _build_contacts_formset(report, data=None):
    """Contacts formset for the compose page (TRWI-13 proposal).

    ``extra=1`` always: the template clones ``contacts_formset.empty_form``
    client-side (``static/js/transitions_compose.js``'s ``addFormsetRow``) to
    add further rows with no page reload, so there is no need to pre-render
    a pile of blank ones. Blank extra rows are silently skipped by Django's
    own ``empty_permitted`` formset handling -- no manual filtering needed.
    """
    contacts = report.contacts.all()
    factory = modelformset_factory(ReportContact, form=ReportContactForm, can_delete=True, extra=1)
    kwargs = {"queryset": contacts, "prefix": "contacts"}
    if data is not None:
        kwargs["data"] = data
    return factory(**kwargs)


def _build_key_dates_formset(report, data=None):
    """Key Dates formset for the compose page (TRWI-13 proposal) -- see
    ``_build_contacts_formset`` for the ``extra=`` reasoning.
    """
    key_dates = report.key_dates.all()
    factory = modelformset_factory(ReportKeyDate, form=ReportKeyDateForm, can_delete=True, extra=1)
    kwargs = {"queryset": key_dates, "prefix": "key_dates"}
    if data is not None:
        kwargs["data"] = data
    return factory(**kwargs)


def _save_child_formset(formset, **extra_fields):
    """Save a ``modelformset_factory`` formset whose model needs a parent FK
    set after the fact (mirrors ``objectives.views.ObjectiveDetailView``'s
    own ``actions_form_valid``/``notes.views.ChapterNoteDetailView``'s
    ``subnotes_form_valid`` -- the established pattern in this codebase for
    exactly this "child rows of a parent, added/edited/deleted in one
    formset" shape). Caller must have already checked ``formset.is_valid()``.
    """
    instances = formset.save(commit=False)
    for instance in instances:
        for field, value in extra_fields.items():
            setattr(instance, field, value)
        instance.save()
    formset.save()


class StartReportView(LoginRequiredMixin, View):
    """POST-only: start the viewer's Transition Report for a position they
    currently hold, before ``generate_transition_obligations`` has assigned it.

    Creates the same obligation the daily command would (see
    ``services.start_report_early``), then sends them to compose it. They
    can save a draft and come back as often as they like; reminders follow
    the due date and run until the report is submitted.
    """

    def post(self, request, role_change_pk):
        obligation = services.start_report_early(request.user, role_change_pk)
        if obligation is None:
            messages.error(request, "You can't start a Transition Report for that position.")
            return redirect("transitions:list")
        return redirect("transitions:compose", pk=obligation.public_id)


class ComposeReportView(LoginRequiredMixin, View):
    """Compose/edit/submit the report for one obligation.

    Only the obligation's own assigned officer may compose it -- there is no
    "someone else fills it in for you" path. Author may edit indefinitely
    (decision F15): no lock, no grace window, and editing after submission
    does not change ``status`` back to draft.
    """

    template_name = "transitions/compose_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.obligation = get_object_or_404(ReportObligation, public_id=kwargs["pk"])
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
        return self._render(
            request,
            report,
            form,
            contacts_formset=_build_contacts_formset(report),
            key_dates_formset=_build_key_dates_formset(report),
        )

    def post(self, request, *args, **kwargs):
        report = services.get_or_create_report(self.obligation)
        action = request.POST.get("action")
        if action == "add_attachment":
            return self._handle_attachment(request, report)

        submitting = action == "submit"
        form = ComposeReportForm(request.POST, template=report.template, submitting=submitting)
        contacts_formset = _build_contacts_formset(report, data=request.POST)
        key_dates_formset = _build_key_dates_formset(report, data=request.POST)
        if form.is_valid() and contacts_formset.is_valid() and key_dates_formset.is_valid():
            _save_child_formset(contacts_formset, report=report)
            _save_child_formset(key_dates_formset, report=report)
            if submitting:
                services.submit_report(report, form.answers_data())
                services.set_manual_tags(report, form.manual_tags_data())
                messages.success(request, "Transition Report submitted. Thank you!")
                return redirect("transitions:list")
            services.save_draft(report, form.answers_data())
            services.set_manual_tags(report, form.manual_tags_data())
            messages.success(request, "Draft saved.")
            return redirect("transitions:compose", pk=self.obligation.public_id)
        return self._render(
            request, report, form, contacts_formset=contacts_formset, key_dates_formset=key_dates_formset
        )

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
        return redirect("transitions:compose", pk=self.obligation.public_id)

    def _render(self, request, report, form, contacts_formset=None, key_dates_formset=None):
        prior_answers = services.get_prior_answers(request.user, report)
        return render(
            request,
            self.template_name,
            {
                "obligation": self.obligation,
                "report": report,
                "form": form,
                "fields_with_prior_answers": form.fields_with_prior_answers(prior_answers),
                "attachment_form": ReportAttachmentForm(),
                "contacts_formset": contacts_formset,
                "key_dates_formset": key_dates_formset,
            },
        )


class AttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        attachment = get_object_or_404(ReportAttachment, public_id=pk)
        if request.user != attachment.report.author:
            messages.error(request, "Only the report's author may remove an attachment.")
        else:
            attachment.file.delete(save=False)
            attachment.delete()
            messages.success(request, "Attachment removed.")
        return redirect("transitions:compose", pk=attachment.report.obligation.public_id)


class TransitionTagAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete for :class:`TransitionTag` (the compose form's
    "Additional tags" field, 2026-09 UI change).

    Any signed-in member may search existing tags or type a new one to add
    it, so the vocabulary grows with use -- mirrors
    ``jobs.views.VocabularyAutocomplete``/``users.views.PositionAutocomplete``.
    """

    max_name_length = 50

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return TransitionTag.objects.none()
        qs = TransitionTag.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")

    def has_add_permission(self, request):
        # DAL's default requires the add_transitiontag model permission,
        # which no CMT role grants, so the "Create" option would never appear.
        if self.create_field is None:
            return False
        return bool(request.user.is_authenticated)

    def validate(self, text):
        name = " ".join((text or "").split())
        if not name:
            raise ValidationError({self.create_field: ["Enter a tag before adding it."]})
        if len(name) > self.max_name_length:
            raise ValidationError({self.create_field: [f"Keep this to {self.max_name_length} characters or fewer."]})

    def create_object(self, text):
        name = " ".join((text or "").split())
        # get_queryset() is search-scoped, so use the manager to avoid
        # inserting a duplicate row for a tag that already exists.
        existing = TransitionTag.objects.filter(name__iexact=name).first()
        return existing or TransitionTag.objects.create(name=name)


class CloseNAVacantView(LoginRequiredMixin, View):
    """Regent/RD-only path that closes an obligation WITHOUT a report."""

    def post(self, request, pk):
        obligation = get_object_or_404(ReportObligation, public_id=pk)
        if not services.can_close_na_vacant(request.user, obligation):
            messages.error(request, "Only the chapter Regent or a Regional Director can close this as vacant.")
        else:
            services.close_as_na_vacant(obligation)
            messages.success(request, "Closed as vacant -- no report required.")
        return redirect("transitions:list")


class HandoffPacketView(LoginRequiredMixin, TemplateView):
    """ALL reports the viewer may read for one position/chapter (TRWI-7),
    reverse-chronological -- permanently reachable, not a one-time
    notification. Access is whatever ``services.get_readable_reports``
    already allows (successor/Regent/RD/national/admin); an unentitled
    viewer simply sees an empty packet, the same "the queryset IS the
    security boundary" approach as ``TransitionsListView``.
    """

    template_name = "transitions/handoff_packet.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = get_object_or_404(Chapter, pk=kwargs["chapter_pk"])
        position_key = kwargs["position_key"]
        reports = list(services.get_handoff_packet(self.request.user, chapter, position_key))
        acknowledged_ids = set(
            self.request.user.transition_report_acknowledgements.filter(report__in=reports).values_list(
                "report_id", flat=True
            )
        )
        context["chapter"] = chapter
        context["position_key"] = position_key
        context["reports"] = reports
        context["acknowledged_report_ids"] = acknowledged_ids
        return context


class AcknowledgeReportView(LoginRequiredMixin, View):
    """Records "I've read this" for one report (TRWI-7). Requires read
    access to the report itself -- the packet view already only ever shows
    readable reports, but this is checked again here too since it is its
    own POST endpoint.
    """

    def post(self, request, pk):
        report = get_object_or_404(TransitionReport, public_id=pk)
        if not services.can_read_report(request.user, report):
            messages.error(request, "You are not able to acknowledge this report.")
        else:
            services.acknowledge_report(report, request.user)
            messages.success(request, "Marked as read.")
        return redirect("transitions:packet", chapter_pk=report.chapter_id, position_key=report.position_key)


def _default_cycle(request):
    """``request.GET`` with ``cycle=current`` injected when absent (TRWI-9) --
    mirrors ``forms.views.DefaultCurrentPeriodMixin``'s exact pattern so an
    unfiltered initial load defaults to the current cycle.
    """
    request_get = request.GET.copy()
    if not request_get.get("cancel") and "cycle" not in request_get:
        request_get["cycle"] = services.DEFAULT_CYCLE
    return request_get


def _default_search_cycle(request):
    """``request.GET`` with ``cycle=all`` injected when absent (TRWI-11) --
    search's own default is "All time", not "current" (see
    ``filters.SearchFilter``'s docstring for why), so this mirrors
    ``_default_cycle`` with a different default rather than reusing it.
    """
    request_get = request.GET.copy()
    if not request_get.get("cancel") and "cycle" not in request_get:
        request_get["cycle"] = "all"
    return request_get


def _search_context(request, chapter=None):
    """Search/browse section (TRWI-11, merged with the chapter obligation
    table 2026-09) -- every report the viewer may read, filterable by query
    text/position/tag/cycle (plus chapter/region for RD/National
    Officer/Admin), each linking out to the report itself. When ``chapter``
    narrows to one specific chapter (the viewer's own, or an explicit one
    for RD/National Officer/Admin), the SAME table also carries that
    chapter's other obligations with no readable report yet (TRWI-9) -- see
    ``services.get_report_rows``, which does the actual row-building. A
    national-scoped viewer's OWN chapter/region filter picks take priority
    over the ``chapter`` passed in, so picking a different chapter there
    switches which chapter's full picture is shown.
    """
    user = request.user
    is_national = user.is_admin or user.is_national_officer_group
    filter_class = NationalSearchFilter if is_national else SearchFilter

    filterset = filter_class(_default_search_cycle(request), queryset=TransitionReport.objects.none())
    filterset.request = request
    filterset.form.helper = SearchFilterFormHelper(form=filterset.form)
    filterset.form.is_valid()

    cleaned = filterset.form.cleaned_data
    query = cleaned.get("q") or ""
    position_key = cleaned.get("position_key") or ""
    filter_chapter = cleaned.get("chapter") if is_national else None
    region = cleaned.get("region") if is_national else None
    tag = cleaned.get("tag") or ""
    cycle = cleaned.get("cycle") or "all"
    scoped_chapter = filter_chapter or chapter

    rows = services.get_report_rows(
        user, query=query, position_key=position_key, chapter=scoped_chapter, region=region, tag=tag, cycle=cycle
    )
    table = ReportRowTable(data=rows)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)

    return {
        "filter": filterset,
        "table": table,
        "cycle_label": services.cycle_label(cycle) if cycle != "all" else "All time",
        "chapter": scoped_chapter,
    }


class ReportSearchView(LoginRequiredMixin, TemplateView):
    """An explicit OTHER chapter's obligations + search (RD/
    National Officer/Admin only), reached via ``transitions:chapter-dashboard``.

    The viewer's OWN combined table now lives inline on ``transitions:list``
    (2026-09 second merge) -- this view no longer resolves ``request.user``'s
    own chapter itself, so ``transitions:search`` (no ``chapter_pk``) simply
    redirects there; that URL is kept resolvable only so an old link/bookmark
    doesn't 404, not because it has any content of its own anymore.
    """

    template_name = "transitions/search.html"

    def dispatch(self, request, *args, **kwargs):
        chapter_pk = kwargs.get("chapter_pk")
        if chapter_pk is None:
            return redirect("transitions:list")
        self.chapter = get_object_or_404(Chapter, pk=chapter_pk)
        if not services.can_view_chapter_dashboard(request.user, self.chapter):
            messages.error(request, "You are not able to view this chapter's dashboard.")
            return redirect("transitions:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_search_context(self.request, chapter=self.chapter))
        return context


class ComplianceRatesView(LoginRequiredMixin, TemplateView):
    """Submission/acknowledgment rates by chapter (TRWI-9 regional/national
    view) -- one row per chapter, filterable by position/cycle (and, for
    National Officers/Admins only, region). RD/CCD see only their own
    ``director_regions``' chapters; National Officer/Admin see every active
    chapter.

    Not a ``PagedFilteredTableView``: its rows are post-aggregation
    ``services.ChapterComplianceStats`` dataclasses, not a plain queryset,
    so the filter is applied to the underlying obligations BEFORE
    ``services.get_chapter_compliance_stats`` aggregates them, then a
    ``django_tables2`` table wraps the resulting list directly.
    """

    template_name = "transitions/rates_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not services.can_view_compliance_rates(request.user):
            messages.error(request, "You are not able to view the completion rates dashboard.")
            return redirect("transitions:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_national = user.is_admin or user.is_national_officer_group
        filter_class = NationalComplianceRateFilter if is_national else ComplianceRateFilter

        filterset = filter_class(_default_cycle(self.request), queryset=ReportObligation.objects.none())
        filterset.request = self.request
        filterset.form.helper = ComplianceRateFilterFormHelper(form=filterset.form)
        filterset.form.is_valid()

        position_key = filterset.form.cleaned_data.get("position_key") or ""
        region = filterset.form.cleaned_data.get("region") if is_national else None
        cycle = filterset.form.cleaned_data.get("cycle") or services.DEFAULT_CYCLE

        chapters = services.get_compliance_rate_chapters(user, region=region)
        stats = services.get_chapter_compliance_stats(chapters, cycle=cycle, position_key=position_key)
        table = ChapterRateTable(data=stats)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)

        context["filter"] = filterset
        context["table"] = table
        context["cycle_label"] = services.cycle_label(cycle)
        context["is_national"] = is_national
        return context


class TrendView(LoginRequiredMixin, TemplateView):
    """National tag-trend view (TRWI-11): tag frequency across every
    submitted report, plus which active chapters have submitted nothing yet
    -- National Officer/Admin only (``services.can_view_trends``).
    """

    template_name = "transitions/trends.html"

    def dispatch(self, request, *args, **kwargs):
        if not services.can_view_trends(request.user):
            messages.error(request, "You are not able to view the transition report trends.")
            return redirect("transitions:list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filterset = TrendFilter(_default_cycle(self.request), queryset=TransitionReport.objects.none())
        filterset.request = self.request
        filterset.form.helper = TrendFilterFormHelper(form=filterset.form)
        filterset.form.is_valid()

        position_key = filterset.form.cleaned_data.get("position_key") or ""
        region = filterset.form.cleaned_data.get("region")
        cycle = filterset.form.cleaned_data.get("cycle") or services.DEFAULT_CYCLE

        tag_frequency = services.get_tag_frequency(cycle=cycle, position_key=position_key, region=region)
        table = TagFrequencyTable(data=tag_frequency)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)

        context["filter"] = filterset
        context["table"] = table
        context["cycle_label"] = services.cycle_label(cycle)
        context["chapters_with_no_submissions"] = services.get_chapters_with_no_submissions(
            cycle=cycle, position_key=position_key, region=region
        )
        return context
