import importlib
import os

from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.contrib.sites.models import Site

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


def _autoload_local_anonymizers():
    """Import the project's own ``anonymizer/<app>.py`` modules.

    dj_anonymizer only auto-imports ``anonymizer/<file>.py`` when ``<file>``
    matches an installed app's ``AppConfig.name``. The local apps use dotted
    names (e.g. ``thetatauCMT.users``) but their anonymizer files are named by
    short label (``users.py``), so dj_anonymizer would never load them and none
    of the local models would be de-identified. ``base`` is always imported
    first, so we bridge that gap here: import every sibling module whose
    basename is NOT an installed app name (those short-named files are
    third-party ones such as ``address.py``/``herald.py`` that dj_anonymizer
    imports itself — importing them again would raise "already declared").

    This is intentionally dynamic so a newly added local app is picked up as
    soon as its ``anonymizer/<app>.py`` file exists; until then
    ``anonymize_db --check_only`` fails loudly for the unregistered models.
    """
    app_names = {app.name for app in apps.get_app_configs()}
    here = os.path.dirname(os.path.abspath(__file__))
    for entry in sorted(os.listdir(here)):
        if not entry.endswith(".py") or entry in ("__init__.py", "base.py"):
            continue
        module_name = entry[:-3]
        if module_name in app_names:
            # Handled by dj_anonymizer's own app.name-based loader.
            continue
        importlib.import_module(f"anonymizer.{module_name}")


_autoload_local_anonymizers()
