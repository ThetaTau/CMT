import os
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from ckeditor_uploader.fields import RichTextUploadingField

from core.models import TimeStampedModel, EnumClass
from chapters.models import Chapter


def get_upload_path(instance, filename):
    if not hasattr(instance, "chapter"):
        chapter = instance.user.chapter
    else:
        chapter = instance.chapter
    if hasattr(instance, "user"):
        file_path = os.path.join(
            "notes",
            f"{chapter.slug}",
            f"{instance.user.user_id}",
            f"{chapter.slug}_{instance.user.user_id}_{filename}",
        )
    else:
        file_path = os.path.join(
            "notes", f"{chapter.slug}", "chapter_notes", f"{chapter.slug}_{filename}",
        )
    return file_path


class Note(TimeStampedModel):
    class TYPES(EnumClass):
        responsible = ("responsible", "Responsible")
        not_responsible = ("not_responsible", "Not Responsible")
        accolade = ("accolade", "Accolade")
        note = ("note", "Note")

    title = models.CharField(_("Title"), max_length=255)
    note = RichTextUploadingField()
    file = models.FileField(upload_to=get_upload_path, blank=True, null=True)
    type = models.CharField(
        max_length=20, default="note", choices=[x.value for x in TYPES]
    )

    class Meta:
        abstract = True


class ChapterNote(Note):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="notes")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes_created_chapter",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes_modified_chapter",
        blank=True,
        null=True,
    )


class UserNote(Note):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes_created_user",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes_modified_user",
        blank=True,
        null=True,
    )
