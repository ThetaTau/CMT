from zoneinfo import ZoneInfo

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.db.models import Count, Q
from django.template.response import SimpleTemplateResponse
from django.utils import timezone

from . import services
from .models import (
    DEFAULT_TIME_ZONE,
    TIME_ZONE_CHOICES,
    Assignment,
    Competition,
    CriterionScore,
    Entry,
    EntryFile,
    EntryMember,
    Judge,
    KeyDate,
    NotificationLog,
    Participant,
    Round,
    RubricCriterion,
    Scorecard,
    SubmissionItem,
)

DEFAULT_ZONE_LABEL = dict(TIME_ZONE_CHOICES)[DEFAULT_TIME_ZONE]


def _follow(obj, path):
    for name in path:
        if obj is None:
            return None
        obj = getattr(obj, name)
    return obj


def _rendered_in(zone, view, *args):
    """Run an admin view, and render its page, in ``zone``.

    Admin pages are template responses, which normally render after the view has returned
    and so outside the override; render them inside it.
    """
    with timezone.override(zone):
        response = view(*args)
        if isinstance(response, SimpleTemplateResponse) and not response.is_rendered:
            response.render()
    return response


class CompetitionTimeZoneMixin:
    """Enter and show every date and time in the competition's own time zone.

    Django reads and shows form times in the site's time zone (Arizona), so each page runs
    inside ``timezone.override`` of its competition's zone. ``zone_path`` leads from the
    object to its competition; ``posted_field`` names the form field holding the parent
    (such as a new entry's round), used before the object exists.
    """

    zone_path = ()
    posted_field = None

    def page_zone(self, request, object_id):
        competition = None
        if self.posted_field:
            value = request.POST.get(self.posted_field) or request.GET.get(self.posted_field)
            if value and str(value).isdigit():
                parent_model = self.model._meta.get_field(self.posted_field).related_model
                competition = _follow(parent_model.objects.filter(pk=value).first(), self.zone_path[1:])
        if competition is None and object_id:
            competition = _follow(self.get_object(request, unquote(object_id)), self.zone_path)
        return competition.zone if competition else ZoneInfo(DEFAULT_TIME_ZONE)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        zone = self.page_zone(request, object_id)
        return _rendered_in(zone, super().changeform_view, request, object_id, form_url, extra_context)

    def changelist_view(self, request, extra_context=None):
        return _rendered_in(ZoneInfo(DEFAULT_TIME_ZONE), super().changelist_view, request, extra_context)

    @admin.display(description="Time zone")
    def times_in(self, obj):
        competition = _follow(obj, self.zone_path) if obj is not None and obj.pk else None
        label = competition.zone_label if competition else DEFAULT_ZONE_LABEL
        return f"Every date and time on this page is {label} time, the competition's time zone."


class KeyDateInline(admin.TabularInline):
    model = KeyDate
    extra = 0
    fields = ("date", "label", "description", "link")


class RoundInline(admin.StackedInline):
    model = Round
    extra = 0
    fields = ("number", "name", "selection", "eligibility", ("opens_at", "closes_at"), "judging_closes_at")
    show_change_link = True
    verbose_name_plural = "rounds (open a round to edit its rubric, the files it collects and its other settings)"


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 1
    fields = ("chapter", "contacts", "team_size_estimate", "source", "withdrawn_at")
    readonly_fields = ("source",)
    autocomplete_fields = ("chapter", "contacts")


