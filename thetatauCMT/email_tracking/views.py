"""Admin/National-Officer views to look up a member's email communication.

These actively query the Mailjet REST API (see :mod:`.mailjet_api`) rather than
the locally-recorded webhook events, so a National Officer can pull the full
list of messages Mailjet sent to a member (or any address) on demand, and drill
into the delivery/open/click history of any single message.
"""

import logging
from datetime import datetime, timezone

from django.db.models import Q
from django.http import JsonResponse
from django.views.generic import TemplateView, View

from core.views import NationalOfficerRequiredMixin

from . import mailerlite_api, mailjet_api
from .forms import MemberCommunicationForm
from .models import EmailTrackingEvent, TrackedEmail

logger = logging.getLogger(__name__)

_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)

# Mailjet Status -> Bootstrap badge suffix.
_STATUS_BADGE = {
    "opened": "success",
    "clicked": "primary",
    "sent": "info",
    "delivered": "info",
    "queued": "secondary",
    "deferred": "warning",
    "bounce": "danger",
    "bounced": "danger",
    "hardbounced": "danger",
    "hard_bounced": "danger",
    "softbounced": "warning",
    "soft_bounced": "warning",
    "blocked": "danger",
    "spam": "warning",
    "junk": "warning",
    "unsub": "dark",
    "unsubscribed": "dark",
    "forwarded": "info",
    "opened_forward": "success",
    "complaint": "warning",
    # MailerLite activity-log names (GET /subscribers/{id}/activity-log)
    "campaign_send": "info",
    "automation_email_sent": "info",
    "email_open": "success",
    "link_click": "primary",
    "email_bounce": "danger",
    "spam_complaint": "warning",
    "email_forward": "info",
    "marketing_preferences_change": "secondary",
    "preference_center": "secondary",
    "added_to_group": "secondary",
    "activated": "success",
}

# Human-friendly labels for MailerLite activity-log names.
_MAILERLITE_LABELS = {
    "campaign_send": "Sent",
    "automation_email_sent": "Sent (automation)",
    "email_open": "Opened",
    "link_click": "Clicked",
    "email_bounce": "Bounced",
    "spam_complaint": "Spam complaint",
    "unsubscribed": "Unsubscribed",
    "email_forward": "Forwarded",
    "marketing_preferences_change": "Preferences changed",
    "preference_center": "Preference center",
    "added_to_group": "Added to group",
    "activated": "Activated",
}


def _status_class(status):
    return _STATUS_BADGE.get((status or "").lower(), "secondary")


