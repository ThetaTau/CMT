import logging

from dal import autocomplete
from django.contrib import messages
from django.db import transaction
from django.db.utils import IntegrityError
from django.forms.models import modelformset_factory
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DetailView, ListView, RedirectView, UpdateView, View

from core.forms import MultiFormsView
from core.models import user_is_national_officer
from core.views import LoginRequiredMixin, NatOfficerRequiredMixin, PagedFilteredTableView, TypeFieldFilteredChapterAdd
from thetatauCMT.scores.models import ScoreType

from .filters import EventListFilter
from .forms import EventForm, EventListFormHelper, PictureForm
from .models import Event, Picture
from .tables import EventTable


def _safe_next(request, default):
    """Return a safe same-host redirect target from ``next``, else ``default``."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return default


def apply_event_workflow_fields(event, user, recompute_approval=True):
    """Apply the national / public / approval rules to an event before saving.

    Shared by the create and update views so both surfaces behave identically.

    - National events (only National Officers may set the flag) are org-wide:
      not tied to a chapter, always public, and auto-approved.
    - Otherwise the event belongs to the acting user's current chapter, its
      region defaults from that chapter, and (when ``recompute_approval``) the
      approval status is derived from the public flag and the creator's role.
    """
    acting_is_natoff = user_is_national_officer(user)
    if event.is_national and acting_is_natoff:
        event.is_public = True
        event.chapter = None
        event.approval_status = Event.ApprovalStatus.APPROVED
        if event.reviewed_by_id is None:
            event.reviewed_by = user
            event.reviewed_at = timezone.now()
        return
    # Defense in depth: non-national-officers can never create national events.
    event.is_national = False
    if event.chapter_id is None and event.parent_event_id is None:
        event.chapter = user.current_chapter
    if event.region_id is None and event.parent_event_id is None and event.chapter_id:
        event.region = event.chapter.region
    if recompute_approval:
        event.approval_status = Event.default_approval_status(
            is_public=event.is_public,
            created_by_national_officer=acting_is_natoff,
        )
        if (
            acting_is_natoff
            and event.is_public
            and event.approval_status == Event.ApprovalStatus.APPROVED
            and event.reviewed_by_id is None
        ):
            event.reviewed_by = user
            event.reviewed_at = timezone.now()


class EventAutocomplete(autocomplete.Select2QuerySetView):
    """Type-to-search lookup for ``Event.parent_event``.

    Officer-gated. The searchable scope depends on the forwarded ``is_national``
    flag of the event being created/edited: national events look up other
    national events (they are not tied to a chapter), while chapter events look
    up only their own chapter's events. The event being edited is excluded via
    the forwarded ``self_pk``.
    """

    def _is_authorized(self):
        user = self.request.user
        return user.is_authenticated and (user.is_officer_group or user.is_superuser)

    def get_queryset(self):
        if not self._is_authorized():
            return Event.objects.none()
        is_national = self.forwarded.get("is_national")
        is_national = is_national in (True, "true", "True", "on", "1", 1)
        if is_national:
            qs = Event.objects.national()
        else:
            chapter = self.request.user.current_chapter
            qs = Event.objects.filter(chapter=chapter)
        self_pk = self.forwarded.get("self_pk")
        if self_pk:
            qs = qs.exclude(pk=self_pk)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.select_related("chapter", "type").order_by("-date")


class NationalOfficerRequiredMixin(LoginRequiredMixin):
    """Restrict a view to National Officers / Admins.

    A user qualifies as a National Officer through any existing mechanism
    (superuser/Admin, the ``natoff`` group, or a current national-officer role),
    as determined by :func:`~core.models.user_is_national_officer`.
    Authenticated users who do not qualify are redirected home with an error;
    unauthenticated users are sent to login by ``LoginRequiredMixin``.
    """

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user_is_national_officer(user):
            messages.add_message(request, messages.ERROR, "Only National Officers can access this.")
            return HttpResponseRedirect(reverse("home"))
        return super().dispatch(request, *args, **kwargs)


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event

    def get_object(self, queryset=None):
        # The detail URL is date + slug based and slug is not unique, so more
        # than one event can match; return the earliest to stay deterministic.
        obj = (
            Event.objects.filter(
                date__year=self.kwargs["year"],
                date__month=self.kwargs["month"],
                date__day=self.kwargs["day"],
                slug=self.kwargs["slug"],
            )
            .order_by("pk")
            .first()
        )
        if obj is None:
            raise Http404("No event matches the given query.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sub_events"] = self.object.sub_events.select_related("chapter", "type").order_by("-date")
        # National Officers can review (approve/reject) a pending public event
        # directly from its detail page.
        context["can_review"] = bool(user_is_national_officer(self.request.user) and self.object.is_pending)
        # Attendance records for the attendance table on the detail page.
        context["attendance_records"] = self.object.attendance_records.select_related(
            "user", "chapter", "recorded_by"
        ).order_by("user__first_name", "user__last_name")
        return context


class EventCreateView(
    LoginRequiredMixin,
    CreateView,
    MultiFormsView,
):
    model = Event
    template_name = "events/event_create_form.html"
    officer_edit = "events"
    officer_edit_type = "create"
    score_type = "Evt"
    form_classes = {
        "event": EventForm,
        "picture": PictureForm,
    }
    fields = [
        "name",
        "date",
        "type",
        "description",
        "members",
        "pledges",
        "alumni",
        "guests",
        "duration",
        "stem",
        "host",
        "miles",
        "raised",
        "virtual",
    ]
    grouped_forms = {"eventpage": ["event", "picture"]}

    def get_success_url(self):
        return reverse("events:list")

    def get_event_kwargs(self):
        """Inject the acting user so the event form can gate the national flag."""
        return {"request_user": self.request.user}

    def _group_exists(self, group_name):
        return False

    def forms_valid(self, forms):
        event_form = forms["event"]
        picture_forms = forms["picture"]
        user = self.request.user
        event = event_form.instance
        event._acting_user = user
        # Apply the national / public / approval workflow rules (sets chapter,
        # region, is_public, approval_status, reviewer as appropriate).
        apply_event_workflow_fields(event, user, recompute_approval=True)
        try:
            with transaction.atomic():
                event_form.save()
        except IntegrityError:
            message = "Name and date together must be unique. You can have the same name on different date."
            messages.add_message(self.request, messages.ERROR, message)
            event_form.add_error("name", message)
            event_form.add_error("date", message)
            forms["event"] = event_form
            return self.render_to_response(self.get_context_data(forms=forms))
        for picture_form in picture_forms:
            if picture_form.is_valid() and picture_form.instance.image.name != "":
                picture_form.instance.event = event_form.instance
                picture_form.save()
        # "Save & Add Attendance" jumps straight to the new event's roster.
        if self.request.POST.get("add_attendance"):
            return HttpResponseRedirect(event.get_attendance_url())
        return HttpResponseRedirect(self.get_success_url())

    def create_picture_form(self, **kwargs):
        factory = modelformset_factory(Picture, form=PictureForm, **{"can_delete": True, "extra": 1})
        formset_kwargs = dict(queryset=Picture.objects.none())
        if self.request.method in ("POST", "PUT"):
            formset_kwargs.update({"data": self.request.POST.copy(), "files": self.request.FILES.copy()})
        return factory(**formset_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        descriptions = (
            ScoreType.objects.filter(type=self.score_type)
            .all()
            .values("id", "description", "formula", "points", "slug")
        )
        logging.debug(f"context {context}")
        form = context["forms"]["event"]
        slug = self.kwargs.get("slug")
        if slug:
            score_obj = ScoreType.objects.filter(slug=slug)
            form.initial = {"type": score_obj[0].pk}
            form.fields["type"].queryset = score_obj
        else:
            form.fields["type"].queryset = ScoreType.objects.filter(type=self.score_type).all()
        # return form
        context["descriptions"] = descriptions
        return context


class EventCopyView(EventCreateView):
    fields = [
        "name",
        "date",
        "type",
        "description",
        "members",
        "pledges",
        "alumni",
        "guests",
        "duration",
        "stem",
        "host",
        "miles",
        "raised",
        "virtual",
    ]

    def get_event_initial(self):
        event = Event.objects.get(pk=self.kwargs["pk"])
        self.initial = {
            "name": event.name,
            "date": event.date,
            "type": event.type,
            "description": event.description,
            "members": event.members,
            "pledges": event.pledges,
            "alumni": event.alumni,
            "guests": event.guests,
            "duration": event.duration,
            "stem": event.stem,
            "host": event.host,
            "miles": event.miles,
            "raised": event.raised,
            "virtual": event.virtual,
        }
        return self.initial


class EventRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("events:list")


class EventUpdateView(
    LoginRequiredMixin,
    TypeFieldFilteredChapterAdd,
    UpdateView,
):
    officer_edit = "events"
    officer_edit_type = "edit"
    form_class = EventForm
    model = Event

    def get_object(self, queryset=None):
        # Match the detail view's non-enumerable date + slug lookup.
        obj = (
            Event.objects.filter(
                date__year=self.kwargs["year"],
                date__month=self.kwargs["month"],
                date__day=self.kwargs["day"],
                slug=self.kwargs["event_slug"],
            )
            .order_by("pk")
            .first()
        )
        if obj is None:
            raise Http404("No event matches the given query.")
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sub_events"] = self.object.sub_events.select_related("chapter", "type").order_by("-date")
        return context

    def form_valid(self, form):
        event = form.instance
        event._acting_user = self.request.user
        # Only recompute approval when the public/national flags actually change,
        # so unrelated edits do not knock an approved event back to pending.
        recompute = bool({"is_public", "is_national"} & set(form.changed_data))
        apply_event_workflow_fields(event, self.request.user, recompute_approval=recompute)
        try:
            with transaction.atomic():
                self.object = form.save()
        except IntegrityError:
            message = (
                "Name, date, and type together must be unique. "
                "You can have the same name on different dates or a different type."
            )
            messages.add_message(self.request, messages.ERROR, message)
            form.add_error("name", message)
            form.add_error("date", message)
            return self.render_to_response(self.get_context_data(form=form))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("events:list")


class EventListView(LoginRequiredMixin, PagedFilteredTableView):
    # These next two lines tell the view to index lookups by username
    model = Event
    slug_field = "chapter"
    slug_url_kwarg = "chapter"
    context_object_name = "event"
    ordering = ["-date"]
    table_class = EventTable
    filter_class = EventListFilter
    formhelper_class = EventListFormHelper
    filter_chapter = True


class EventListAllView(EventListView, NatOfficerRequiredMixin):
    filter_chapter = False
    template_name = "events/event_list_all.html"

    def get_table_kwargs(self):
        return {"natoff": True}

    def get_filter_kwargs(self):
        return {"natoff": True}

    def get_filter_helper_kwargs(self):
        return {"natoff": True}


class EventPendingListView(NationalOfficerRequiredMixin, ListView):
    """List public events awaiting National Officer approval (natoff only)."""

    model = Event
    template_name = "events/event_pending_list.html"
    context_object_name = "events"
    paginate_by = 50

    def get_queryset(self):
        return (
            Event.objects.public()
            .pending()
            .select_related("chapter", "chapter__region", "type", "created_by")
            .order_by("-date")
        )


class EventApproveView(NationalOfficerRequiredMixin, View):
    """Approve a pending public event (natoff only). POST only."""

    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Event, pk=kwargs["pk"])
        event.approve(reviewer=request.user)
        messages.add_message(
            request,
            messages.SUCCESS,
            f"Approved public event '{event.name}'. It is now visible to all chapters.",
        )
        return HttpResponseRedirect(_safe_next(request, reverse("events:pending")))


class EventRejectView(NationalOfficerRequiredMixin, View):
    """Reject a pending public event with an optional reason (natoff only). POST only."""

    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Event, pk=kwargs["pk"])
        reason = (request.POST.get("rejection_reason") or "").strip()
        event.reject(reviewer=request.user, reason=reason)
        messages.add_message(
            request,
            messages.SUCCESS,
            f"Rejected public event '{event.name}'.",
        )
        return HttpResponseRedirect(_safe_next(request, reverse("events:pending")))