@admin.register(Competition)
class CompetitionAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    list_display = ("__str__", "case_title", "is_published", "chapters_taking_part", "intent_window")
    list_filter = ("is_published",)
    search_fields = ("name", "short_name", "year_label", "case_title")
    prepopulated_fields = {"slug": ("short_name", "year_label")}
    readonly_fields = ("times_in", "contact_now", "created_by", "created", "modified")
    inlines = (KeyDateInline, RoundInline, ParticipantInline)
    actions = ("copy_to_next_year",)
    fieldsets = (
        (None, {"fields": ("name", "short_name", "year_label", "slug", "is_published")}),
        ("Case", {"fields": ("case_title", "case_description")}),
        (
            "Competition page",
            {"fields": ("about", "resources", "announcement", "contact_now", "contact_role", "contact_email")},
        ),
        ("Dates", {"fields": ("times_in", "time_zone", "intent_opens_at", "intent_closes_at")}),
        ("Record", {"classes": ("collapse",), "fields": ("created_by", "created", "modified")}),
    )

    def page_zone(self, request, object_id):
        posted = request.POST.get("time_zone")
        if posted in dict(TIME_ZONE_CHOICES):
            return ZoneInfo(posted)
        return super().page_zone(request, object_id)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(active_participants=Count("participants", filter=Q(participants__withdrawn_at__isnull=True)))
        )

    @admin.display(description="Chapters taking part", ordering="active_participants")
    def chapters_taking_part(self, obj):
        return obj.active_participants

    @admin.display(description="Intent form")
    def intent_window(self, obj):
        return f"{obj.format_time(obj.intent_opens_at)} to {obj.format_time(obj.intent_closes_at)}"

    @admin.display(description="Contact now")
    def contact_now(self, obj):
        """Who replies reach today, and why, so the setting overriding the fields below is never a surprise."""
        contact = services.competition_contact(obj)
        who = f"{contact.name} ({contact.email})" if contact.name else contact.email
        why = {
            services.CONTACT_FROM_SETTING: (
                f"set by the {services.CONTACT_CONFIG_KEY} setting, which overrides the contact role and email below"
            ),
            services.CONTACT_FROM_COMPETITION: "from the contact role and email below",
            services.CONTACT_FROM_CENTRAL_OFFICE: "nobody holds the contact role below and there is no contact email",
        }[contact.source]
        return f"{who}: {why}. Replies to the competition's emails go here."

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model is not Participant:
            return super().save_formset(request, form, formset, change)
        for participant in formset.save(commit=False):
            if participant.pk is None:
                participant.source = Participant.Source.ADMIN
                participant.declared_by = request.user
            participant.save()
        for participant in formset.deleted_objects:
            participant.delete()
        formset.save_m2m()

    @admin.action(description="Copy to a new year (the setup only, not published)")
    def copy_to_next_year(self, request, queryset):
        for competition in queryset:
            copy = services.copy_to_next_year(competition, by=request.user)
            self.message_user(
                request,
                f"Copied {competition} to {copy}. It is not published. Check every date before you publish it.",
                messages.SUCCESS,
            )


def _rubric_locked(obj):
    return bool(obj is not None and getattr(obj, "rubric_locked_at", None))


class RubricCriterionInline(admin.TabularInline):
    """Read only once the rubric is locked, so every judge scores the same criteria."""

    model = RubricCriterion
    extra = 0
    fields = ("order", "name", "description", "max_points")

    def has_add_permission(self, request, obj=None):
        return not _rubric_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not _rubric_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not _rubric_locked(obj) and super().has_delete_permission(request, obj)


class SubmissionItemInline(admin.TabularInline):
    model = SubmissionItem
    extra = 0
    fields = ("order", "label", "description", "kind", "file_types", "max_size_mb", "required")


