from itertools import groupby

from dal import autocomplete
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, ListView
from django_tables2 import SingleTableView
from viewflow.flow.views import CreateProcessView, UpdateProcessView

from core.models import user_is_national_officer
from core.views import PagedFilteredTableView
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import User

from . import reports
from .certificates import generate_certificate, store_uploaded_artifact
from .eligibility import describe_eligibility, get_eligible_recipients
from .exports import grants_export_response
from .filters import AwardGrantFilter
from .forms import AwardDirectoryFilterHelper, AwardNominationForm, AwardNominationReviewForm, DirectGrantForm
from .importer import ingest_award_csv
from .models import AwardCycle, AwardGrant, AwardImportMatchQueueItem, AwardNominationProcess, AwardType, GrantArtifact
from .services import can_grant_awards, direct_grant, nominatable_award_types
from .tables import AwardGrantTable


class DirectGrantView(LoginRequiredMixin, FormView):
    """Officer-facing view to grant a direct award to an eligible recipient."""

    template_name = "awards/direct_grant_form.html"
    form_class = DirectGrantForm
    success_url = reverse_lazy("awards:direct_grant")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_grant_awards(request.user):
            messages.error(request, "Only officers can grant awards.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            grant = direct_grant(
                form.cleaned_data["award_type"],
                form.cleaned_data["cycle"],
                form.cleaned_data["recipient"],
                self.request.user,
                effective_date=form.cleaned_data.get("effective_date"),
                reason=form.cleaned_data.get("reason", ""),
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, f"Granted {grant.award_type} to {grant.recipient_display}.")
        return super().form_valid(form)


class AwardNominationCreateView(LoginRequiredMixin, CreateProcessView):
    """Start node: the role-scoped award nomination entry form.

    The submitting member is recorded as the ``nominator``; the nomination then
    parks awaiting review (the AWI-7 approval workflow).
    """

    template_name = "awards/award_nomination_form.html"
    model = AwardNominationProcess
    form_class = AwardNominationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_initial(self):
        # Pre-fill recipient / award / cycle from query params so the profile,
        # chapter, and award-page "Nominate" buttons land on a ready-to-submit form.
        initial = super().get_initial()
        for param in ("award_type", "cycle", "recipient_member", "recipient_chapter", "recipient_region"):
            value = self.request.GET.get(param)
            if value:
                initial[param] = value
        return initial

    def get_context_data(self, **kwargs):
        # Map each selectable award to its recipient kind so the template shows
        # only the matching recipient field (member / chapter / region), plus the
        # award's description / eligibility so the nominator sees what it is for.
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        if form is not None:
            awards = form.fields["award_type"].queryset.prefetch_related(
                "eligibility_rules__chapters", "eligibility_rules__regions"
            )
            context["award_kinds"] = {str(award.pk): award.recipient_kind for award in awards}
            context["award_details"] = {
                str(award.pk): {
                    "name": award.name,
                    "category": award.category,
                    "level": award.get_level_display(),
                    "description": award.description,
                    "eligibility": award.eligibility,
                    "eligibility_bullets": describe_eligibility(award),
                    "winners_url": reverse("awards:type_winners", args=[award.pk]),
                }
                for award in awards
            }
            context["catalog_url"] = reverse("awards:catalog")
        return context

    def form_valid(self, form, *args, **kwargs):
        form.instance.nominator = self.request.user
        return super().form_valid(form, *args, **kwargs)

    def get_success_url(self):
        return reverse("home")

    def activation_done(self, *args, **kwargs):
        self.activation.done()
        self.success("Your nomination has been submitted for review.")


class EligibleRecipientsView(LoginRequiredMixin, View):
    """JSON list of recipients eligible for an award, scoped to the requester.

    Powers the nomination form's dynamic recipient picker (AWI-4). Never returns
    recipients the requester is not authorized to nominate.
    """

    def get(self, request):
        award = AwardType.objects.filter(pk=request.GET.get("award_type")).first()
        if award is None:
            return JsonResponse({"kind": None, "results": []})
        cycle = AwardCycle.objects.filter(pk=request.GET.get("cycle")).first()
        recipients = get_eligible_recipients(award, cycle=cycle, actor=request.user)[:50]
        results = [{"id": obj.pk, "label": str(obj)} for obj in recipients]
        return JsonResponse({"kind": award.recipient_kind, "results": results})


class AwardRecipientMemberAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """Member picker for the nomination form, filtered by the selected award.

    Reuses the AWI-4 eligibility engine so that when the chosen award restricts
    recipients (e.g. an alumni-only award), only those members are offered --
    always within the requester's own scope. Returns nothing until a
    member-level award is selected (the matching field is hidden until then).
    """

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return User.objects.none()
        award = AwardType.objects.filter(pk=self.forwarded.get("award_type")).first()
        if award is None or award.recipient_kind != "member":
            return User.objects.none()
        cycle = AwardCycle.objects.filter(pk=self.forwarded.get("cycle")).first()
        qs = get_eligible_recipients(award, cycle=cycle, actor=self.request.user)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")


class AwardNominationReviewView(UpdateProcessView):
    """Reviewer approve / reject view (assigned to the config-driven approver).

    Records who / when reviewed before the activation advances to the grant /
    close handler.
    """

    form_class = AwardNominationReviewForm

    def form_valid(self, form, *args, **kwargs):
        form.instance.reviewed_by = self.request.user
        form.instance.reviewed_at = timezone.now()
        response = super().form_valid(form, *args, **kwargs)
        messages.success(
            self.request,
            f"Nomination review saved. The nomination was {form.instance.get_result_display().lower()}.",
        )
        return response

    def get_success_url(self):
        # The review task is assigned to a config-driven approver who may not be
        # a national officer. The viewflow default would redirect to the process
        # ``:detail`` page, which requires ``awards.view_awardnominationprocess``
        # (national officers/staff only) and 403s that approver. Send them home,
        # matching the safe landing used by the award nomination entry view.
        return reverse("home")


