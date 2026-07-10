import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View

from core.models import user_is_national_officer
from core.views import LoginRequiredMixin
from thetatauCMT.events.models import Event
from thetatauCMT.users.models import User

from .forms import NationalAttendanceUploadForm
from .models import AttendanceRecord, MatchQueueItem
from .quorum import quorum_status
from .services import active_roster_for_event, can_record_attendance, parent_attendee_roster, record_attendance
from .upload import ingest_attendance_csv

logger = logging.getLogger(__name__)


def _event_url_kwargs(event):
    """URL kwargs for the non-enumerable date + slug attendance routes."""
    return {
        "year": event.date.year,
        "month": event.date.month,
        "day": event.date.day,
        "event_slug": event.slug,
    }


def _roster_url(event):
    return event.get_attendance_url()


def _lookup_event(kwargs):
    """Resolve the event from the date + slug URL kwargs (not an enumerable pk)."""
    obj = (
        Event.objects.filter(
            date__year=kwargs["year"],
            date__month=kwargs["month"],
            date__day=kwargs["day"],
            slug=kwargs["event_slug"],
        )
        .order_by("pk")
        .first()
    )
    if obj is None:
        raise Http404("No event matches the given query.")
    return obj


class AttendancePermissionMixin(LoginRequiredMixin):
    """Loads ``self.event`` from the date + slug route and enforces record permission."""

    def dispatch(self, request, *args, **kwargs):
        self.event = _lookup_event(kwargs)
        if request.user.is_authenticated and not can_record_attendance(request.user, self.event):
            messages.add_message(
                request,
                messages.ERROR,
                "Only the Chapter Scribe or officers can record attendance for this event.",
            )
            return HttpResponseRedirect(reverse("events:list"))
        return super().dispatch(request, *args, **kwargs)


class AttendanceRosterView(AttendancePermissionMixin, View):
    """Roster of active members for an event with attendance checkboxes,
    Check All / Uncheck All, a quorum indicator, and the guest section."""

    template_name = "attendance/roster.html"

    def get(self, request, *args, **kwargs):
        event = self.event
        context = self.build_context(request, event)
        return render(request, self.template_name, context)

    def build_context(self, request, event):
        records = {r.user_id: r for r in AttendanceRecord.objects.filter(event=event).select_related("user", "chapter")}
        roster_mode = request.GET.get("roster", "")
        if event.parent_event_id and roster_mode != "full":
            members = parent_attendee_roster(event)
            roster_source = "parent"
        else:
            members = active_roster_for_event(event)
            roster_source = "active"
        active_ids = set(active_roster_for_event(event).values_list("pk", flat=True))
        roster = []
        for member in members:
            rec = records.get(member.pk)
            roster.append(
                {
                    "member": member,
                    "record": rec,
                    "status": rec.status if rec else "",
                    "status_display": rec.get_status_display() if rec else "",
                    "checked": bool(rec and rec.status == AttendanceRecord.STATUS.ATTENDED),
                    "signed_up": bool(rec and rec.status == AttendanceRecord.STATUS.SIGNED_UP),
                    "is_active": member.pk in active_ids,
                }
            )
        # Default display order: alphabetical by first name (the table is also
        # client-side sortable on any column).
        roster.sort(key=lambda r: ((r["member"].first_name or "").lower(), (r["member"].last_name or "").lower()))
        active_count = len(active_ids)
        attended_active = AttendanceRecord.objects.filter(
            event=event, status=AttendanceRecord.STATUS.ATTENDED, was_active=True
        ).count()
        guest_records = [r for r in records.values() if event.chapter_id and r.chapter_id != event.chapter_id]
        # Chapters for the guest prefilter select (exclude the event's own chapter).
        from thetatauCMT.chapters.models import Chapter

        guest_chapters = (
            Chapter.objects.exclude(pk=event.chapter_id).order_by("name")
            if event.chapter_id
            else Chapter.objects.order_by("name")
        )
        url_kwargs = _event_url_kwargs(event)
        return {
            "event": event,
            "roster": roster,
            "roster_source": roster_source,
            "quorum": quorum_status(active_count, attended_active),
            "guest_records": guest_records,
            "guest_chapters": guest_chapters,
            "signed_up_count": AttendanceRecord.objects.filter(
                event=event, status=AttendanceRecord.STATUS.SIGNED_UP
            ).count(),
            "sub_events": event.sub_events.select_related("chapter", "type").order_by("date"),
            "guest_min_length": getattr(settings, "ATTENDANCE_GUEST_SEARCH_MIN_LENGTH", 2),
            "STATUS": AttendanceRecord.STATUS,
            # Non-enumerable action URLs (date + slug) for the roster forms.
            "save_url": reverse("attendance:save", kwargs=url_kwargs),
            "bulk_update_url": reverse("attendance:bulk_update", kwargs=url_kwargs),
            "guest_add_url": reverse("attendance:guest_add", kwargs=url_kwargs),
            "rollup_url": reverse("attendance:rollup", kwargs=url_kwargs),
            # National-event bulk upload + inline manual match review (WI-7).
            "is_national_event": event.is_national,
            "upload_url": f"{reverse('attendance:national_upload')}?event={event.pk}",
            "match_queue_items": (
                MatchQueueItem.objects.filter(event=event, status=MatchQueueItem.Status.PENDING).order_by(
                    "-best_score", "raw_name"
                )
            ),
        }