@admin.register(Round)
class RoundAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("competition",)
    posted_field = "competition"
    list_display = ("__str__", "window", "judging_deadline", "results")
    list_filter = ("competition",)
    list_select_related = ("competition",)
    readonly_fields = ("times_in", "created", "modified")
    raw_id_fields = ("results_published_by",)
    inlines = (RubricCriterionInline, SubmissionItemInline)
    fieldsets = (
        (None, {"fields": ("competition", "number", "name", "selection", "eligibility", "instructions")}),
        ("Window", {"fields": ("times_in", "opens_at", "closes_at", "grace_minutes", "judging_closes_at")}),
        (
            "Scoring and selection",
            {"fields": ("score_min", "advance_per_region", "advance_total", "min_average_to_advance", "places")},
        ),
        (
            "Reminders",
            {"fields": ("reminder_days_before_open", "reminder_days_before_close", "judge_reminder_days")},
        ),
        (
            "Results",
            {
                "fields": (
                    "share_feedback",
                    "share_scores",
                    "share_rank",
                    "results_published_at",
                    "results_published_by",
                    "rubric_locked_at",
                )
            },
        ),
        ("Record", {"classes": ("collapse",), "fields": ("created", "modified")}),
    )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "GET" and _rubric_locked(self.get_object(request, unquote(object_id))):
            self.message_user(
                request,
                "The rubric is locked because judges have started scoring. To change it, clear "
                "'Rubric locked at', save, and tell the judges.",
                messages.WARNING,
            )
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(description="Window")
    def window(self, obj):
        return f"{obj.competition.format_time(obj.opens_at)} to {obj.competition.format_time(obj.closes_at)}"

    @admin.display(description="Judging deadline", ordering="judging_closes_at")
    def judging_deadline(self, obj):
        return obj.competition.format_time(obj.judging_closes_at)

    @admin.display(description="Results published", ordering="results_published_at")
    def results(self, obj):
        return obj.competition.format_time(obj.results_published_at)


class WithdrawnFilter(admin.SimpleListFilter):
    title = "taking part or withdrawn"
    parameter_name = "withdrawn"

    def lookups(self, request, model_admin):
        return (("no", "Taking part"), ("yes", "Withdrawn"))

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(withdrawn_at__isnull=True)
        if self.value() == "yes":
            return queryset.filter(withdrawn_at__isnull=False)
        return queryset


