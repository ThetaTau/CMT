from django.db import migrations
from django.utils.text import slugify


def derive_slugs(apps, schema_editor):
    """Give hand-set legacy slugs (``dues``, ``audit-treasurer``) the ``slugify(name + owner)``
    form ``Task.save()`` writes, which it otherwise does on the row's first admin save
    (adding a due date is enough), silently unlinking the feature registry entries naming it.
    """
    Task = apps.get_model("tasks", "Task")
    max_length = Task._meta.get_field("slug").max_length
    taken = set(Task.objects.values_list("slug", flat=True))
    for task in Task.objects.order_by("pk"):
        slug = slugify(task.name + task.owner)
        if slug in taken or len(slug) > max_length:
            continue
        Task.objects.filter(pk=task.pk).update(slug=slug)
        taken.discard(task.slug)
        taken.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0008_taskdate_archived_taskdate_archived_on_and_more"),
    ]

    operations = [
        migrations.RunPython(derive_slugs, migrations.RunPython.noop),
    ]
