import hashlib

from django.db import migrations
from django.utils.text import slugify


def _event_slug(name):
    # Frozen copy of events.models.event_slug.
    slug = slugify(name)
    if slug:
        return slug
    return "event-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]


def backfill_event_slugs(apps, schema_editor):
    """Give events a slug the ``<slug:>`` URL converter accepts.

    ``Event.save()`` used to store ``slugify(name)`` as is, which is empty for
    a name made only of characters slugify drops (Greek letters, emoji, ...),
    and every page linking to such an event raised ``NoReverseMatch``.
    """
    Event = apps.get_model("events", "Event")
    broken = Event.objects.exclude(slug__regex=r"^[-a-zA-Z0-9_]+$").values_list("pk", "name")
    for pk, name in list(broken):
        Event.objects.filter(pk=pk).update(slug=_event_slug(name))


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0013_event_external_link_event_start_time_event_time_zone_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_event_slugs, migrations.RunPython.noop),
    ]