class MemberCommunicationView(NationalOfficerRequiredMixin, TemplateView):
    """List the messages sent to a selected member or a typed email.

    Combines two sources: the Mailjet REST API (live, paginated) enriched with,
    and falling back to, the locally-recorded tracking (:class:`TrackedEmail`).
    """

    template_name = "email_tracking/member_communication.html"
    page_size = 25
    # When a date/subject search is active, scan up to this many messages per
    # address (Mailjet can't filter by subject, so we filter client-side).
    search_scan_limit = 200
    # How many MailerLite activity records to pull per address.
    mailerlite_scan_limit = 100

    def _parse(self):
        """Parse the request into (form, selected_user, emails, filters).

        Cheap: makes no Mailjet calls, so the page shell can render immediately.
        """
        form = MemberCommunicationForm(self.request.GET or None)
        selected_user = None
        emails = []
        filters = {"date_from": None, "date_to": None, "subject": ""}
        if form.is_valid():
            selected_user = form.cleaned_data.get("member")
            typed_email = form.cleaned_data.get("email")
            filters["date_from"] = form.cleaned_data.get("date_from")
            filters["date_to"] = form.cleaned_data.get("date_to")
            filters["subject"] = (form.cleaned_data.get("subject") or "").strip()
            if selected_user:
                emails = self._emails_for_user(selected_user)
            elif typed_email:
                emails = [typed_email]
        return form, selected_user, emails, filters

    def get_context_data(self, **kwargs):
        # The page shell renders immediately and does NOT hit the Mailjet API;
        # the results table is loaded asynchronously (see
        # MemberCommunicationResultsView) so the page isn't blocked on the API.
        context = super().get_context_data(**kwargs)
        form, selected_user, emails, filters = self._parse()
        context["form"] = form
        context["mailjet_configured"] = mailjet_api.is_configured()
        context["mailerlite_configured"] = mailerlite_api.is_configured()
        context["selected_user"] = selected_user
        context["emails_checked"] = emails
        context["searched"] = bool(emails)
        context["is_search"] = bool(filters["date_from"] or filters["date_to"] or filters["subject"])
        return context

    @staticmethod
    def _emails_for_user(user):
        """All addresses we know for a member: primary, school and allauth."""
        emails = []
        seen = set()

        def add(value):
            if value and value.lower() not in seen:
                seen.add(value.lower())
                emails.append(value)

        add(user.email)
        add(user.email_school)
        try:
            from allauth.account.models import EmailAddress

            for address in EmailAddress.objects.filter(user=user):
                add(address.email)
        except Exception:  # pragma: no cover - allauth always present here
            pass
        return emails

    def _page_number(self):
        try:
            page = int(self.request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        return max(page, 1)

    def _lookup(self, emails, page, filters):
        offset = (page - 1) * self.page_size
        is_search = bool(filters.get("date_from") or filters.get("date_to") or filters.get("subject"))
        # MailerLite subscriber activity (empty unless configured AND the member
        # is a MailerLite subscriber). Merged into the table as an extra source.
        mailerlite_rows = self._mailerlite_rows(emails)
        result = {
            "email_rows": [],
            "lookup_error": None,
            "page": page,
            "page_size": self.page_size,
            "has_previous": page > 1,
            "has_next": False,
            "total_count": 0,
            "source_label": "Mailjet",
        }

        if mailjet_api.is_configured():
            try:
                # Any filter, OR MailerLite rows present, means we merge and
                # paginate in memory; otherwise use Mailjet's server-side paging.
                if is_search or mailerlite_rows:
                    result.update(self._search_api(emails, page, filters, extra_rows=mailerlite_rows))
                else:
                    rows, total, has_next = self._from_api(emails, offset)
                    result["email_rows"] = rows
                    result["total_count"] = total
                    result["has_next"] = has_next
                base_label = "Mailjet"
            except (mailjet_api.MailjetConfigurationError, mailjet_api.MailjetAPIError):
                logger.warning("Mailjet message lookup failed", exc_info=True)
                result.update(self._from_local(emails, offset, filters, extra_rows=mailerlite_rows))
                result["lookup_error"] = (
                    "Could not retrieve messages from Mailjet; showing " "internally-tracked messages instead."
                )
                base_label = "Internal tracking (Mailjet unavailable)"
            result["source_label"] = f"{base_label} + MailerLite" if mailerlite_rows else base_label
            return result

        # No Mailjet credentials -> internally-tracked data (+ MailerLite).
        result.update(self._from_local(emails, offset, filters, extra_rows=mailerlite_rows))
        result["source_label"] = "MailerLite + Internal tracking" if mailerlite_rows else "Internal tracking"
        result["mailjet_unavailable"] = True
        return result

    def _from_api(self, emails, offset):
        collected = []
        email_totals = []
        page_counts = []
        for email in emails:
            try:
                email_totals.append(mailjet_api.get_message_count(email))
            except (mailjet_api.MailjetConfigurationError, mailjet_api.MailjetAPIError):
                email_totals.append(None)
            resp = mailjet_api.get_messages_for_email(email, limit=self.page_size, offset=offset)
            page_counts.append(resp["count"])
            for msg in resp["data"]:
                collected.append((email, msg))

        # Mailjet's /message Total just echoes the current page size, so decide
        # "is there a next page?" from whether any address returned a full page.
        has_next = any(count >= self.page_size for count in page_counts)
        # The accurate grand total comes from the separate countOnly lookups.
        if email_totals and all(count is not None for count in email_totals):
            total = sum(email_totals)
        else:
            total = None

        rows = self._build_rows(collected)
        rows.sort(key=lambda r: r["sent_at"] or _MIN_DT, reverse=True)
        return rows, total, has_next

    def _search_api(self, emails, page, filters, extra_rows=None):
        """Merge/paginate in memory: Mailjet can't filter by subject, so scan a
        bounded, date-narrowed window across every address, add any extra rows
        (e.g. MailerLite activity), filter, sort and paginate in memory."""
        offset = (page - 1) * self.page_size
        collected = []
        scan_capped = False
        for email in emails:
            resp = mailjet_api.get_messages_for_email(
                email,
                limit=self.search_scan_limit,
                offset=0,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
            )
            if resp["count"] >= self.search_scan_limit:
                scan_capped = True
            for msg in resp["data"]:
                collected.append((email, msg))

        rows = self._build_rows(collected) + list(extra_rows or [])
        rows = self._apply_filters(rows, filters)
        rows.sort(key=lambda r: r["sent_at"] or _MIN_DT, reverse=True)
        total = len(rows)
        return {
            "email_rows": rows[offset : offset + self.page_size],
            "total_count": total,
            "has_next": offset + self.page_size < total,
            "scan_capped": scan_capped,
        }

    def _build_rows(self, collected):
        ids = [str(m.get("ID")) for _, m in collected if m.get("ID")]
        tracked = {
            t.message_id: t for t in TrackedEmail.objects.filter(message_id__in=ids).select_related("sent_notification")
        }
        return [self._api_row(email, msg, tracked.get(str(msg.get("ID")))) for email, msg in collected]

    @staticmethod
    def _apply_filters(rows, filters):
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        subject = (filters.get("subject") or "").strip().lower()
        result = []
        for row in rows:
            sent = row.get("sent_at")
            day = sent.date() if sent else None
            if date_from and (day is None or day < date_from):
                continue
            if date_to and (day is None or day > date_to):
                continue
            if subject and subject not in (row.get("subject_display") or "").lower():
                continue
            result.append(row)
        return result

    def _from_local(self, emails, offset, filters=None, extra_rows=None):
        filters = filters or {}
        query = Q()
        for email in emails:
            query |= Q(recipient__iexact=email)
        qs = TrackedEmail.objects.filter(query).select_related("sent_notification")
        if filters.get("date_from"):
            qs = qs.filter(sent_at__date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(sent_at__date__lte=filters["date_to"])
        if filters.get("subject"):
            qs = qs.filter(subject__icontains=filters["subject"])
        qs = qs.order_by("-sent_at")

        if extra_rows:
            # Merge with extra rows (e.g. MailerLite) -> paginate in memory.
            rows = [self._local_row(t) for t in qs[: self.search_scan_limit]]
            rows = self._apply_filters(rows + list(extra_rows), filters)
            rows.sort(key=lambda r: r["sent_at"] or _MIN_DT, reverse=True)
            total = len(rows)
            return {
                "email_rows": rows[offset : offset + self.page_size],
                "total_count": total,
                "has_next": offset + self.page_size < total,
            }

        total = qs.count()
        rows = [self._local_row(t) for t in qs[offset : offset + self.page_size]]
        return {
            "email_rows": rows,
            "total_count": total,
            "has_next": offset + self.page_size < total,
        }

    @staticmethod
    def _api_row(email, msg, local):
        return {
            "message_id": str(msg.get("ID")) if msg.get("ID") else "",
            "sent_at": msg.get("arrived_at"),
            "subject_display": (msg.get("Subject") or (local.subject if local else "") or "(no subject)"),
            "recipient_email": email,
            "status": msg.get("Status") or "",
            "status_class": _status_class(msg.get("Status")),
            "has_tracking": local is not None,
            "opens": local.open_count if local else None,
            "clicks": local.click_count if local else None,
            "tracked": local,
            "source": "Mailjet",
        }

    @staticmethod
    def _local_row(tracked):
        status = tracked.last_status or ("delivered" if tracked.delivered_at else "sent")
        return {
            "message_id": tracked.message_id,
            "sent_at": tracked.sent_at,
            "subject_display": tracked.subject or "(no subject)",
            "recipient_email": tracked.recipient,
            "status": status,
            "status_class": _status_class(status),
            "has_tracking": True,
            "opens": tracked.open_count,
            "clicks": tracked.click_count,
            "tracked": tracked,
            "source": "Internal",
        }

    def _mailerlite_rows(self, emails):
        """One normalized row per (address, MailerLite campaign).

        MailerLite returns a flat activity log (one entry per open/click/send),
        so we group by campaign: each campaign becomes a single row whose
        ``history_events`` carries the individual records (shown like Mailjet's
        per-message history). Empty unless MailerLite is configured AND the
        address is a subscriber.
        """
        if not mailerlite_api.is_configured():
            return []
        rows = []
        for email in emails:
            try:
                entries = mailerlite_api.get_activity_for_email(email, limit=self.mailerlite_scan_limit)
            except (
                mailerlite_api.MailerLiteConfigurationError,
                mailerlite_api.MailerLiteAPIError,
            ):
                logger.warning("MailerLite lookup failed for %s", email, exc_info=True)
                continue
            groups = {}
            order = []
            for entry in entries:
                subject = mailerlite_api.activity_subject(entry) or "MailerLite activity"
                key = self._mailerlite_group_key(entry, subject)
                if key not in groups:
                    groups[key] = {"subject": subject, "entries": []}
                    order.append(key)
                groups[key]["entries"].append(entry)
            for key in order:
                rows.append(self._mailerlite_group_row(email, groups[key]["subject"], groups[key]["entries"]))
        return rows

    @staticmethod
    def _mailerlite_group_key(entry, subject):
        """Group activity by campaign id when available, else by subject."""
        props = entry.get("properties")
        if isinstance(props, dict):
            campaign_id = props.get("campaign_id") or props.get("automation_id")
            if campaign_id:
                return f"c:{campaign_id}"
        return f"s:{(subject or '').strip().lower()}"

    @staticmethod
    def _mailerlite_event(entry):
        """Normalize one MailerLite activity entry into a history event."""
        log_name = (entry.get("log_name") or entry.get("type") or "").strip()
        label = _MAILERLITE_LABELS.get(log_name) or (log_name.replace("_", " ").title() if log_name else "Activity")
        return {
            "log_name": log_name,
            "label": label,
            "status_class": _status_class(log_name),
            "when": mailerlite_api.parse_date(entry.get("created_at") or entry.get("date")),
        }

    @classmethod
    def _mailerlite_group_row(cls, email, subject, entries):
        events = [cls._mailerlite_event(e) for e in entries]
        events.sort(key=lambda e: e["when"] or _MIN_DT, reverse=True)
        opens = sum(1 for e in events if e["log_name"] == "email_open")
        clicks = sum(1 for e in events if e["log_name"] == "link_click")
        sent_dates = [
            e["when"] for e in events if e["log_name"] in ("campaign_send", "automation_email_sent") and e["when"]
        ]
        all_dates = [e["when"] for e in events if e["when"]]
        sent_at = min(sent_dates) if sent_dates else (min(all_dates) if all_dates else None)
        if clicks:
            status, status_class = "Clicked", _status_class("link_click")
        elif opens:
            status, status_class = "Opened", _status_class("email_open")
        elif sent_dates:
            status, status_class = "Sent", _status_class("campaign_send")
        elif events:
            status, status_class = events[0]["label"], events[0]["status_class"]
        else:
            status, status_class = "Activity", "secondary"
        return {
            "message_id": "",  # no Mailjet-style per-message drill-down
            "sent_at": sent_at,
            "subject_display": subject or "(no subject)",
            "recipient_email": email,
            "status": status,
            "status_class": status_class,
            "has_tracking": True,
            "opens": opens,
            "clicks": clicks,
            "tracked": None,
            "source": "MailerLite",
            "history_events": events,
        }


class MemberCommunicationResultsView(MemberCommunicationView):
    """The results table fragment, loaded asynchronously by the page shell.

    This is where the (slower) Mailjet API lookup happens, so the base page can
    render immediately while this fragment loads via AJAX.
    """

    template_name = "email_tracking/_results.html"

    def get_context_data(self, **kwargs):
        # Skip the page-shell get_context_data; build only what the partial needs.
        context = super(MemberCommunicationView, self).get_context_data(**kwargs)
        form, selected_user, emails, filters = self._parse()
        context["selected_user"] = selected_user
        context["emails_checked"] = emails
        context["searched"] = bool(emails)
        context["is_search"] = bool(filters["date_from"] or filters["date_to"] or filters["subject"])
        context["search_scan_limit"] = self.search_scan_limit
        if emails:
            page = self._page_number()
            context.update(self._lookup(emails, page, filters))
            params = self.request.GET.copy()
            params.pop("page", None)
            context["base_query"] = params.urlencode()
            offset = (page - 1) * self.page_size
            total = context.get("total_count")
            context["total_known"] = total is not None
            context["page_row_count"] = len(context.get("email_rows", []))
            if total is not None:
                context["showing_from"] = offset + 1 if total else 0
                context["showing_to"] = min(offset + self.page_size, total)
        return context


class MessageHistoryView(NationalOfficerRequiredMixin, View):
    """Return one message's event history as JSON.

    Prefers Mailjet's authoritative ``messagehistory`` and falls back to the
    locally-recorded :class:`EmailTrackingEvent` rows if the API is unavailable.
    """

    def get(self, request, message_id, *args, **kwargs):
        message_id = str(message_id)
        api_events = []
        api_error = None
        if mailjet_api.is_configured():
            try:
                api_events = mailjet_api.get_message_history(message_id)
            except mailjet_api.MailjetConfigurationError as exc:
                api_error = str(exc)
            except mailjet_api.MailjetAPIError:
                logger.warning("Mailjet history lookup failed", exc_info=True)
                api_error = "Could not retrieve history from Mailjet."

        if api_events:
            payload = [
                {
                    "event_type": event.get("EventType"),
                    "event_at": event["event_at"].isoformat() if event.get("event_at") else None,
                    "useragent": event.get("UserAgentFull") or event.get("Useragent") or "",
                    "source": "Mailjet",
                }
                for event in api_events
            ]
            return JsonResponse({"message_id": message_id, "events": payload})

        # Fall back to the internally-tracked events.
        local_events = EmailTrackingEvent.objects.filter(message_id=message_id).order_by("timestamp", "created")
        payload = [
            {
                "event_type": event.event_type,
                "event_at": event.timestamp.isoformat() if event.timestamp else None,
                "useragent": event.user_agent or "",
                "source": "Internal",
            }
            for event in local_events
        ]
        response = {"message_id": message_id, "events": payload}
        if not payload and api_error:
            response["error"] = api_error
        return JsonResponse(response)
