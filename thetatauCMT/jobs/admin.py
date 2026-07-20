from django.contrib import admin

from .models import Job, JobPostingBan, JobSearch, Keyword, Major

# ``UserForeignKey(auto_user_add=True)`` sets ``editable=False`` on the model
# field, which causes Django's admin (and any ModelForm) to skip it entirely.
# We still want national admins to be able to reassign a posting's owner, so
# flip the flag here. ``auto_user_add`` only fires on the initial insert
# (``add=True``), so existing rows are untouched when saved from the admin.
Job._meta.get_field("created_by").editable = True


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Major)
class MajorAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "priority",
        "publish_start",
        "publish_end",
        "created",
        "created_by",
    )
    list_filter = [
        "priority",
        "publish_start",
        "publish_end",
        "created",
    ]
    search_fields = ("title", "description")
    ordering = [
        "-created",
    ]
    raw_id_fields = (
        "location",
        "country",
        "created_by",
        "deleted_by",
        "reported_by",
        "approved_by",
    )
    # Ajax autocomplete for M2M fields with many rows (keywords fixture ships ~1000).
    autocomplete_fields = ("keywords", "majors")


@admin.register(JobSearch)
class JobSearchAdmin(admin.ModelAdmin):
    list_display = (
        "search_title",
        "created_by",
        "created",
        "modified",
    )
    list_filter = [
        "created",
        "modified",
    ]
    search_fields = ("search_title",)
    ordering = [
        "-created",
    ]
    raw_id_fields = ("location", "country")
    autocomplete_fields = ("keywords", "majors")


@admin.register(JobPostingBan)
class JobPostingBanAdmin(admin.ModelAdmin):
    list_display = ("user", "banned_at", "banned_by", "created")
    list_filter = ("banned_at", "created")
    search_fields = ("user__username", "user__email", "reason")
    raw_id_fields = ("user", "banned_by")
    readonly_fields = ("created", "modified")
