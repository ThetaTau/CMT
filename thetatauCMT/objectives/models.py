from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from core.models import TimeStampedModel
from chapters.models import Chapter
from users.models import User


class Objective(TimeStampedModel):
    class Meta:
        ordering = [
            "-date",
        ]

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="objectives_owned"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="objectives", blank=True, null=True
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="objectives",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=50)
    date = models.DateField()
    complete = models.BooleanField(default=False)
    description = RichTextUploadingField()
    restricted_ec = models.BooleanField(
        verbose_name="Restrict read/write to Executive Council",
        default=False,
        help_text="If True only EC will be able to read or edit",
    )
    restricted_co = models.BooleanField(
        verbose_name="Restrict read/write to Central Office",
        default=False,
        help_text="If True only CO will be able to read or edit",
    )


class Action(TimeStampedModel):
    objective = models.ForeignKey(
        Objective, on_delete=models.CASCADE, related_name="actions"
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="actions")
    date = models.DateField()
    complete = models.BooleanField(default=False)
    description = RichTextUploadingField()
