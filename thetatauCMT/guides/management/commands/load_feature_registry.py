"""Load ``guides/fixtures/feature_registry.json`` into the feature registry.

Why this is a custom command rather than ``loaddata``:

* ``loaddata`` with fixed primary keys clobbers whatever is already in those
  rows, and with ``"pk": null`` it inserts a fresh duplicate on every run. The
  registry has to be re-loaded after *every* release to pick up new and reworded
  entries, so neither behaviour is acceptable.
* Rows are therefore matched on their natural key (``key``) and upserted. User
  history -- ``UserAcknowledgement`` -- points at these rows, so losing and
  recreating them would silently re-show dismissed announcements.
* ``loaddata`` bypasses ``Model.clean()``. The registry's whole value is that its
  audiences, roles and selectors are valid, so this command calls
  ``full_clean()`` on every instance and names the offending ``key`` when it
  fails.
* ``modified`` is ``auto_now``; ``loaddata`` would try to restore a serialized
  value for it. Building instances normally lets Django set it.

Anything present in the database but absent from the fixture is **deactivated,
never deleted**, so a feature that is retired keeps its acknowledgement history.

Display order is taken from list position in the fixture, so there is no
``order`` field to keep in sync by hand.
"""

import json
from datetime import date
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from thetatauCMT.guides.models import Feature, FeatureArea, RoleGuide, RoleGuideStep
from thetatauCMT.tasks.models import Task

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "feature_registry.json"

AREA_FIELDS = (
    "name",
    "description",
    "icon",
    "audience",
    "feature_flag",
)
FEATURE_FIELDS = (
    "name",
    "short_description",
    "long_description",
    "url_name",
    "external_url",
    "url_kwargs",
    "url_fragment",
    "audience",
    "roles",
    "feature_flag",
    "released_at",
    "release_version",
    "is_highlighted",
)
GUIDE_FIELDS = (
    "title",
    "summary",
)
GUIDE_STEP_FIELDS = (
    "title",
    "body",
    "cadence",
)

_UNSET = object()


class _Rollback(Exception):
    """Raised at the end of a ``--dry-run`` so the transaction unwinds."""

    def __init__(self, stats):
        super().__init__("dry run")
        self.stats = stats


class _Stats:
    def __init__(self):
        self.areas_created = 0
        self.areas_updated = 0
        self.areas_unchanged = 0
        self.areas_deactivated = 0
        self.features_created = 0
        self.features_updated = 0
        self.features_unchanged = 0
        self.features_deactivated = 0
        self.guides_created = 0
        self.guides_updated = 0
        self.guides_unchanged = 0
        self.guides_deactivated = 0
        self.guide_steps_created = 0
        self.guide_steps_updated = 0
        self.guide_steps_unchanged = 0
        self.guide_steps_removed = 0
        self.missing_tasks = []
        self.missing_features = []


def _default(model, field_name):
    """The model's own default for ``field_name``, so the fixture stays terse."""
    return model._meta.get_field(field_name).get_default()


def _parse_date(value, key):
    """``released_at`` as a ``date``.

    The fixture carries an ISO string; the database hands back a ``date``.
    Coercing here keeps a re-run from seeing every dated feature as changed.
    """
    if not value or isinstance(value, date):
        return value or None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"Feature '{key}' has an unreadable released_at {value!r}: {exc}")


def _apply(instance, values):
    """Set ``values`` on ``instance``; return whether anything actually changed.

    Reading an unset non-nullable foreign key raises rather than returning
    ``None``, so a missing attribute counts as a change.
    """
    changed = False
    for name, value in values.items():
        try:
            current = getattr(instance, name)
        except ObjectDoesNotExist:
            current = _UNSET
        if current != value:
            setattr(instance, name, value)
            changed = True
    return changed


