from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin
from .models import (
    Badge,
    Guard,
    Initiation,
    Depledge,
    StatusChange,
    PledgeForm,
    RiskManagement,
    PledgeProgram,
    Audit,
    Pledge,
    ChapterReport,
    Convention,
    OSM,
    DisciplinaryProcess,
    DisciplinaryAttachment,
    InitiationProcess,
)
from .resources import (
    InitiationResource,
    DepledgeResource,
    PledgeResource,
    PledgeFormResource,
    StatusChangeResource,
    PledgeProgramResource,
)
from core.admin import user_chapter


admin.site.register(Badge)
admin.site.register(Guard)


class ChapterReportAdmin(admin.ModelAdmin):
    list_display = (
        "chapter",
        "year",
        "term",
    )
    list_filter = [
        "chapter",
        "year",
    ]
    ordering = [
        "-year",
    ]


admin.site.register(ChapterReport, ChapterReportAdmin)


class PledgeProgramAdmin(ImportExportActionModelAdmin):
    list_display = (
        "chapter",
        "manual",
        "year",
        "term",
        "modified",
    )
    list_filter = [
        "chapter",
        "manual",
        "year",
        "modified",
    ]
    ordering = [
        "-modified",
    ]
    resource_class = PledgeProgramResource


admin.site.register(PledgeProgram, PledgeProgramAdmin)


class RiskManagementAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "user",
        "date",
        "year",
        "term",
    )
    list_filter = [
        "user__chapter",
        "year",
        "term",
    ]
    ordering = [
        "-date",
    ]
    search_fields = [
        "user__name",
    ]


admin.site.register(RiskManagement, RiskManagementAdmin)


class AuditAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "user",
        "created",
        "year",
        "term",
    )
    list_filter = [
        "user__chapter",
        "year",
        "term",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "user__name",
    ]


admin.site.register(Audit, AuditAdmin)


class PledgeFormAdmin(ImportExportActionModelAdmin):
    list_display = (
        "name",
        "chapter",
        "created",
    )
    list_filter = [
        "chapter",
        "created",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "name",
    ]
    resource_class = PledgeFormResource


admin.site.register(PledgeForm, PledgeFormAdmin)


class InitiationAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "date", "created", user_chapter)
    list_filter = ["date", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = InitiationResource


admin.site.register(Initiation, InitiationAdmin)


class DepledgeAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "reason", "date", "created", user_chapter)
    list_filter = ["reason", "date", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = DepledgeResource


admin.site.register(Depledge, DepledgeAdmin)


class StatusChangeAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "reason", "date_start", "date_end", "created", user_chapter)
    list_filter = ["reason", "date_start", "date_end", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = StatusChangeResource


admin.site.register(StatusChange, StatusChangeAdmin)


class PledgeAdmin(ImportExportActionModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "school_name",
        "email_school",
        "email_personal",
        "created",
    )
    list_filter = [
        "school_name",
        "created",
    ]
    ordering = [
        "-created",
    ]
    search_fields = ["first_name", "last_name"]
    resource_class = PledgeResource


admin.site.register(Pledge, PledgeAdmin)


class ConventionAdmin(admin.ModelAdmin):
    raw_id_fields = ["delegate", "alternate", "officer1", "officer2"]
    list_display = (
        "chapter",
        "created",
        "year",
        "term",
    )
    list_filter = [
        "chapter",
        "year",
        "term",
    ]
    ordering = [
        "-created",
    ]
    search_fields = ["delegate__name", "alternate__name"]


admin.site.register(Convention, ConventionAdmin)


class OSMAdmin(admin.ModelAdmin):
    raw_id_fields = ["nominate", "officer1", "officer2"]
    list_display = (
        "chapter",
        "created",
        "year",
        "term",
    )
    list_filter = [
        "chapter",
        "year",
        "term",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "nominate__name",
    ]


admin.site.register(OSM, OSMAdmin)


class DisciplinaryAttachmentInline(admin.TabularInline):
    model = DisciplinaryAttachment
    fields = ["file"]
    show_change_link = True


class DisciplinaryProcessAdmin(admin.ModelAdmin):
    inlines = [DisciplinaryAttachmentInline]
    raw_id_fields = [
        "user",
    ]
    list_display = (
        "user",
        "chapter",
        "created",
        "trial_date",
        "why_take",
        "ed_process",
        "ec_approval",
    )
    list_filter = [
        "chapter",
        "created",
        "why_take",
        "ed_process",
        "ec_approval",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "user__name",
    ]
    exclude = [
        "flow_class",
        "status",
        "finished",
        "artifact_content_type",
        "artifact_object_id",
        "data",
    ]


admin.site.register(DisciplinaryProcess, DisciplinaryProcessAdmin)


class InitiationProcessAdmin(admin.ModelAdmin):
    list_display = (
        "chapter",
        "created",
        "ceremony",
        "invoice",
    )
    list_filter = [
        "chapter",
        "created",
        "ceremony",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "chapter",
    ]
    exclude = [
        "flow_class",
        "status",
        "finished",
        "artifact_content_type",
        "artifact_object_id",
        "data",
        "initiations",
    ]


admin.site.register(InitiationProcess, InitiationProcessAdmin)
