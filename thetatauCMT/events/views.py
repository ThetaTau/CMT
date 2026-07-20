import logging

from dal import autocomplete
from django.contrib import messages
from django.db import transaction
from django.db.utils import IntegrityError
from django.forms.models import modelformset_factory
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DetailView, ListView, RedirectView, TemplateView, UpdateView, View

from core.forms import MultiFormsView
from core.models import user_is_national_officer
from core.views import (
    LoginRequiredMixin,
    NationalOfficerRequiredMixin,
    NatOfficerRequiredMixin,
    PagedFilteredTableView,
    TypeFieldFilteredChapterAdd,
)
from thetatauCMT.scores.models import ScoreType

from .filters import EventListFilter
from .forms import CalendarFeedSubscriptionForm, EventForm, EventListFormHelper, PictureForm, TaskFeedForm
from .models import CalendarFeedSubscription, Event, Picture, can_delete_event
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
        # WI-6 privacy: only officers who can record attendance for the event's
        # chapter (or National Officers / superusers) and members of the event's
        # own chapter may see the full attendance roster — never a cross-chapter
        # visitor discovering the event via the public calendar.
        from thetatauCMT.attendance.services import can_record_attendance, can_rsvp

        user = self.request.user
        same_chapter = bool(
            self.object.chapter_id and user.current_chapter and user.current_chapter.pk == self.object.chapter_id
        )
        context["can_view_attendance"] = bool(can_record_attendance(user, self.object) or same_chapter)
        # WI-10: a member may RSVP for an upcoming event they can see.
        context["can_rsvp"] = can_rsvp(user, self.object)
        my_record = self.object.attendance_records.filter(user=user).first()
        context["my_rsvp_status"] = my_record.status if my_record else ""
        # Chapter officers of this event's chapter may soft-delete it.
        context["can_delete"] = can_delete_event(user, self.object)
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
        context["can_delete"] = can_delete_event(self.request.user, self.object)
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


class EventDeleteView(LoginRequiredMixin, View):
    """Soft-delete an event.

    Restricted to chapter officers of the event's own chapter (National Officers
    and superusers may delete any event). A GET renders a confirmation page; the
    actual delete only happens on the confirming POST.
    """

    template_name = "events/event_confirm_delete.html"

    def _get_event(self):
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

    def dispatch(self, request, *args, **kwargs):
        # Let LoginRequiredMixin handle unauthenticated users first.
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.event = self._get_event()
        if not can_delete_event(request.user, self.event):
            messages.add_message(
                request,
                messages.ERROR,
                "Only officers of this event's chapter can delete it.",
            )
            return HttpResponseRedirect(self.event.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"event": self.event})

    def post(self, request, *args, **kwargs):
        name = self.event.name
        self.event.soft_delete(request.user)
        messages.add_message(request, messages.SUCCESS, f"Event '{name}' was deleted.")
        return HttpResponseRedirect(_safe_next(request, reverse("events:list")))


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # WI-10 — let members RSVP straight from the events table. Map each
        # event to the member's current status so the table can offer RSVP or
        # "Cancel RSVP" (matching the event detail page) as appropriate.
        from thetatauCMT.attendance.models import AttendanceRecord

        context["my_rsvp_status"] = dict(
            AttendanceRecord.objects.filter(user=self.request.user).values_list("event_id", "status")
        )
        return context


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