class AttendanceBulkSaveView(AttendancePermissionMixin, View):
    """Record attendance for all selected members in a single request (WI-3)."""

    def post(self, request, *args, **kwargs):
        event = self.event
        status = request.POST.get("status", AttendanceRecord.STATUS.ATTENDED)
        if status not in AttendanceRecord.STATUS.values:
            status = AttendanceRecord.STATUS.ATTENDED
        checked_ids = set()
        for raw in request.POST.getlist("attendees"):
            try:
                checked_ids.add(int(raw))
            except (TypeError, ValueError):
                continue
        active_map = {m.pk: m for m in active_roster_for_event(event)}
        active_ids = set(active_map.keys())
        now = timezone.now()
        recorded = 0
        with transaction.atomic():
            for uid in checked_ids:
                member = active_map.get(uid) or User.objects.filter(pk=uid).first()
                if member is None:
                    continue
                record_attendance(event, member, status, request.user, when=now)
                recorded += 1
            # Deselecting an active member for THIS status removes that record so
            # the roster reflects the checkboxes (other statuses are untouched).
            AttendanceRecord.objects.filter(event=event, status=status, user_id__in=active_ids).exclude(
                user_id__in=checked_ids
            ).delete()
        label = dict(AttendanceRecord.STATUS.choices).get(status, status)
        messages.add_message(request, messages.SUCCESS, f"Saved {recorded} '{label}' record(s).")
        return HttpResponseRedirect(_roster_url(event))


class AttendanceBulkUpdateView(AttendancePermissionMixin, View):
    """Post-event bulk lifecycle updates (WI-4): convert sign-ups to attended,
    plus individual no-show / attended overrides. History is preserved."""

    def post(self, request, *args, **kwargs):
        event = self.event
        user = request.user
        converted = 0
        with transaction.atomic():
            if request.POST.get("convert_all"):
                for rec in AttendanceRecord.objects.filter(event=event, status=AttendanceRecord.STATUS.SIGNED_UP):
                    rec.set_status(AttendanceRecord.STATUS.ATTENDED, changed_by=user)
                    converted += 1
            for uid in request.POST.getlist("no_show"):
                rec = AttendanceRecord.objects.filter(event=event, user_id=uid).first()
                if rec:
                    rec.set_status(AttendanceRecord.STATUS.NO_SHOW, changed_by=user)
            for uid in request.POST.getlist("attended"):
                rec = AttendanceRecord.objects.filter(event=event, user_id=uid).first()
                if rec:
                    rec.set_status(AttendanceRecord.STATUS.ATTENDED, changed_by=user)
        messages.add_message(request, messages.SUCCESS, f"Updated attendance ({converted} sign-up(s) converted).")
        return HttpResponseRedirect(_roster_url(event))


class AttendanceRollupView(AttendancePermissionMixin, View):
    """Attendance rollup for a parent event: per sub-event counts + aggregate (WI-5)."""

    template_name = "attendance/rollup.html"

    def get(self, request, *args, **kwargs):
        parent = self.event
        sub_events = list(parent.sub_events.select_related("chapter", "type").order_by("date"))
        rows = []
        all_attendee_ids = set()
        for sub in sub_events:
            attended = AttendanceRecord.objects.filter(event=sub, status=AttendanceRecord.STATUS.ATTENDED)
            attended_ids = set(attended.values_list("user_id", flat=True))
            all_attendee_ids |= attended_ids
            active_count = active_roster_for_event(sub).count()
            attended_active = attended.filter(was_active=True).count()
            rows.append(
                {
                    "event": sub,
                    "attended_count": len(attended_ids),
                    "attended_active": attended_active,
                    "active_count": active_count,
                    "quorum": quorum_status(active_count, attended_active),
                }
            )
        parent_attended = AttendanceRecord.objects.filter(event=parent, status=AttendanceRecord.STATUS.ATTENDED)
        parent_attended_ids = set(parent_attended.values_list("user_id", flat=True))
        all_attendee_ids |= parent_attended_ids
        total_records = AttendanceRecord.objects.filter(
            event__in=[parent] + sub_events, status=AttendanceRecord.STATUS.ATTENDED
        ).count()
        aggregate = {
            "sub_event_count": len(sub_events),
            "unique_attendees": len(all_attendee_ids),
            "total_records": total_records,
        }
        context = {
            "parent": parent,
            "rows": rows,
            "aggregate": aggregate,
            "parent_attended_count": len(parent_attended_ids),
        }
        return render(request, self.template_name, context)


