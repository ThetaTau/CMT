from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse
from import_export.admin import ImportMixin


from .models import UserNote, ChapterNote
from .resources import UserNoteResource, ChapterNoteResource


class ChapterSubNoteInline(admin.TabularInline):
    verbose_name_plural = "Sub Chapter Notes"
    model = ChapterNote
    fields = ["title", "type", "note", "restricted", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1
    fk_name = "parent"


class UserSubNoteInline(admin.TabularInline):
    verbose_name_plural = "Sub User Notes"
    model = UserNote
    fields = ["title", "type", "note", "restricted", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1
    fk_name = "parent"


class UserNoteAdmin(ImportMixin, admin.ModelAdmin):
    inlines = [UserSubNoteInline]
    raw_id_fields = ["user", "parent"]
    readonly_fields = ("created_by", "modified_by", "created", "modified")
    list_display = (
        "user",
        "title",
        "restricted",
        "type",
        "parent_link",
        "created",
        "modified",
    )
    list_filter = ["type", "restricted", "user__chapter", "created", "modified"]
    search_fields = ["user__name", "title"]
    ordering = [
        "-created",
    ]
    resource_class = UserNoteResource

    def parent_link(self, obj):
        parent = None
        if obj.parent is not None:
            parent = mark_safe(
                f"<a href='{reverse('admin:notes_usernote_change', kwargs={'object_id': obj.parent.pk})}'>{obj.parent.title}</a>"
            )
        return parent

    def save_model(self, request, instance, form, change):
        user = request.user
        instance = form.save(commit=False)
        if not change or not instance.created_by:
            instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return instance

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.created_by = request.user
                instance.user = form.instance.user
            instance.modified_by = request.user
            instance.save()
        formset.save_m2m()

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        kwargs = super().get_resource_kwargs(request, *args, **kwargs)
        kwargs.update({"created_by": request.user})
        return kwargs


admin.site.register(UserNote, UserNoteAdmin)


class ChapterNoteAdmin(ImportMixin, admin.ModelAdmin):
    inlines = [ChapterSubNoteInline]
    raw_id_fields = ["parent"]
    readonly_fields = (
        "created_by",
        "modified_by",
        "created",
        "modified",
    )
    list_display = (
        "chapter",
        "title",
        "restricted",
        "type",
        "parent_link",
        "created",
        "modified",
    )
    list_filter = ["type", "restricted", "chapter", "created", "modified"]
    search_fields = ["title"]
    ordering = [
        "-created",
    ]
    resource_class = ChapterNoteResource

    def parent_link(self, obj):
        parent = None
        if obj.parent is not None:
            parent = mark_safe(
                f"<a href='{reverse('admin:notes_chapternote_change', kwargs={'object_id': obj.parent.pk})}'>{obj.parent.title}</a>"
            )
        return parent

    def save_model(self, request, instance, form, change):
        user = request.user
        instance = form.save(commit=False)
        if not change or not instance.created_by:
            instance.created_by = user
        instance.modified_by = user
        instance.save()
        form.save_m2m()
        return instance

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.created_by = request.user
                instance.chapter = form.instance.chapter
            instance.modified_by = request.user
            instance.save()
        formset.save_m2m()

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        kwargs = super().get_resource_kwargs(request, *args, **kwargs)
        kwargs.update({"created_by": request.user})
        return kwargs


admin.site.register(ChapterNote, ChapterNoteAdmin)


class ChapterNoteInline(admin.TabularInline):
    model = ChapterNote
    raw_id_fields = ["parent"]
    fields = ["title", "type", "note", "restricted", "parent", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1


class UserNoteInline(admin.TabularInline):
    model = UserNote
    raw_id_fields = ["parent"]
    fields = ["title", "type", "note", "restricted", "parent", "file"]
    ordering = ["-created"]
    show_change_link = True
    extra = 1
    fk_name = "user"