class EventCalendarView(LoginRequiredMixin, TemplateView):
    """Cross-chapter public events calendar with region/chapter filters.

    Displays events visible to the member's chapter — their own chapter's events
    plus approved cross-chapter public events (reuses the WI-2
    :meth:`~EventQuerySet.visible_to_chapter` logic). Public events that are
    still pending or rejected in another chapter are never shown. Renders a month
    grid (default) or a table (``?view=table``); no attendance roster is exposed
    (WI-6). Members can RSVP to upcoming events straight from the calendar.
    """

    template_name = "events/event_calendar.html"

    def get_context_data(self, **kwargs):
        import calendar as calendar_module
        import datetime

        from thetatauCMT.attendance.models import AttendanceRecord
        from thetatauCMT.attendance.services import can_rsvp
        from thetatauCMT.chapters.models import Chapter
        from thetatauCMT.regions.models import Region

        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()

        # Resolve the month being viewed (defaults to the current month).
        try:
            year, month = (int(part) for part in self.request.GET.get("month", "").split("-"))
            datetime.date(year, month, 1)
        except (ValueError, TypeError):
            year, month = today.year, today.month

        # Base visibility (WI-2) + region / chapter filters.
        events = Event.objects.visible_to_chapter(user.current_chapter).select_related(
            "chapter", "chapter__region", "type"
        )
        region_slug = self.request.GET.get("region", "") or ""
        chapter_slug = self.request.GET.get("chapter", "") or ""
        if region_slug and region_slug != "all":
            events = events.filter(chapter__region__slug=region_slug)
        if chapter_slug and chapter_slug != "all":
            events = events.filter(chapter__slug=chapter_slug)
        month_events = list(events.filter(date__year=year, date__month=month).order_by("date", "name"))

        # The member's own records for the shown events → RSVP state (own record
        # only; never another chapter's roster).
        my_records = {
            rec.event_id: rec
            for rec in AttendanceRecord.objects.filter(user=user, event_id__in=[event.pk for event in month_events])
        }
        for event in month_events:
            rec = my_records.get(event.pk)
            event.my_status = rec.status if rec else ""
            event.my_status_display = rec.get_status_display() if rec else ""
            event.member_can_rsvp = can_rsvp(user, event)

        # Build the month grid (Sunday-first) mapping events onto their dates.
        events_by_date = {}
        for event in month_events:
            events_by_date.setdefault(event.date, []).append(event)
        cal = calendar_module.Calendar(firstweekday=6)
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            weeks.append(
                [
                    {
                        "date": day,
                        "in_month": day.month == month,
                        "is_today": day == today,
                        "events": events_by_date.get(day, []),
                    }
                    for day in week
                ]
            )

        prev_month = (datetime.date(year, month, 1) - datetime.timedelta(days=1)).replace(day=1)
        next_month = (datetime.date(year, month, 28) + datetime.timedelta(days=7)).replace(day=1)

        context.update(
            {
                "view_mode": "table" if self.request.GET.get("view") == "table" else "calendar",
                "year": year,
                "month": month,
                "month_name": calendar_module.month_name[month],
                "weeks": weeks,
                "events": month_events,
                "regions": Region.objects.all().order_by("name"),
                "chapters": Chapter.objects.filter(active=True).order_by("name"),
                "selected_region": region_slug,
                "selected_chapter": chapter_slug,
                "today": today,
                "prev_month": f"{prev_month.year}-{prev_month.month:02d}",
                "next_month": f"{next_month.year}-{next_month.month:02d}",
                # Month / year jump selectors.
                "month_padded": f"{month:02d}",
                "month_choices": [(f"{i:02d}", calendar_module.month_name[i]) for i in range(1, 13)],
                "year_choices": list(range(today.year - 5, today.year + 6)),
                "STATUS": AttendanceRecord.STATUS,
            }
        )
        return context


# ===========================================================================
# iCal calendar feed subscriptions
# ===========================================================================


class ChapterFeedAutocomplete(autocomplete.Select2QuerySetView):
    """Type-to-search active chapters for the feed-subscription form."""

    def get_queryset(self):
        from thetatauCMT.chapters.models import Chapter

        if not self.request.user.is_authenticated:
            return Chapter.objects.none()
        qs = Chapter.objects.filter(active=True)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")


class RegionFeedAutocomplete(autocomplete.Select2QuerySetView):
    """Type-to-search regions for the feed-subscription form."""

    def get_queryset(self):
        from thetatauCMT.regions.models import Region

        if not self.request.user.is_authenticated:
            return Region.objects.none()
        qs = Region.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by("name")


def _feed_prefix(feed):
    """A per-feed form prefix so several edit forms can share one page."""
    return f"feed{feed.pk}"