class GuestMemberAutocompleteView(LoginRequiredMixin, View):
    """Privacy-safe cross-chapter member lookup (WI-6).

    Requires a chapter prefilter AND a minimum-length query, and returns only
    that chapter's matching members (with badge + grad year for disambiguation).
    There is deliberately no way to enumerate the full membership.
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and (user.is_officer_group or user.is_superuser)):
            return JsonResponse({"results": [], "error": "Not authorized."}, status=403)
        chapter_id = request.GET.get("chapter")
        if not chapter_id:
            return JsonResponse({"results": [], "error": "Select a chapter before searching."}, status=400)
        try:
            chapter_id = int(chapter_id)
        except (TypeError, ValueError):
            return JsonResponse({"results": [], "error": "Invalid chapter."}, status=400)
        query = (request.GET.get("q") or "").strip()
        min_length = getattr(settings, "ATTENDANCE_GUEST_SEARCH_MIN_LENGTH", 2)
        if len(query) < min_length:
            return JsonResponse({"results": [], "error": f"Enter at least {min_length} characters to search."})
        max_results = getattr(settings, "ATTENDANCE_GUEST_SEARCH_MAX_RESULTS", 20)
        members = (
            User.objects.filter(chapter_id=chapter_id)
            .filter(Q(name__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
            .order_by("last_name", "first_name")[:max_results]
        )
        results = [
            {
                "id": member.pk,
                "text": f"{member.name} — badge {member.badge_number}, grad {member.graduation_year}",
                "name": member.name,
                "badge_number": member.badge_number,
                "graduation_year": member.graduation_year,
            }
            for member in members
        ]
        return JsonResponse({"results": results})


class AttendanceGuestAddView(AttendancePermissionMixin, View):
    """Record attendance for one or more members from other chapters (WI-6).

    Accepts a ``member`` list so several guests can be submitted at once.
    """

    def post(self, request, *args, **kwargs):
        event = self.event
        status = request.POST.get("status", AttendanceRecord.STATUS.ATTENDED)
        if status not in AttendanceRecord.STATUS.values:
            status = AttendanceRecord.STATUS.ATTENDED
        member_ids = []
        for raw in request.POST.getlist("member"):
            try:
                member_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        added = 0
        names = []
        with transaction.atomic():
            for mid in member_ids:
                member = User.objects.filter(pk=mid).first()
                if member is None:
                    continue
                record_attendance(event, member, status, request.user)
                added += 1
                names.append(member.name)
        if added:
            messages.add_message(
                request,
                messages.SUCCESS,
                f"Recorded guest attendance for {added} member(s): {', '.join(names)}.",
            )
        else:
            messages.add_message(request, messages.WARNING, "No guests were selected.")
        return HttpResponseRedirect(_roster_url(event))


# ===========================================================================
# WI-7 — National event bulk attendance upload + matching queue
# ===========================================================================


class NationalOfficerRequiredMixin(LoginRequiredMixin):
    """Restrict a view to National Officers / Admins (WI-7).

    Qualification is delegated to :func:`core.models.user_is_national_officer`
    (superuser, the ``natoff`` group, or a current national-officer role).
    """

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user_is_national_officer(user):
            messages.add_message(
                request,
                messages.ERROR,
                "Only National Officers can upload or resolve national attendance.",
            )
            return HttpResponseRedirect(reverse("events:list"))
        return super().dispatch(request, *args, **kwargs)


class NationalAttendanceUploadView(NationalOfficerRequiredMixin, View):
    """Upload a CSV of attendees for a national event; auto-match confident rows
    and route the rest to the manual match queue (WI-7)."""

    template_name = "attendance/national_upload.html"

    def get(self, request, *args, **kwargs):
        initial = {}
        event_id = request.GET.get("event")
        if event_id:
            event = Event.objects.national().filter(pk=event_id).first()
            if event is not None:
                initial["event"] = event.pk
        return render(request, self.template_name, {"form": NationalAttendanceUploadForm(initial=initial)})

    def post(self, request, *args, **kwargs):
        form = NationalAttendanceUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        event = form.cleaned_data["event"]
        default_status = form.cleaned_data["default_status"]
        file_bytes = form.cleaned_data["file"].read()
        result = ingest_attendance_csv(event, file_bytes, request.user, default_status=default_status)
        messages.add_message(
            request,
            messages.SUCCESS,
            (
                f"Processed {result.total} row(s) for {event.name}: "
                f"{result.auto_matched} auto-matched, {result.updated} updated, "
                f"{result.queued} routed to the review queue, {result.skipped} skipped."
            ),
        )
        for err in result.errors[:10]:
            messages.add_message(request, messages.WARNING, err)
        url = reverse("attendance:match_queue")
        return HttpResponseRedirect(f"{url}?event={event.pk}")


class MatchQueueListView(NationalOfficerRequiredMixin, View):
    """Review pending unresolved attendance rows and their candidate matches (WI-7)."""

    template_name = "attendance/match_queue.html"

    def get(self, request, *args, **kwargs):
        items = MatchQueueItem.objects.filter(status=MatchQueueItem.Status.PENDING).select_related("event")
        event = None
        event_id = request.GET.get("event")
        if event_id:
            try:
                event = Event.objects.filter(pk=int(event_id)).first()
            except (TypeError, ValueError):
                event = None
            if event is not None:
                items = items.filter(event=event)
        context = {
            "items": items.order_by("event__name", "-best_score", "raw_name"),
            "event": event,
            "STATUS": AttendanceRecord.STATUS,
            "resolved_count": MatchQueueItem.objects.filter(status=MatchQueueItem.Status.RESOLVED).count(),
        }
        return render(request, self.template_name, context)


class MatchQueueResolveView(NationalOfficerRequiredMixin, View):
    """Manually resolve (confirm a candidate / pick a member) or skip a queue item (WI-7)."""

    def post(self, request, *args, **kwargs):
        item = MatchQueueItem.objects.filter(pk=request.POST.get("item")).select_related("event").first()
        if item is None:
            messages.add_message(request, messages.ERROR, "Queue item not found.")
            return self._redirect(request)
        if not item.is_pending:
            messages.add_message(request, messages.INFO, "That row was already resolved.")
            return self._redirect(request, item)

        action = request.POST.get("action", "resolve")
        if action == "skip":
            item.skip(request.user, note=request.POST.get("note", ""))
            messages.add_message(request, messages.SUCCESS, f"Skipped '{item.display_label}'.")
            return self._redirect(request, item)

        user_id = request.POST.get("user_id")
        member = User.objects.filter(pk=user_id).first() if user_id else None
        if member is None:
            messages.add_message(request, messages.ERROR, "Select a member to confirm the match.")
            return self._redirect(request, item)
        status = request.POST.get("status", item.target_status)
        if status not in AttendanceRecord.STATUS.values:
            status = item.target_status
        item.resolve_to(member, request.user, status=status)
        messages.add_message(
            request,
            messages.SUCCESS,
            f"Recorded attendance for {member.name} (from '{item.display_label}').",
        )
        return self._redirect(request, item)

    def _redirect(self, request, item=None):
        # Prefer an explicit, safe ``next`` (e.g. resolving inline from the
        # national event's attendance page returns there); otherwise fall back
        # to the match queue filtered to the item's event.
        nxt = request.POST.get("next")
        if nxt and url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return HttpResponseRedirect(nxt)
        url = reverse("attendance:match_queue")
        event_id = request.POST.get("event") or (item.event_id if item else None)
        if event_id:
            url = f"{url}?event={event_id}"
        return HttpResponseRedirect(url)


class NationalMemberAutocompleteView(NationalOfficerRequiredMixin, View):
    """Cross-chapter member search for manual queue resolution (National Officers only)."""

    def get(self, request, *args, **kwargs):
        query = (request.GET.get("q") or "").strip()
        min_length = getattr(settings, "ATTENDANCE_GUEST_SEARCH_MIN_LENGTH", 2)
        if len(query) < min_length:
            return JsonResponse({"results": [], "error": f"Enter at least {min_length} characters to search."})
        max_results = getattr(settings, "ATTENDANCE_GUEST_SEARCH_MAX_RESULTS", 20)
        filters = Q(name__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        if query.isdigit():
            filters |= Q(badge_number=int(query))
        if "@" in query:
            filters |= Q(email__iexact=query) | Q(email_school__iexact=query)
        members = (
            User.objects.filter(filters).select_related("chapter").order_by("last_name", "first_name")[:max_results]
        )
        results = [
            {
                "id": member.pk,
                "text": (
                    f"{member.name} — {member.chapter.name if member.chapter_id else 'No chapter'}, "
                    f"badge {member.badge_number}, grad {member.graduation_year}"
                ),
                "name": member.name,
                "chapter": member.chapter.name if member.chapter_id else "",
                "badge_number": member.badge_number,
                "graduation_year": member.graduation_year,
            }
            for member in members
        ]
        return JsonResponse({"results": results})