class Command(BaseCommand):
    help = "Load or refresh the feature registry from the in-repo fixture (idempotent, upsert by key)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Registry fixture to load. Defaults to the one packaged with the guides app.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        dry_run = options["dry_run"]
        if not path.exists():
            raise CommandError(f"Registry fixture not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}")
        areas = data.get("areas")
        if not isinstance(areas, list):
            raise CommandError(f"{path} has no 'areas' list")
        guides = data.get("role_guides", [])
        if not isinstance(guides, list):
            raise CommandError(f"{path} has a 'role_guides' key that is not a list")

        stats = _Stats()
        try:
            with transaction.atomic():
                self._load(areas, stats)
                # Guides run after areas so their steps can point at features by key.
                self._load_guides(guides, stats)
                if dry_run:
                    raise _Rollback(stats)
        except _Rollback as exc:
            stats = exc.stats

        self._report(stats, path, dry_run)
        return None

    # -- loading ---------------------------------------------------------

    def _load(self, areas, stats):
        seen_areas = set()
        seen_features = set()
        for position, area_data in enumerate(areas):
            area = self._upsert_area(area_data, position, stats)
            seen_areas.add(area.key)
            for feature_position, feature_data in enumerate(area_data.get("features", [])):
                feature = self._upsert_feature(area, feature_data, feature_position, stats)
                seen_features.add(feature.key)
        self._deactivate_missing(FeatureArea, seen_areas, stats, "areas_deactivated")
        self._deactivate_missing(Feature, seen_features, stats, "features_deactivated")

    def _upsert_area(self, data, position, stats):
        key = self._require_key(data, "area")
        area = FeatureArea.objects.filter(key=key).first()
        created = area is None
        if created:
            area = FeatureArea(key=key)
        values = {field: data.get(field, _default(FeatureArea, field)) for field in AREA_FIELDS}
        values["order"] = position
        values["is_active"] = data.get("is_active", True)
        changed = _apply(area, values)
        self._validate(area, f"area '{key}'")
        if created:
            area.save()
            stats.areas_created += 1
        elif changed:
            area.save()
            stats.areas_updated += 1
        else:
            stats.areas_unchanged += 1
        return area

    def _upsert_feature(self, area, data, position, stats):
        key = self._require_key(data, "feature")
        feature = Feature.objects.filter(key=key).first()
        created = feature is None
        if created:
            feature = Feature(key=key)
        values = {field: data.get(field, _default(Feature, field)) for field in FEATURE_FIELDS}
        values["released_at"] = _parse_date(values["released_at"], key)
        values["area"] = area
        values["order"] = position
        values["is_active"] = data.get("is_active", True)
        values["task"] = self._resolve_task(data.get("task"), f"feature '{key}'", stats)
        changed = _apply(feature, values)
        self._validate(feature, f"feature '{key}'")
        if created:
            feature.save()
            stats.features_created += 1
        elif changed:
            feature.save()
            stats.features_updated += 1
        else:
            stats.features_unchanged += 1
        return feature

    def _deactivate_missing(self, model, seen_keys, stats, stat_name):
        stale = model.objects.filter(is_active=True).exclude(key__in=seen_keys)
        count = stale.update(is_active=False)
        setattr(stats, stat_name, getattr(stats, stat_name) + count)

    # -- role guides (TWI-12) --------------------------------------------

    def _load_guides(self, guides, stats):
        seen_roles = set()
        for position, guide_data in enumerate(guides):
            guide = self._upsert_guide(guide_data, position, stats)
            seen_roles.add(guide.role)
            self._sync_guide_steps(guide, guide_data.get("steps", []), stats)
        stale = RoleGuide.objects.filter(is_active=True).exclude(role__in=seen_roles)
        stats.guides_deactivated += stale.update(is_active=False)

    def _upsert_guide(self, data, position, stats):
        """Upsert one guide, matched on ``role`` -- its natural key.

        Guides have no ``key`` field: the role *is* the identity, because there
        can only ever be one guide per office and the role has to match
        ``tasks.Task.owner`` verbatim for the live obligations to join up.
        """
        role = data.get("role")
        if not role:
            raise CommandError(f"Every role guide needs a 'role'; found one without: {sorted(data)}")
        guide = RoleGuide.objects.filter(role=role).first()
        created = guide is None
        if created:
            guide = RoleGuide(role=role)
        values = {field: data.get(field, _default(RoleGuide, field)) for field in GUIDE_FIELDS}
        values["order"] = position
        values["is_active"] = data.get("is_active", True)
        changed = _apply(guide, values)
        self._validate(guide, f"role guide '{role}'")
        if created:
            guide.save()
            stats.guides_created += 1
        elif changed:
            guide.save()
            stats.guides_updated += 1
        else:
            stats.guides_unchanged += 1
        return guide

    def _sync_guide_steps(self, guide, steps, stats):
        """Same position-is-identity rule as :meth:`_sync_steps`."""
        for position, step_data in enumerate(steps):
            step = RoleGuideStep.objects.filter(guide=guide, order=position).first()
            created = step is None
            if created:
                step = RoleGuideStep(guide=guide, order=position)
            values = {field: step_data.get(field, _default(RoleGuideStep, field)) for field in GUIDE_STEP_FIELDS}
            label = f"step {position} of role guide '{guide.role}'"
            values["feature"] = self._resolve_feature(step_data.get("feature"), label, stats)
            values["task"] = self._resolve_task(step_data.get("task"), label, stats)
            changed = _apply(step, values)
            self._validate(step, label)
            if created:
                step.save()
                stats.guide_steps_created += 1
            elif changed:
                step.save()
                stats.guide_steps_updated += 1
            else:
                stats.guide_steps_unchanged += 1
        removed, _ = RoleGuideStep.objects.filter(guide=guide, order__gte=len(steps)).delete()
        stats.guide_steps_removed += removed

    def _resolve_feature(self, key, label, stats):
        """The catalog entry a guide step points at, or ``None``.

        Warn rather than fail, for the same reason as :meth:`_resolve_task`: a
        guide step still reads as useful advice without its deep link, and a
        typo should not block the whole registry from loading.
        """
        if not key:
            return None
        feature = Feature.objects.filter(key=key).first()
        if feature is None:
            stats.missing_features.append((label, key))
            self.stdout.write(self.style.WARNING(f"  no feature '{key}' for {label} -- leaving unlinked"))
        return feature

    # -- helpers ---------------------------------------------------------

    def _require_key(self, data, kind):
        key = data.get("key")
        if not key:
            raise CommandError(f"Every {kind} needs a 'key'; found one without: {sorted(data)}")
        return key

    def _resolve_task(self, slug, label, stats):
        """The ``tasks.Task`` a feature or guide step satisfies, or ``None``.

        A missing slug is a warning rather than an error: a fresh or test
        database may not have ``tasks/fixtures/tasks.json`` loaded, and the
        catalog is still useful without the due-date link.
        """
        if not slug:
            return None
        task = Task.objects.filter(slug=slug).first()
        if task is None:
            stats.missing_tasks.append((label, slug))
            self.stdout.write(self.style.WARNING(f"  no task '{slug}' for {label} -- leaving unlinked"))
        return task

    def _validate(self, instance, label):
        try:
            instance.full_clean()
        except ValidationError as exc:
            raise CommandError(f"Invalid {label}: {exc.message_dict}")

    def _report(self, stats, path, dry_run):
        prefix = "Would load" if dry_run else "Loaded"
        self.stdout.write(f"{prefix} feature registry from {path}")
        for label, created, updated, unchanged in (
            ("areas", stats.areas_created, stats.areas_updated, stats.areas_unchanged),
            ("features", stats.features_created, stats.features_updated, stats.features_unchanged),
            ("role guides", stats.guides_created, stats.guides_updated, stats.guides_unchanged),
            (
                "role guide steps",
                stats.guide_steps_created,
                stats.guide_steps_updated,
                stats.guide_steps_unchanged,
            ),
        ):
            self.stdout.write(f"  {label}: {created} added, {updated} updated, {unchanged} unchanged")
        if stats.areas_deactivated or stats.features_deactivated or stats.guides_deactivated:
            self.stdout.write(
                self.style.WARNING(
                    f"  deactivated: {stats.areas_deactivated} areas, "
                    f"{stats.features_deactivated} features, {stats.guides_deactivated} role guides"
                )
            )
        if stats.guide_steps_removed:
            self.stdout.write(self.style.WARNING(f"  removed {stats.guide_steps_removed} role guide steps"))
        if stats.missing_tasks:
            self.stdout.write(self.style.WARNING(f"  {len(stats.missing_tasks)} entr(ies) reference an unknown task"))
        if stats.missing_features:
            self.stdout.write(
                self.style.WARNING(f"  {len(stats.missing_features)} guide step(s) reference an unknown feature")
            )
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run -- nothing was written."))
        else:
            self.stdout.write(self.style.SUCCESS("Feature registry up to date."))