class CalendarFeedListView(LoginRequiredMixin, View):
    """Manage the member's iCal subscriptions — add, edit, and remove feeds."""

    template_name = "events/calendar_feeds.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._context(request))

    def post(self, request, *args, **kwargs):
        """Create a brand-new feed."""
        form = CalendarFeedSubscriptionForm(request.POST, prefix="new")
        if form.is_valid():
            feed = form.save(commit=False)
            feed.user = request.user
            feed.save()
            form.save_m2m()
            messages.add_message(
                request,
                messages.SUCCESS,
                f"Created calendar feed '{feed.name}'. Subscribe using the URL below.",
            )
            return HttpResponseRedirect(f"{reverse('events:feeds')}#feed-{feed.pk}")
        return render(request, self.template_name, self._context(request, create_form=form))

    def _context(self, request, create_form=None, edit_forms=None, task_feed_form=None):
        edit_forms = edit_forms or {}
        feeds = request.user.calendar_feeds.prefetch_related("chapters", "regions")
        feed_forms = [
            (
                feed,
                edit_forms.get(
                    feed.pk,
                    CalendarFeedSubscriptionForm(instance=feed, prefix=_feed_prefix(feed)),
                ),
            )
            for feed in feeds
        ]
        return {
            "feed_forms": feed_forms,
            "create_form": create_form or CalendarFeedSubscriptionForm(prefix="new"),
            "task_feed_form": task_feed_form or TaskFeedForm(prefix="tasks"),
            "national_feed_path": reverse("events:ical_national"),
        }


class TaskFeedCreateView(LoginRequiredMixin, View):
    """Create a to-dos-only feed of the member's chapter tasks, optionally
    limited to specific officer roles."""

    def post(self, request, *args, **kwargs):
        form = TaskFeedForm(request.POST, prefix="tasks")
        if form.is_valid():
            feed = CalendarFeedSubscription.objects.create(
                user=request.user,
                name=form.cleaned_data["name"],
                include_national=False,
                include_todos=True,
                task_owner_roles=form.cleaned_data["task_owner_roles"],
            )
            messages.add_message(
                request,
                messages.SUCCESS,
                f"Created task feed '{feed.name}'. Subscribe using the URL below.",
            )
            return HttpResponseRedirect(f"{reverse('events:feeds')}#feed-{feed.pk}")
        return render(
            request,
            CalendarFeedListView.template_name,
            CalendarFeedListView()._context(request, task_feed_form=form),
        )


class CalendarFeedUpdateView(LoginRequiredMixin, View):
    """Edit one of the member's own feeds (add/remove chapters, regions, flags)."""

    def post(self, request, *args, **kwargs):
        feed = get_object_or_404(CalendarFeedSubscription, pk=kwargs["pk"], user=request.user)
        form = CalendarFeedSubscriptionForm(request.POST, instance=feed, prefix=_feed_prefix(feed))
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, f"Updated calendar feed '{feed.name}'.")
            return HttpResponseRedirect(f"{reverse('events:feeds')}#feed-{feed.pk}")
        # Re-render the manage page with this feed's form showing its errors.
        view = CalendarFeedListView()
        context = view._context(request, edit_forms={feed.pk: form})
        return render(request, CalendarFeedListView.template_name, context)


class ChapterFeedSubscribeView(LoginRequiredMixin, View):
    """Subscribe to a chapter's public events from the chapter detail page.

    Adds the chapter to an existing feed when one is chosen, otherwise creates a
    new feed — so members build up a combined calendar instead of accumulating a
    separate feed per chapter.
    """

    def post(self, request, *args, **kwargs):
        from thetatauCMT.chapters.models import Chapter

        chapter = get_object_or_404(Chapter, slug=request.POST.get("chapter"))
        target = request.POST.get("feed") or "new"
        feed = None
        if target != "new":
            feed = CalendarFeedSubscription.objects.filter(pk=target, user=request.user).first()
        if feed is None:
            feed = CalendarFeedSubscription.objects.create(
                user=request.user,
                name=f"{chapter.name} public events",
                include_national=False,
                include_todos=False,
            )
            verb = "Created a new feed with"
        else:
            verb = f"Added {chapter.name} to '{feed.name}' —"
        feed.chapters.add(chapter)
        messages.add_message(
            request,
            messages.SUCCESS,
            f"{verb} {chapter.name}'s public events. Copy the feed URL below into your calendar app.",
        )
        return HttpResponseRedirect(f"{reverse('events:feeds')}#feed-{feed.pk}")


class CalendarFeedDeleteView(LoginRequiredMixin, View):
    """Delete one of the member's own calendar feeds."""

    def post(self, request, *args, **kwargs):
        feed = CalendarFeedSubscription.objects.filter(pk=kwargs["pk"], user=request.user).first()
        if feed is not None:
            feed.delete()
            messages.add_message(request, messages.SUCCESS, "Calendar feed removed.")
        return HttpResponseRedirect(reverse("events:feeds"))
