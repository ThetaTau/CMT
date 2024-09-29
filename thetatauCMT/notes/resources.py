from import_export import resources
from .models import ChapterNote, UserNote
from users.models import User
from chapters.models import Chapter


class ChapterNoteResource(resources.ModelResource):
    class Meta:
        model = ChapterNote
        force_init_instance = True
        fields = ("chapter__slug", "title", "note", "type", "restricted", "parent")

    def __init__(self, created_by):
        self.created_by = created_by

    def before_save_instance(self, instance, using_transactions, dry_run):
        instance.created_by = self.created_by
        instance.chapter = self.chapter

    def before_import_row(self, row, row_number=None, **kwargs):
        chapter = Chapter.objects.get(slug=row["chapter__slug"])
        self.chapter = chapter


class UserNoteResource(resources.ModelResource):
    class Meta:
        model = UserNote
        force_init_instance = True
        fields = ("user__id", "title", "note", "type", "restricted", "parent")

    def __init__(self, created_by):
        self.created_by = created_by

    def before_save_instance(self, instance, using_transactions, dry_run):
        instance.created_by = self.created_by
        instance.user = self.user

    def before_import_row(self, row, row_number=None, **kwargs):
        user = User.objects.get(id=row["user__id"])
        self.user = user