class GrantArtifactView(LoginRequiredMixin, View):
    """Manage certificates / letters for a grant: generate or upload (officers)."""

    template_name = "awards/grant_artifacts.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_grant_awards(request.user):
            messages.error(request, "Only officers can manage award certificates.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, grant_pk):
        grant = get_object_or_404(AwardGrant, pk=grant_pk)
        return render(request, self.template_name, {"grant": grant, "artifacts": grant.artifacts.all()})

    def post(self, request, grant_pk):
        grant = get_object_or_404(AwardGrant, pk=grant_pk)
        action = request.POST.get("action")
        if action == "generate":
            try:
                generate_certificate(grant, created_by=request.user)
                messages.success(request, "Certificate generated.")
            except Exception:
                messages.error(request, "Certificate generation failed.")
        elif action == "upload" and request.FILES.get("file"):
            store_uploaded_artifact(grant, request.FILES["file"], created_by=request.user)
            messages.success(request, "Certificate uploaded.")
        else:
            messages.error(request, "Choose a file to upload or generate a certificate.")
        return redirect("awards:grant_artifacts", grant_pk=grant.pk)


class GrantArtifactDownloadView(LoginRequiredMixin, View):
    """Download a stored certificate / letter (awards are public to members)."""

    def get(self, request, artifact_pk):
        artifact = get_object_or_404(GrantArtifact, pk=artifact_pk)
        filename = artifact.file.name.rsplit("/", 1)[-1]
        return FileResponse(artifact.file.open("rb"), as_attachment=True, filename=filename)


class AwardCatalogView(LoginRequiredMixin, ListView):
    """Catalog of every available award: description, eligibility, and rules.

    Each entry links to the winners of that award
    (:class:`AwardTypeWinnersView`). Retired awards are hidden unless
    ``?show_retired=1`` is passed by a National Officer / Admin. A ``?q=``
    search matches the name, description, eligibility, or category.
    """

    model = AwardType
    template_name = "awards/award_catalog.html"
    context_object_name = "award_types"

    def _show_retired(self):
        return user_is_national_officer(self.request.user) and self.request.GET.get("show_retired") in (
            "1",
            "true",
            "on",
            "yes",
        )

    def get_queryset(self):
        queryset = AwardType.objects.prefetch_related("eligibility_rules__chapters", "eligibility_rules__regions")
        if not self._show_retired():
            queryset = queryset.active()
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(eligibility__icontains=search)
                | Q(category__icontains=search)
            )
        level = self.request.GET.get("level", "").strip()
        if level:
            queryset = queryset.filter(level=level)
        return queryset.annotate(
            winner_count=Count("grants", filter=Q(grants__status=AwardGrant.Status.ACTIVE), distinct=True)
        ).order_by("category", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        award_types = list(context["award_types"])
        nominatable = set(nominatable_award_types(self.request.user).values_list("pk", flat=True))
        for award in award_types:
            award.eligibility_bullets = describe_eligibility(award)
            award.can_nominate = award.pk in nominatable
        # Group by category so the page reads like the printed awards manual.
        context["award_groups"] = [
            (category, list(awards)) for category, awards in groupby(award_types, key=lambda a: a.category)
        ]
        context["search"] = self.request.GET.get("q", "")
        context["level"] = self.request.GET.get("level", "")
        context["level_choices"] = AwardType.Level.choices
        context["can_view_retired"] = user_is_national_officer(self.request.user)
        context["show_retired"] = self._show_retired()
        context["nominate_url"] = reverse("viewflow:awards:awardnomination:start")
        return context


class AwardDirectoryView(LoginRequiredMixin, PagedFilteredTableView):
    """Filterable directory of award winners (AWI-11).

    Award data is visible to any signed-in member — it is not public. It lists
    *active* grants by default (revoked grants are excluded); passing
    ``?show_revoked=1`` includes revoked grants, which the table then labels with
    their status. Filter by award type, level, cycle, chapter, region, or a
    recipient search.
    """

    model = AwardGrant
    template_name = "awards/award_directory.html"
    table_class = AwardGrantTable
    filter_class = AwardGrantFilter
    formhelper_class = AwardDirectoryFilterHelper
    table_pagination = {"per_page": 50}

    def _can_view_revoked(self):
        # Revoked grants are only surfaced to National Officers / Admins.
        return user_is_national_officer(self.request.user)

    def _show_revoked(self):
        return self._can_view_revoked() and self.request.GET.get("show_revoked") in ("1", "true", "on", "yes")

    def get_base_queryset(self):
        qs = AwardGrant.objects.select_related(
            "award_type",
            "cycle",
            "recipient_member",
            "recipient_member__chapter",
            "recipient_member__chapter__region",
            "recipient_chapter",
            "recipient_chapter__region",
            "recipient_region",
        )
        if not self._show_revoked():
            qs = qs.active()
        return qs

    def get_queryset(self, **kwargs):
        self.queryset = self.get_base_queryset()
        return super().get_queryset(**kwargs)

    def get_table_kwargs(self):
        # The status column is only meaningful when revoked grants are shown.
        if self._show_revoked():
            return {}
        return {"exclude": ("status",)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_revoked"] = self._show_revoked()
        context["can_view_revoked"] = self._can_view_revoked()
        context["can_export"] = self.request.user.is_admin
        context["can_nominate"] = self.request.user.is_authenticated
        context["catalog_url"] = reverse("awards:catalog")
        context["nominate_url"] = reverse("viewflow:awards:awardnomination:start")
        return context


class AwardTypeWinnersView(AwardDirectoryView):
    """ "All winners of X" -- the public directory scoped to one award type."""

    def get_base_queryset(self):
        self.award_type = get_object_or_404(AwardType, pk=self.kwargs["pk"])
        return super().get_base_queryset().filter(award_type=self.award_type)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["award_type"] = self.award_type
        context["heading"] = f"Winners of {self.award_type}"
        context["eligibility_bullets"] = describe_eligibility(self.award_type)
        context["export_url"] = f"{reverse('awards:export')}?award_type={self.award_type.pk}"
        if self.award_type.grant_method == AwardType.GrantMethod.NOMINATION_WORKFLOW:
            context["nominate_url"] = (
                f"{reverse('viewflow:awards:awardnomination:start')}?award_type={self.award_type.pk}"
            )
            context["nominate_award_label"] = str(self.award_type)
        return context


class AwardCycleWinnersView(AwardDirectoryView):
    """ "Winners in cycle Y" -- the public directory scoped to one cycle."""

    def get_base_queryset(self):
        self.cycle = get_object_or_404(AwardCycle, pk=self.kwargs["pk"])
        return super().get_base_queryset().filter(cycle=self.cycle)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cycle"] = self.cycle
        context["heading"] = f"Winners in {self.cycle}"
        context["export_url"] = f"{reverse('awards:export')}?cycle={self.cycle.pk}"
        context["nominate_url"] = f"{reverse('viewflow:awards:awardnomination:start')}?cycle={self.cycle.pk}"
        return context


class AwardExportView(LoginRequiredMixin, View):
    """Administrator-gated CSV / Excel export of award grants (AWI-12).

    Award data is public to browse one page at a time, but a bulk export hands
    over the whole set at once, so it is restricted to superusers -- a tighter
    gate than the direct-grant and certificate tools. Officers use the winners
    directory and their own chapter history instead. A single GET parameter
    selects the report -- ``cycle`` (pk), ``chapter`` (slug), ``region`` (slug),
    ``award_type`` (pk), or ``member`` (username); none means "all grants".
    ``?format=xlsx`` returns an Excel workbook (CSV otherwise); ``?include_revoked=1``
    adds revoked grants.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_admin:
            messages.error(request, "Only administrators can export award reports.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        fmt = "xlsx" if request.GET.get("format") == "xlsx" else "csv"
        include_revoked = request.GET.get("include_revoked") in ("1", "true", "on", "yes")
        cycle_pk = request.GET.get("cycle")
        chapter_slug = request.GET.get("chapter")
        region_slug = request.GET.get("region")
        award_pk = request.GET.get("award_type")
        member_username = request.GET.get("member")
        if cycle_pk:
            cycle = get_object_or_404(AwardCycle, pk=cycle_pk)
            queryset = reports.awards_by_cycle(cycle, include_revoked=include_revoked)
            stem = f"awards_cycle_{cycle.pk}"
        elif chapter_slug:
            chapter = get_object_or_404(Chapter, slug=chapter_slug)
            queryset = reports.awards_by_chapter(chapter, include_revoked=include_revoked)
            stem = f"awards_chapter_{chapter.slug}"
        elif region_slug:
            region = get_object_or_404(Region, slug=region_slug)
            queryset = reports.awards_by_region(region, include_revoked=include_revoked)
            stem = f"awards_region_{region.slug}"
        elif award_pk:
            award = get_object_or_404(AwardType, pk=award_pk)
            queryset = reports.awards_by_award_type(award, include_revoked=include_revoked)
            stem = f"awards_type_{award.pk}"
        elif member_username:
            member = get_object_or_404(User, username=member_username)
            queryset = reports.member_award_history(member, include_revoked=include_revoked)
            stem = f"awards_member_{member.pk}"
        else:
            queryset = reports.all_grants(include_revoked=include_revoked)
            stem = "awards_all"
        return grants_export_response(queryset, fmt=fmt, filename_stem=stem)


class _AwardHistoryView(LoginRequiredMixin, SingleTableView):
    """Base for the chronological award-history views (AWI-12).

    Reuses :class:`~thetatauCMT.awards.tables.AwardGrantTable` (status column
    included so revoked grants are labeled). The queryset is ordered by
    ``effective_date`` so backdated grants sort into their historical place,
    though only the award period is displayed. Visible to any signed-in member,
    but export buttons are shown only to administrators.
    """

    template_name = "awards/award_history.html"
    table_class = AwardGrantTable
    table_pagination = {"per_page": 50}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_export"] = self.request.user.is_admin
        return context


class MemberAwardHistoryView(_AwardHistoryView):
    """A single member's full award history (chronological, includes revoked)."""

    def get_queryset(self):
        self.member = get_object_or_404(User, username=self.kwargs["username"])
        return reports.member_award_history(self.member, include_revoked=user_is_national_officer(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["member"] = self.member
        context["heading"] = f"Award history for {self.member}"
        context["export_url"] = f"{reverse('awards:export')}?member={self.member.username}"
        return context


class ChapterAwardHistoryView(_AwardHistoryView):
    """A chapter's full award history (the chapter's and its members')."""

    def get_queryset(self):
        self.chapter = get_object_or_404(Chapter, slug=self.kwargs["slug"])
        return reports.chapter_award_history(self.chapter, include_revoked=user_is_national_officer(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapter"] = self.chapter
        context["heading"] = f"Award history for {self.chapter}"
        context["export_url"] = f"{reverse('awards:export')}?chapter={self.chapter.slug}"
        return context


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to superusers only -- the AWI-13 legacy import tools.

    Legacy bulk import is a superuser-only activity (not national officers):
    superusers pass, other authenticated users are sent home with a message,
    and anonymous users are sent to login.
    """

    def test_func(self):
        return bool(getattr(self.request.user, "is_admin", False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Only superusers can import awards.")
            return redirect("home")
        return super().handle_no_permission()


class AwardImportUploadView(SuperuserRequiredMixin, View):
    """Superuser CSV upload for legacy award winners (AWI-13)."""

    template_name = "awards/import_upload.html"

    def get(self, request):
        context = {"pending_count": AwardImportMatchQueueItem.objects.filter(status="pending").count()}
        return render(request, self.template_name, context)

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, "Choose a CSV file to import.")
            return redirect("awards:import_upload")
        result = ingest_award_csv(upload.read(), request.user)
        messages.success(
            request,
            f"Import complete: {result.imported} imported, {result.duplicates} duplicate(s), "
            f"{result.queued} queued for review, {result.skipped} skipped.",
        )
        for error in result.errors[:20]:
            messages.warning(request, error)
        return redirect("awards:import_queue")


class AwardImportQueueListView(SuperuserRequiredMixin, View):
    """Review the pending low-confidence import rows and their candidates (AWI-13)."""

    template_name = "awards/import_queue.html"

    def get(self, request):
        items = (
            AwardImportMatchQueueItem.objects.filter(status=AwardImportMatchQueueItem.Status.PENDING)
            .select_related("award_type", "cycle")
            .order_by("-best_score", "raw_recipient")
        )
        context = {
            "items": items,
            "resolved_count": AwardImportMatchQueueItem.objects.filter(
                status=AwardImportMatchQueueItem.Status.RESOLVED
            ).count(),
            "skipped_count": AwardImportMatchQueueItem.objects.filter(
                status=AwardImportMatchQueueItem.Status.SKIPPED
            ).count(),
        }
        return render(request, self.template_name, context)


class AwardImportQueueResolveView(SuperuserRequiredMixin, View):
    """Manually resolve (confirm a recipient) or skip an import queue item (AWI-13)."""

    def post(self, request):
        item = get_object_or_404(AwardImportMatchQueueItem, pk=request.POST.get("item"))
        if not item.is_pending:
            messages.info(request, "That row was already resolved.")
            return self._redirect(request)
        if request.POST.get("action") == "skip":
            item.skip(request.user, note=request.POST.get("note", ""))
            messages.success(request, f"Skipped '{item.display_label}'.")
            return self._redirect(request)
        recipient = self._recipient(item, request.POST.get("recipient_id"))
        if recipient is None:
            messages.error(request, "Select a valid recipient to confirm the match.")
            return self._redirect(request)
        grant = item.resolve_to(recipient, request.user)
        messages.success(request, f"Imported {grant.award_type} for {grant.recipient_display}.")
        return self._redirect(request)

    @staticmethod
    def _recipient(item, recipient_id):
        if not recipient_id:
            return None
        model = {
            AwardImportMatchQueueItem.RecipientKind.MEMBER: User,
            AwardImportMatchQueueItem.RecipientKind.CHAPTER: Chapter,
            AwardImportMatchQueueItem.RecipientKind.REGION: Region,
        }.get(item.recipient_kind)
        return model.objects.filter(pk=recipient_id).first() if model is not None else None

    def _redirect(self, request):
        nxt = request.POST.get("next")
        if nxt and url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return HttpResponseRedirect(nxt)
        return HttpResponseRedirect(reverse("awards:import_queue"))
