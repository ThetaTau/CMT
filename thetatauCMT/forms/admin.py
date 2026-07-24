from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportActionModelAdmin

from core.admin import ComponentAddressAdminMixin, user_chapter

from .models import (
    OSM,
    Audit,
    Badge,
    Bylaws,
    ChapterReport,
    CollectionReferral,
    Convention,
    Depledge,
    DisciplinaryAttachment,
    DisciplinaryProcess,
    Employer,
    Guard,
    HSEducation,
    Initiation,
    InitiationProcess,
    OtherSchool,
    Pledge,
    PledgeProcess,
    PledgeProgram,
    PledgeProgramProcess,
    PrematureAlumnus,
    ResignationProcess,
    ReturnStudent,
    RiskManagement,
    StatusChange,
)
from .resources import (
    CollectionReferralResource,
    DepledgeResource,
    InitiationResource,
    PledgeProgramResource,
    PledgeResource,
    PrematureAlumnusResource,
    ReturnStudentResource,
    StatusChangeResource,
)

admin.site.register(Badge)
admin.site.register(Guard)


@admin.register(OtherSchool)
class OtherSchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "created", "modified")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("name", "created", "modified")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(ChapterReport)
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


@admin.register(HSEducation)
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
    readonly_fields = ("created_by",)


@admin.register(PledgeProgram)
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


@admin.register(RiskManagement)
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


@admin.register(Audit)
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


@admin.register(Initiation)
class InitiationAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    readonly_fields = ["process_link"]
    list_display = ("user", "date", "created", "chapter")
    list_filter = ["date", "created", "chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = InitiationResource

    def process_link(self, initiation):
        process = initiation.process.first()
        if process:
            host = settings.CURRENT_URL
            link = reverse(
                "viewflow:forms:initiationprocess:detail",
                kwargs={
                    "process_pk": process.pk,
                },
            )
            return mark_safe(f"<a href='{host}{link}' target='_blank'>Initiation Process Details<a/>")


@admin.register(Depledge)
class DepledgeAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "reason", "date", "created", user_chapter)
    list_filter = ["reason", "date", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    resource_class = DepledgeResource


@admin.register(StatusChange)
class StatusChangeAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "reason", "date_start", "date_end", "created", user_chapter)
    list_filter = ["reason", "date_start", "date_end", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__username", "user__name"]
    readonly_fields = ("created_by",)
    resource_class = StatusChangeResource


@admin.register(Pledge)
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


@admin.register(Convention)
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


@admin.register(OSM)
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


class DisciplinaryAttachmentInline(admin.TabularInline):
    model = DisciplinaryAttachment
    fields = ["file"]
    show_change_link = True


@admin.register(DisciplinaryProcess)
class DisciplinaryProcessAdmin(ComponentAddressAdminMixin, admin.ModelAdmin):
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


class InitiationInline(admin.TabularInline):
    model = InitiationProcess.initiations.through
    raw_id_fields = ["initiation"]
    extra = 1


@admin.register(InitiationProcess)
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
    inlines = [InitiationInline]


class PledgeInline(admin.TabularInline):
    model = PledgeProcess.pledges.through
    extra = 1
    raw_id_fields = ("pledge",)


@admin.register(PledgeProcess)
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


@admin.register(ResignationProcess)
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


@admin.register(PrematureAlumnus)
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


@admin.register(CollectionReferral)
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


@admin.register(ReturnStudent)
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


@admin.register(Bylaws)
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


@admin.register(PledgeProgramProcess)
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
