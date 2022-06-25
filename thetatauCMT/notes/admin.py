from django.contrib import admin

from .models import UserNote, ChapterNote


class UserNoteAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    readonly_fields = ("created_by", "modified_by", "created", "modified")
    list_display = ("user", "title", "restricted", "type", "created", "modified")
    list_filter = ["type", "restricted", "user__chapter", "created", "modified"]
    search_fields = ["user__name", "title"]
    ordering = [
        "-created",
    ]

    def save_model(self, request, instance, form, change):
        user = request.user
        instance = form.save(commit=False)
        if not change or not instance.created_by:
            instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return instance


admin.site.register(UserNote, UserNoteAdmin)


class ChapterNoteAdmin(admin.ModelAdmin):
    readonly_fields = ("created_by", "modified_by", "created", "modified")
    list_display = ("chapter", "title", "restricted", "type", "created", "modified")
    list_filter = ["type", "restricted", "chapter", "created", "modified"]
    search_fields = ["title"]
    ordering = [
        "-created",
    ]

    def save_model(self, request, instance, form, change):
        user = request.user
        instance = form.save(commit=False)
        if not change or not instance.created_by:
            instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return instance


admin.site.register(ChapterNote, ChapterNoteAdmin)


class ChapterNoteInline(admin.TabularInline):
    model = ChapterNote
    fields = ["title", "type", "note", "restricted", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1


class UserNoteInline(admin.TabularInline):
    model = UserNote
    fields = ["title", "type", "note", "restricted", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1
    fk_name = "user"