@admin.register(Participant)
class ParticipantAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("competition",)
    posted_field = "competition"
    list_display = ("chapter", "region", "competition", "source", "contact_names", "created", "withdrawn_at")
    list_filter = ("competition", WithdrawnFilter, "source", "chapter__region")
    list_select_related = ("chapter__region", "competition")
    search_fields = ("chapter__name", "chapter__school", "contacts__name", "contacts__email")
    autocomplete_fields = ("chapter", "contacts")
    raw_id_fields = ("declared_by", "withdrawn_by")
    readonly_fields = ("times_in", "created", "modified")
    fields = (
        "competition",
        "chapter",
        "source",
        "contacts",
        "team_size_estimate",
        "note",
        "declared_by",
        "times_in",
        "withdrawn_at",
        "withdrawn_by",
        "created",
        "modified",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("contacts")

    @admin.display(description="Region", ordering="chapter__region__name")
    def region(self, obj):
        return obj.chapter.region

    @admin.display(description="Contacts")
    def contact_names(self, obj):
        return ", ".join(str(user) for user in obj.contacts.all()) or "None"

    def save_model(self, request, obj, form, change):
        if not change and obj.declared_by_id is None:
            obj.declared_by = request.user
        super().save_model(request, obj, form, change)


class EntryMemberInline(admin.TabularInline):
    model = EntryMember
    extra = 0
    fields = ("order", "user", "team_role")
    autocomplete_fields = ("user",)


class EntryFileInline(admin.TabularInline):
    model = EntryFile
    extra = 0
    fields = ("item", "file", "link", "original_name", "size", "uploaded_by", "created", "replaced_at")
    readonly_fields = ("created",)
    raw_id_fields = ("uploaded_by",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj is not None and "item" in formset.form.base_fields:
            formset.form.base_fields["item"].queryset = SubmissionItem.objects.filter(round_id=obj.round_id)
        return formset


@admin.register(Entry)
class EntryAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("round", "competition")
    posted_field = "round"
    list_display = ("chapter", "round", "title", "submitted_at", "eligible", "advanced", "place")
    list_filter = ("round__competition", "round", "eligible", "advanced")
    list_select_related = ("chapter", "round__competition")
    search_fields = ("chapter__name", "title")
    autocomplete_fields = ("chapter",)
    raw_id_fields = ("last_saved_by", "decided_by")
    readonly_fields = ("public_id", "times_in", "created", "modified")
    inlines = (EntryMemberInline, EntryFileInline)
    fieldsets = (
        (None, {"fields": ("round", "chapter", "title", "summary", "public_id")}),
        (
            "Saving",
            {
                "fields": (
                    "times_in",
                    "submitted_at",
                    "last_saved_at",
                    "last_saved_by",
                    "last_saved_on_behalf",
                    "deadline_override",
                )
            },
        ),
        (
            "Decision",
            {
                "fields": (
                    "eligible",
                    "ineligible_reason",
                    "advanced",
                    "place",
                    "decided_by",
                    "decided_at",
                    "manager_note",
                )
            },
        ),
        ("Record", {"classes": ("collapse",), "fields": ("created", "modified")}),
    )


@admin.register(Judge)
class JudgeAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("round", "competition")
    posted_field = "round"
    list_display = ("user", "round", "created", "removed_at")
    list_filter = ("round__competition", "round")
    list_select_related = ("user", "round__competition")
    search_fields = ("user__name", "user__email")
    autocomplete_fields = ("user",)
    raw_id_fields = ("added_by",)
    readonly_fields = ("times_in", "created", "modified")


@admin.register(Assignment)
class AssignmentAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("judge", "round", "competition")
    posted_field = "judge"
    list_display = ("judge_name", "entry", "stepped_aside_at")
    list_filter = ("judge__round__competition", "judge__round")
    list_select_related = ("judge__user", "judge__round__competition", "entry__chapter", "entry__round")
    search_fields = ("judge__user__name", "entry__chapter__name", "entry__title")
    raw_id_fields = ("judge", "entry")
    readonly_fields = ("public_id", "times_in", "created", "modified")

    @admin.display(description="Judge", ordering="judge__user__name")
    def judge_name(self, obj):
        return obj.judge.user


class CriterionScoreInline(admin.TabularInline):
    model = CriterionScore
    extra = 0
    fields = ("criterion", "points", "comment", "comment_hidden")

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj is not None and "criterion" in formset.form.base_fields:
            formset.form.base_fields["criterion"].queryset = RubricCriterion.objects.filter(
                round_id=obj.assignment.entry.round_id
            )
        return formset


@admin.register(Scorecard)
class ScorecardAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    zone_path = ("assignment", "judge", "round", "competition")
    posted_field = "assignment"
    list_display = ("judge_name", "entry", "submitted_at", "total")
    list_filter = ("assignment__judge__round__competition", "assignment__judge__round")
    list_select_related = (
        "assignment__judge__user",
        "assignment__entry__chapter",
        "assignment__entry__round",
    )
    search_fields = ("assignment__judge__user__name", "assignment__entry__chapter__name")
    raw_id_fields = ("assignment",)
    readonly_fields = ("times_in", "created", "modified")
    inlines = (CriterionScoreInline,)

    @admin.display(description="Judge", ordering="assignment__judge__user__name")
    def judge_name(self, obj):
        return obj.assignment.judge.user

    @admin.display(description="Entry")
    def entry(self, obj):
        return obj.assignment.entry


@admin.register(NotificationLog)
class NotificationLogAdmin(CompetitionTimeZoneMixin, admin.ModelAdmin):
    """Read only. Deleting a row lets the daily command send that email again."""

    zone_path = ("competition",)
    list_display = ("sent_at", "kind", "competition", "round", "chapter", "user")
    list_filter = ("competition", "kind")
    list_select_related = ("competition", "round__competition", "chapter", "user")
    search_fields = ("key", "recipients", "chapter__name", "user__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
