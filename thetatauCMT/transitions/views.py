"""TRWI-5: compose/submit views. Plain CreateView-style logic + services.py,
matching notes/objectives -- no viewflow (this feature has no approval step).
"""

from dal import autocomplete
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.forms.models import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from core.views import LoginRequiredMixin, RequestConfig
from thetatauCMT.chapters.models import Chapter

from . import services
from .filters import (
    ComplianceRateFilter,
    NationalComplianceRateFilter,
    NationalSearchFilter,
    ObligationComplianceFilter,
    SearchFilter,
    TrendFilter,
)
from .forms import (
    ComplianceFilterFormHelper,
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
    ReportAcknowledgement,
    ReportAttachment,
    ReportContact,
    ReportKeyDate,
    ReportObligation,
    TransitionReport,
    TransitionTag,
)
from .tables import ChapterRateTable, ObligationComplianceTable, SearchResultsTable, TagFrequencyTable


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
        context["my_packets"] = [
            {"position_key": position_key, "chapter": user.chapter}
            for position_key in sorted(set(user.current_roles or []) & set(POSITION_KEY_TO_TYPE))
        ]
        context["show_rates_dashboard_link"] = services.can_view_compliance_rates(user)
        context["show_trends_link"] = services.can_view_trends(user)
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


def _default_dashboard_cycle(request):
    """``request.GET`` with ``obl_cycle=current`` injected when absent --
    mirrors ``_default_cycle`` but for the merged dashboard+search page's own
    ``obl_``-prefixed cycle field (see ``ObligationComplianceFilter``),
    which must not collide with the search section's own bare ``cycle``.
    """
    request_get = request.GET.copy()
    if not request_get.get("cancel") and "obl_cycle" not in request_get:
        request_get["obl_cycle"] = services.DEFAULT_CYCLE
    return request_get


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
            messages.error(request, "You are not able to view the compliance rates dashboard.")
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


class ReportSearchView(LoginRequiredMixin, TemplateView):
    """Combined chapter obligation dashboard + full-text/filtered report
    search (TRWI-9's dashboard and TRWI-11's search were merged into one
    page in a 2026-09 UI pass -- "My chapter dashboard" and "Search reports"
    were two separate pages that looked near-identical and, for a chapter
    officer, covered mostly the same chapter's data).

    Reachable two ways, both routed here (see ``urls.py``):
    - ``transitions:search`` (no ``chapter_pk``): the one link shown to
      everyone from the Transitions list. The dashboard section shows for
      ``request.user.chapter`` only if the viewer can see it
      (``services.can_view_chapter_dashboard``) and is silently omitted
      otherwise (e.g. a plain member) -- this URL must never itself deny
      access, since it is everyone's entry point.
    - ``transitions:chapter-dashboard`` (explicit ``chapter_pk``): the same
      page for a chapter the viewer does not necessarily belong to (RD/
      National Officer/Admin) -- denies with a redirect + message if the
      viewer can't see THAT chapter, matching the original
      ``ChapterComplianceView``'s own gate. No UI links here with an
      explicit ``chapter_pk`` other than the viewer's own; kept for direct
      navigation and the access-control tests.

    The search section (position/tag/cycle/q, plus chapter/region for RD/
    National Officer/Admin) is unchanged: ``services.search_reports``
    already does its own filtering AND its own access control in one place,
    so its filterset is only ever bound to a throwaway/empty queryset to
    clean/render GET params, never used to actually filter a real queryset.

    The dashboard section's own filter fields are prefixed ``obl_`` (see
    ``ObligationComplianceFilter``) so its GET params never collide with the
    search filter's -- ``_partials/collapsible_filter.html`` renders each as
    its own independent ``<form method="get">`` on this same page.
    """

    template_name = "transitions/search.html"

    def dispatch(self, request, *args, **kwargs):
        self.chapter = None
        chapter_pk = kwargs.get("chapter_pk")
        if chapter_pk is not None:
            chapter = get_object_or_404(Chapter, pk=chapter_pk)
            if not services.can_view_chapter_dashboard(request.user, chapter):
                messages.error(request, "You are not able to view this chapter's dashboard.")
                return redirect("transitions:list")
            self.chapter = chapter
        elif request.user.is_authenticated and request.user.chapter_id:
            if services.can_view_chapter_dashboard(request.user, request.user.chapter):
                self.chapter = request.user.chapter
        return super().dispatch(request, *args, **kwargs)

    def _dashboard_context(self):
        base_qs = (
            ReportObligation.objects.filter(chapter=self.chapter)
            .select_related("officer", "report")
            .annotate(acknowledged=Exists(ReportAcknowledgement.objects.filter(report__obligation_id=OuterRef("pk"))))
        )
        filterset = ObligationComplianceFilter(_default_dashboard_cycle(self.request), queryset=base_qs)
        filterset.request = self.request
        filterset.form.helper = ComplianceFilterFormHelper(form=filterset.form)
        # prefix="obl_": this table paginates/sorts independently of the
        # search table below it on the same page -- without it both would
        # read/write the same ?page=/?sort= GET params (django_tables2's
        # own fix for two tables on one page).
        table = ObligationComplianceTable(data=filterset.qs, prefix="obl_")
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)
        return {
            "chapter": self.chapter,
            "compliance_filter": filterset,
            "compliance_table": table,
            "compliance_cycle_label": services.cycle_label(self.request.GET.get("obl_cycle", services.DEFAULT_CYCLE)),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_national = user.is_admin or user.is_national_officer_group
        filter_class = NationalSearchFilter if is_national else SearchFilter

        filterset = filter_class(_default_search_cycle(self.request), queryset=TransitionReport.objects.none())
        filterset.request = self.request
        filterset.form.helper = SearchFilterFormHelper(form=filterset.form)
        filterset.form.is_valid()

        cleaned = filterset.form.cleaned_data
        query = cleaned.get("q") or ""
        position_key = cleaned.get("position_key") or ""
        chapter = cleaned.get("chapter") if is_national else None
        region = cleaned.get("region") if is_national else None
        tag = cleaned.get("tag") or ""
        cycle = cleaned.get("cycle") or "all"

        reports = services.search_reports(
            user, query=query, position_key=position_key, chapter=chapter, region=region, tag=tag, cycle=cycle
        )
        table = SearchResultsTable(data=reports)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)

        context["filter"] = filterset
        context["table"] = table
        context["cycle_label"] = services.cycle_label(cycle) if cycle != "all" else "All time"

        if self.chapter is not None:
            context.update(self._dashboard_context())
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
