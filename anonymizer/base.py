from dj_anonymizer.register_models import register_skip, AnonymBase, register_anonym
from dj_anonymizer import fields

from django.contrib.sites.models import Site
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, Group
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType

register_skip([Site, Permission, Group, Session, ContentType])


class LogEntryAnonym(AnonymBase):
    object_repr = fields.string("Object Name")

    class Meta:
        exclude_fields = [
            "action_flag",
            "object_id",
            "action_time",
            "change_message",
        ]


register_anonym([(LogEntry, LogEntryAnonym)])
