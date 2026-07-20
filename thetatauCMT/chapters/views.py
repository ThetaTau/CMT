from django.contrib import messages
from django.forms.models import modelformset_factory
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import RedirectView, TemplateView

from core.forms import MultiFormsView
from core.models import CHAPTER_OFFICER
from core.views import LoginRequiredMixin, PagedFilteredTableView, RequestConfig
from thetatauCMT.configs.models import Config
from thetatauCMT.forms.models import Audit
from thetatauCMT.forms.notifications import EmailAdvisorWelcome
from thetatauCMT.notes.tables import ChapterNoteTable
from thetatauCMT.users.forms import ExternalUserForm
from thetatauCMT.users.models import User
from thetatauCMT.users.tables import UserTable

from .filters import ChapterListFilter
from .forms import ChapterForm, ChapterFormHelper
from .models import Chapter
from .tables import AuditTable, ChapterCurriculaTable, ChapterTable


class ChapterDetailView(LoginRequiredMixin, MultiFormsView):
    template_name = "chapters/chapter_detail.html"
    form_classes = {
        "chapter": ChapterForm,
        "faculty": ExternalUserForm,
    }

    def faculty_form_valid(self, formset):
        if formset.has_changed():
            for form in formset.forms:
                if form.changed_data and "DELETE" not in form.changed_data:
                    chapter = self.request.user.current_chapter
                    if form.instance.badge_number == 999999999:
                        form.instance.chapter = chapter
                        form.instance.badge_number = chapter.next_advisor_number
                    try:
                        # This is either a previous faculty or alumni
                        user = User.objects.get(username=form.instance.email)
                    except User.DoesNotExist:
                        user = form.save()
                    if not user.is_advisor:
                        user.set_current_status(status="advisor")
                        EmailAdvisorWelcome(user).send()
                    else:
                        messages.add_message(
                            self.request,
                            messages.INFO,
                            f"Advisor {user} already exists.",
                        )
                elif form.changed_data and "DELETE" in form.changed_data:
                    user = form.instance
                    user.set_current_status(None)
        return HttpResponseRedirect(self.get_success_url())

    def create_faculty_form(self, **kwargs):
        chapter = self.request.user.current_chapter
        facultys = chapter.advisors_external
        extra = 0
        min_num = 0
        if not facultys:
            extra = 0
            min_num = 1
        factory = modelformset_factory(
            User,
            form=ExternalUserForm,
            **{
                "can_delete": True,
                "extra": extra,
                "min_num": min_num,
                "validate_min": True,
            },
        )
        # factory.form.base_fields['chapter'].queryset = chapter
        formset_kwargs = {
            "queryset": facultys,
            "form_kwargs": {"initial": {"chapter": chapter}},
        }
        if self.request.method in ("POST", "PUT"):
            if self.request.POST.get("action") == "faculty":
                formset_kwargs.update(
                    {
                        "data": self.request.POST.copy(),
                    }
                )
        return factory(**formset_kwargs)

    def get_success_url(self, form_name=None):
        return reverse("chapters:detail", kwargs={"slug": self.kwargs["slug"]})

    def get_chapter_kwargs(
        self,
    ):
        return {"instance": get_object_or_404(Chapter, slug=self.kwargs["slug"])}

    def chapter_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.get_object()
        note_table = ChapterNoteTable(data=chapter.notes_filtered(self.request.user))
        RequestConfig(self.request).configure(note_table)
        context["note_table"] = note_table
        context.update(
            {
                "object": chapter,
            }
        )
        chapter_officers = chapter.get_current_officers()
        natoff = False
        if self.request.user.is_national_officer() and not self.request.user.natoff_hidden:
            natoff = True
        admin = self.request.user.is_superuser
        table = UserTable(data=chapter_officers, natoff=natoff, admin=admin)
        table.exclude = ("badge_number", "graduation_year")
        RequestConfig(self.request, paginate={"per_page": 100}).configure(table)
        context["table"] = table
        majors = chapter.curricula.filter(approved=True).order_by("major")
        major_table = ChapterCurriculaTable(data=majors)
        context["majors"] = major_table
        # Personal officer emails + region email + the chapter's generic officer
        # mailboxes (regent/vice regent/treasurer/scribe/corresponding secretary
        # plus the general chapter address), deduped and blanks dropped.
        email_parts = [officer.email for officer in chapter_officers]
        email_parts.extend(chapter.get_generic_chapter_emails())
        seen = set()
        deduped_emails = []
        for email in email_parts:
            if email and email not in seen:
                seen.add(email)
                deduped_emails.append(email)
        email_list = ", ".join(deduped_emails)
        context["email_list"] = email_list
        context["group_tax_form_url"] = Config.get_value("GROUP_TAX_FORM")
        from thetatauCMT.attendance.models import AttendanceRecord
        from thetatauCMT.events.models import Event

        public_events = (
            Event.objects.cross_chapter_visible()
            .filter(chapter=chapter, date__gte=timezone.localdate())
            .select_related("type")
            .order_by("date", "name")
        )
        context["public_events"] = public_events
        context["my_rsvp_status"] = dict(
            AttendanceRecord.objects.filter(user=self.request.user, event__in=public_events).values_list(
                "event_id", "status"
            )
        )
        context["user_calendar_feeds"] = self.request.user.calendar_feeds.all()
        # Regional Director(s) for this chapter's region (Region.directors M2M),
        # linked to their member profiles on the chapter detail page.
        region = chapter.region
        context["region_directors"] = region.directors.all().order_by("last_name", "name") if region else []
        return context

    def get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super()._get_form_kwargs(form_name, bind_form)
        if form_name == "chapter":
            kwargs.update(
                {
                    "instance": self.get_object(),
                }
            )
        return kwargs

    def get_object(self):
        # Only get the User record for the user making the request
        return Chapter.objects.get(slug=self.kwargs["slug"])


class ChapterRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("chapters:detail", kwargs={"slug": self.request.user.current_chapter.slug})


class ChapterActivityRedirectView(LoginRequiredMixin, RedirectView):
    """Sends a logged-in user to their own chapter's activity page."""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        chapter = self.request.user.current_chapter
        return reverse("chapters:activity", kwargs={"slug": chapter.slug})


class ChapterActivityView(LoginRequiredMixin, TemplateView):
    """One-stop view of everything a chapter's members have done.

    Access: superusers, national officers (natoff group), or chapter officers
    (officer group) whose current chapter matches the requested slug.
    """

    template_name = "chapters/chapter_activity.html"
    default_months = 6
    per_page = 50
    window_choices = (
        ("3m", "Last 3 months"),
        ("6m", "Last 6 months"),
        ("12m", "Last 12 months"),
        ("current_term", "Current term"),
        ("previous_term", "Previous term"),
        ("academic_year", "Current academic year"),
    )

    def _get_chapter(self):
        return get_object_or_404(Chapter, slug=self.kwargs["slug"])

    def _user_allowed(self, user, chapter):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.groups.filter(name="natoff").exists():
            return True
        if user.groups.filter(name="officer").exists():
            current = getattr(user, "current_chapter", None)
            if current is not None and current.pk == chapter.pk:
                return True
        return False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        chapter = self._get_chapter()
        if not self._user_allowed(request.user, chapter):
            messages.add_message(
                request,
                messages.ERROR,
                "Only chapter officers of this chapter, national officers, " "or superusers can view chapter activity.",
            )
            return HttpResponseRedirect(reverse("home"))
        self.chapter = chapter
        return super().dispatch(request, *args, **kwargs)

    def _resolve_window(self):
        """Return (window_key, start_dt, end_dt) based on ?window=... query param."""
        import datetime as _dt

        from core.models import academic_encompass_start_end_date, semester_encompass_start_end_date

        now = timezone.now()
        raw = (self.request.GET.get("window") or "6m").strip()
        valid_keys = {key for key, _ in self.window_choices}
        window = raw if raw in valid_keys else "6m"
        if window == "3m":
            start = now - _dt.timedelta(days=90)
            end = now
        elif window == "12m":
            start = now - _dt.timedelta(days=365)
            end = now
        elif window == "current_term":
            start, end = semester_encompass_start_end_date()
        elif window == "previous_term":
            # Step back from the START of the current term (not the end).
            # Starting from `prev_end` and stepping back 120 days can land in
            # the same term for long terms, returning the current term twice.
            current_start, _ = semester_encompass_start_end_date()
            prev_middle = current_start - _dt.timedelta(days=90)
            start, end = semester_encompass_start_end_date(prev_middle)
        elif window == "academic_year":
            start, end = academic_encompass_start_end_date()
        else:
            start = now - _dt.timedelta(days=self.default_months * 30)
            end = now
        # Normalize to tz-aware datetimes
        if isinstance(start, _dt.datetime) and timezone.is_naive(start):
            start = timezone.make_aware(start, timezone.get_current_timezone())
        if isinstance(end, _dt.datetime) and timezone.is_naive(end):
            end = timezone.make_aware(end, timezone.get_current_timezone())
        return window, start, end

    def get_context_data(self, **kwargs):
        from collections import Counter

        from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

        from thetatauCMT.chapters.activity import CATEGORIES, iter_chapter_activity

        context = super().get_context_data(**kwargs)
        window, start_dt, end_dt = self._resolve_window()
        all_items = iter_chapter_activity(self.chapter, start_dt, end_dt)
        counts = Counter(item.category for item in all_items)

        selected = (self.request.GET.get("category") or "").strip()
        if selected in CATEGORIES:
            display_items = [i for i in all_items if i.category == selected]
        else:
            selected = ""
            display_items = all_items

        paginator = Paginator(display_items, self.per_page)
        raw_page = self.request.GET.get("page")
        try:
            page_obj = paginator.page(raw_page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        base_qs = {"window": window}
        if selected:
            base_qs["category"] = selected
        base_query = "&".join(f"{k}={v}" for k, v in base_qs.items())

        context.update(
            {
                "object": self.chapter,
                "chapter": self.chapter,
                "activity_items": list(page_obj.object_list),
                "page_obj": page_obj,
                "paginator": paginator,
                "is_paginated": paginator.num_pages > 1,
                "per_page": self.per_page,
                "filtered_count": len(display_items),
                "base_query": base_query,
                "counts": {c: counts.get(c, 0) for c in CATEGORIES},
                "counts_list": [(c, counts.get(c, 0)) for c in CATEGORIES],
                "total_count": len(all_items),
                "selected_window": window,
                "window_choices": self.window_choices,
                "start_date": start_dt.date(),
                "end_date": end_dt.date(),
                "categories": CATEGORIES,
                "selected_category": selected,
            }
        )
        return context


AUDIT_ROW_NAMES = [
    "user",
    "modified",
    "dues_member",
    "dues_pledge",
    "frequency",
    "payment_plan",
    "cash_book",
    "cash_book_reviewed",
    "cash_register",
    "cash_register_reviewed",
    "member_account",
    "member_account_reviewed",
    "balance_checking",
    "balance_savings",
    "debit_card",
    "debit_card_access",
]


def build_chapter_audit_items(chapter):
    """Build the officer-role audit summary rows for ``chapter``.

    Returns the list of dicts consumed by :class:`chapters.tables.AuditTable`.
    Each row represents one audit field and its most-recent value per
    CHAPTER_OFFICER role.
    """
    audits = Audit.objects.filter(user__chapter=chapter).order_by("-modified").values(*AUDIT_ROW_NAMES)
    audit_data = {}
    for audit in audits:
        user = User.objects.get(id=audit["user"])
        role = user.get_officer_role_on_date(audit["modified"])
        if role is not None:
            role = role.role
        if (role not in audit_data) and (role in CHAPTER_OFFICER):
            audit["user"] = user
            audit_data[role] = audit
        if len(audit_data) == len(CHAPTER_OFFICER):
            break
    audit_items = []
    for name in AUDIT_ROW_NAMES:
        row = {"item": Audit._meta.get_field(name).verbose_name.title()}
        for officer in CHAPTER_OFFICER:
            audit = audit_data.get(officer)
            value = "Incomplete"
            if audit is not None:
                value = audit.get(name, "Incomplete")
            row[officer.replace(" ", "_")] = value
        audit_items.append(row)
    return audit_items


class ChapterAuditRedirectView(LoginRequiredMixin, RedirectView):
    """Sends a logged-in user to their own chapter's audit page."""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        chapter = self.request.user.current_chapter
        return reverse("chapters:audit", kwargs={"slug": chapter.slug})


class ChapterAuditView(LoginRequiredMixin, TemplateView):
    """Chapter Audit summary — one row per audit field, one column per role.

    Access: superusers, national officers, or a user whose current chapter
    matches the requested slug. Non-members are redirected home so they cannot
    inspect another chapter's financial state.
    """

    template_name = "chapters/chapter_audit.html"

    def _get_chapter(self):
        return get_object_or_404(Chapter, slug=self.kwargs["slug"])

    def _user_allowed(self, user, chapter):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.groups.filter(name="natoff").exists():
            return True
        current = getattr(user, "current_chapter", None)
        return current is not None and current.pk == chapter.pk

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        chapter = self._get_chapter()
        if not self._user_allowed(request.user, chapter):
            messages.add_message(
                request,
                messages.ERROR,
                "Only chapter members, national officers, or superusers " "can view a chapter's audit.",
            )
            return HttpResponseRedirect(reverse("home"))
        self.chapter = chapter
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_items = build_chapter_audit_items(self.chapter)
        audit_table = AuditTable(data=audit_items)
        RequestConfig(self.request).configure(audit_table)
        context["audit_table"] = audit_table
        context["chapter"] = self.chapter
        return context


class ChapterListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Chapter
    context_object_name = "chapter"
    ordering = ["name"]
    table_class = ChapterTable
    filter_class = ChapterListFilter
    formhelper_class = ChapterFormHelper
    table_pagination = False

    def get_table_kwargs(self):
        return {
            "officer": self.request.user.is_national_officer(),
        }


class DuesSyncMixin:
    def sync_dues(self, request, queryset):
        message = "Sync complete for chapters: <br>"
        for chapter in queryset.all():
            invoice_number = chapter.sync_dues(request)
            message += f"{chapter}: {invoice_number}<br>"
        messages.add_message(request, messages.INFO, mark_safe(message))

    sync_dues.short_description = "Sync selected chapters dues to Quickbooks"

    def reminder_dues(self, request, queryset):
        message = "Sent reminders to chapters: <br>"
        for chapter in queryset.all():
            result = chapter.reminder_dues()
            message += f"{chapter}: {result}<br>"
        messages.add_message(request, messages.INFO, mark_safe(message))

    reminder_dues.short_description = "Send selected chapters dues reminder"
