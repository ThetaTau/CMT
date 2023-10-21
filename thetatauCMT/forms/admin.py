from django.contrib import admin
from import_export.admin import ImportExportActionModelAdmin
from .models import (
    Badge,
    Bylaws,
    Guard,
    Initiation,
    Depledge,
    StatusChange,
    RiskManagement,
    PledgeProgram,
    Audit,
    Pledge,
    ChapterReport,
    HSEducation,
    Convention,
    OSM,
    DisciplinaryProcess,
    DisciplinaryAttachment,
    InitiationProcess,
    PledgeProcess,
    PrematureAlumnus,
    CollectionReferral,
    ResignationProcess,
    ReturnStudent,
    PledgeProgramProcess,
)
from .resources import (
    InitiationResource,
    DepledgeResource,
    PledgeResource,
    StatusChangeResource,
    PledgeProgramResource,
    PrematureAlumnusResource,
    CollectionReferralResource,
    ReturnStudentResource,
)
from core.admin import user_chapter


admin.site.register(Badge)
admin.site.register(Guard)


class ChapterReportAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
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


class HSEducationAdmin(admin.ModelAdmin):
    list_display = ("chapter", "program_date", "category", "approval")
    list_filter = [
        "chapter",
        "program_date",
        "category",
        "approval",
    ]
    ordering = [
        "-program_date",
    ]


admin.site.register(HSEducation, HSEducationAdmin)


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


class InitiationAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "date", "created", "chapter")
    list_filter = ["date", "created", "chapter"]
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
    list_display = ("user", "created", user_chapter)
    raw_id_fields = [
        "user",
    ]
    list_filter = [
        "user__chapter",
        "created",
    ]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
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
        "chapter__name",
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


class PledgeInline(admin.TabularInline):
    model = PledgeProcess.pledges.through
    extra = 1
    raw_id_fields = ("pledge",)


class PledgeProcessAdmin(admin.ModelAdmin):
    inlines = [PledgeInline]
    list_display = (
        "chapter",
        "created",
        "invoice",
    )
    list_filter = [
        "created",
        "chapter",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "chapter__name",
        "invoice",
    ]
    exclude = [
        "flow_class",
        "status",
        "finished",
        "artifact_content_type",
        "artifact_object_id",
        "data",
        "pledges",
    ]


admin.site.register(PledgeProcess, PledgeProcessAdmin)


class ResignationProcessAdmin(admin.ModelAdmin):
    raw_id_fields = (
        "user",
        "officer1",
        "officer2",
    )
    list_display = (
        "user",
        "chapter",
        "created",
    )
    list_filter = [
        "created",
        "chapter",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "user__name",
        "chapter__name",
    ]
    exclude = [
        "flow_class",
        "status",
        "finished",
        "artifact_content_type",
        "artifact_object_id",
        "data",
    ]


admin.site.register(ResignationProcess, ResignationProcessAdmin)


class PrematureAlumnusAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ("user",)
    list_display = (
        "user",
        "created",
        "prealumn_type",
        "approved_exec",
    )
    list_filter = [
        "created",
        "prealumn_type",
        "approved_exec",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "user__username",
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
    resource_class = PrematureAlumnusResource


admin.site.register(PrematureAlumnus, PrematureAlumnusAdmin)


class CollectionReferralAdmin(ImportExportActionModelAdmin):
    raw_id_fields = (
        "created_by",
        "user",
    )
    list_display = (
        "user",
        "balance_due",
        "created",
    )
    list_filter = [
        "created",
    ]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = CollectionReferralResource


admin.site.register(CollectionReferral, CollectionReferralAdmin)


class ReturnStudentAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ("user",)
    list_display = (
        "user",
        "created",
        "approved_exec",
    )
    list_filter = [
        "created",
        "approved_exec",
    ]
    ordering = [
        "-created",
    ]
    search_fields = [
        "user__username",
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
    resource_class = ReturnStudentResource


admin.site.register(ReturnStudent, ReturnStudentAdmin)


class BylawsAdmin(ImportExportActionModelAdmin):
    list_display = (
        "chapter",
        "created",
    )
    list_filter = [
        "created",
        "chapter",
    ]
    ordering = [
        "-created",
    ]


admin.site.register(Bylaws, BylawsAdmin)


class PledgeProgramProcessAdmin(admin.ModelAdmin):
    list_display = (
        "chapter",
        "approval",
        "approval_comments",
    )
    list_filter = [
        "chapter",
        "approval",
    ]
    ordering = [
        "-created",
    ]
    exclude = [
        "flow_class",
        "status",
        "finished",
        "artifact_content_type",
        "artifact_object_id",
        "data",
    ]


admin.site.register(PledgeProgramProcess, PledgeProgramProcessAdmin)
