"""The registry fixture and its loader (TWI-8).

Two kinds of test live here, and the split matters.

*Fixture content* tests read `feature_registry.json` straight off disk. They are
the reason the fixture can be edited confidently: every `url_name` has to
reverse, and every audience, role, flag and task slug has to be a value the rest
of the application recognises. A typo in the fixture is otherwise invisible until
a card renders unlinked in production.

*Loader* tests cover the contract that makes re-seeding after each release safe:
match on `key`, never duplicate, never delete, never lose the acknowledgement
history pointing at these rows.
"""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.urls import resolve

from core.models import ALL_ROLES
from thetatauCMT.guides.management.commands.load_feature_registry import DEFAULT_PATH
from thetatauCMT.guides.models import Audience, Feature, FeatureArea, UserAcknowledgement
from thetatauCMT.guides.services import resolve_feature_url
from thetatauCMT.tasks.models import Task
from thetatauCMT.users.tests.factories import UserFactory

FLAGS_FIXTURE = Path(settings.APPS_DIR) / "configs" / "fixtures" / "feature_flags.json"
TASKS_FIXTURE = Path(settings.APPS_DIR) / "tasks" / "fixtures" / "tasks.json"

REGISTRY = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
AREAS = REGISTRY["areas"]
FEATURES = [(area, feature) for area in AREAS for feature in area.get("features", [])]

# Entries the fixture retires on purpose: the row is kept so its acknowledgement
# history survives, but it is hidden from the catalog. The depledge survey is
# reached only from a personal link in an email, for example.
RETIRED_FEATURE_KEYS = {feature["key"] for _, feature in FEATURES if feature.get("is_active") is False}


def _inactive_feature_keys():
    return set(Feature.objects.filter(is_active=False).values_list("key", flat=True))


def _label(area, child):
    return f"{area['key']}/{child.get('key') or child.get('title')}"


def _flag_keys():
    return {row["fields"]["key"] for row in json.loads(FLAGS_FIXTURE.read_text(encoding="utf-8"))}


def _load(**kwargs):
    call_command("load_feature_registry", verbosity=0, **kwargs)


def _write_registry(tmp_path, areas):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"version": "test", "areas": areas}), encoding="utf-8")
    return str(path)


def _make_late_task():
    """A task the fixture references but `tasks.json` does not contain."""
    return Task.objects.create(
        name="Widget Report",
        owner="regent",
        type="task",
        description="A task that arrives after the registry does.",
    )


# ---------------------------------------------------------------------------
# Fixture content
#
# These walk the whole file and report every offender at once. Parametrizing
# per entry would name the offender for free, but it would also add hundreds of
# test ids to the suite for a single JSON file.
# ---------------------------------------------------------------------------
def test_the_fixture_covers_every_area_in_the_inventory():
    """A shrinking registry is a regression, not a tidy-up."""
    assert len(AREAS) >= 16
    assert len(FEATURES) >= 110


def test_area_keys_are_unique_slugs():
    keys = [area["key"] for area in AREAS]
    assert len(keys) == len(set(keys))
    assert [key for key in keys if not re.fullmatch(r"[a-z0-9-]+", key)] == []


def test_feature_keys_are_unique_slugs_across_the_whole_file():
    """Keys are the upsert identity, so a duplicate would silently overwrite."""
    keys = [feature["key"] for _, feature in FEATURES]
    assert sorted({key for key in keys if keys.count(key) > 1}) == []
    assert [key for key in keys if not re.fullmatch(r"[a-z0-9-]+", key)] == []


def test_every_feature_has_usable_catalog_copy():
    """`short_description` is the card body, and the column is 300 characters."""
    bad = [
        _label(area, feature)
        for area, feature in FEATURES
        if not feature["name"].strip()
        or not feature["short_description"].strip()
        or len(feature["short_description"].strip()) > 300
    ]
    assert bad == []


def test_no_feature_carries_both_a_url_name_and_an_external_url():
    bad = [_label(area, f) for area, f in FEATURES if f.get("url_name") and f.get("external_url")]
    assert bad == []


def test_every_unlinked_feature_explains_where_to_find_it():
    """An unlinked card is deliberate -- the destination needs a per-object id."""
    bad = [
        _label(area, f)
        for area, f in FEATURES
        if not f.get("url_name") and not f.get("external_url") and not f.get("long_description", "").strip()
    ]
    assert bad == []


@pytest.mark.django_db
def test_every_fixture_url_name_reverses():
    """Dynamic tokens are resolved against a real user, exactly as the catalog does."""
    user = UserFactory()
    bad = []
    for area, data in FEATURES:
        if not data.get("url_name"):
            continue
        feature = Feature(url_name=data["url_name"], url_kwargs=data.get("url_kwargs", {}))
        if resolve_feature_url(feature, user) is None:
            bad.append(f"{_label(area, data)} -> {data['url_name']} {data.get('url_kwargs', {})}")
    assert bad == []


@pytest.mark.django_db
def test_every_fixture_url_name_answers_get():
    """ "Take me there" issues a GET, so a POST-only endpoint is a 405 in the catalog.

    Several genuinely useful things -- the badge lookup, calendar subscriptions,
    logging your own attendance -- are action endpoints belonging to a form on a
    larger page. Those features must link the *page*, with ``url_fragment``
    naming the control, not the endpoint the form posts to.
    """
    user = UserFactory()
    bad = []
    for area, data in FEATURES:
        if not data.get("url_name"):
            continue
        feature = Feature(url_name=data["url_name"], url_kwargs=data.get("url_kwargs", {}))
        path = resolve_feature_url(feature, user)
        view = resolve(path.partition("#")[0]).func
        cls = getattr(view, "view_class", None)
        if cls is None:  # a function view; no declared handler set to inspect
            continue
        if not any(hasattr(cls, method) for method in ("get", "head")):
            allowed = [m.upper() for m in cls.http_method_names if hasattr(cls, m)]
            bad.append(f"{_label(area, data)} -> {data['url_name']} ({cls.__name__} allows {allowed})")
    assert bad == []


def test_no_feature_links_the_viewflow_frontend_inbox():
    """`/workflow/` is admin tooling, and reversing is not the same as reaching.

    The frontend inbox reverses fine and answers GET, so the checks above pass it
    happily -- but nothing in the app links there and a chapter officer following
    it is bounced to the login page. A member's outstanding process tasks belong
    on ``tasks:list``, which lists them under "Chapter Process Reminders". Start a
    flow through its own ``:start`` URL instead; those are catalogued and work.
    """
    bad = [
        f"{_label(area, f)} -> {f['url_name']}"
        for area, f in FEATURES
        if f.get("url_name", "") in {"viewflow:index", "viewflow:queue", "viewflow:archive"}
    ]
    assert bad == []


@pytest.mark.django_db
def test_every_fixture_url_fragment_names_an_id_in_a_template():
    """A fragment that names nothing lands the viewer at the top of the page."""
    templates = " ".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (Path(settings.APPS_DIR) / "templates").rglob("*.html")
    )
    bad = [
        f"{_label(area, f)} -> #{f['url_fragment']}"
        for area, f in FEATURES
        if f.get("url_fragment") and f'id="{f["url_fragment"]}"' not in templates
    ]
    assert bad == []


def test_audiences_roles_and_flags_use_known_values():
    entries = [(_label(area, f), f) for area, f in FEATURES] + [(area["key"], area) for area in AREAS]
    flags = _flag_keys()
    bad = []
    for label, entry in entries:
        if entry.get("audience", "") not in {"", *Audience.values}:
            bad.append(f"{label}: audience {entry['audience']!r}")
        unknown_roles = sorted(set(entry.get("roles", [])) - set(ALL_ROLES))
        if unknown_roles:
            bad.append(f"{label}: roles {unknown_roles}")
        if entry.get("feature_flag", "") not in {"", *flags}:
            bad.append(f"{label}: feature_flag {entry['feature_flag']!r}")
    assert bad == []


def test_every_referenced_task_slug_exists_in_the_tasks_fixture():
    """`Task.slug` is `slugify(name + owner)`, so these are easy to mistype."""
    seeded = {row["fields"]["slug"] for row in json.loads(TASKS_FIXTURE.read_text(encoding="utf-8"))}
    referenced = {feature["task"] for _, feature in FEATURES if feature.get("task")}
    assert referenced <= seeded, f"unknown task slug(s): {sorted(referenced - seeded)}"


def test_a_task_is_claimed_by_at_most_one_feature():
    """The card shows the task's due date, so two claimants would contradict each other."""
    slugs = [feature["task"] for _, feature in FEATURES if feature.get("task")]
    assert len(slugs) == len(set(slugs))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_the_loader_creates_the_whole_registry():
    _load()
    assert FeatureArea.objects.count() == len(AREAS)
    assert Feature.objects.count() == len(FEATURES)
    assert not FeatureArea.objects.filter(is_active=False).exists()
    assert _inactive_feature_keys() == RETIRED_FEATURE_KEYS


@pytest.mark.django_db
def test_display_order_comes_from_position_in_the_fixture():
    _load()
    assert list(FeatureArea.objects.values_list("key", flat=True)) == [area["key"] for area in AREAS]
    first = AREAS[0]
    keys = FeatureArea.objects.get(key=first["key"]).features.values_list("key", flat=True)
    assert list(keys) == [feature["key"] for feature in first["features"]]


@pytest.mark.django_db
def test_task_links_are_resolved_by_slug():
    _load()
    linked = Feature.objects.filter(task__isnull=False)
    assert linked.exists()
    for feature in linked.select_related("task"):
        expected = next(data["task"] for _, data in FEATURES if data["key"] == feature.key)
        assert feature.task.slug == expected


@pytest.mark.django_db
def test_reloading_changes_nothing():
    _load()
    before = dict(Feature.objects.values_list("key", "id"))
    _load()
    assert Feature.objects.count() == len(FEATURES)
    assert dict(Feature.objects.values_list("key", "id")) == before


@pytest.mark.django_db
def test_reloading_keeps_user_history():
    """The whole reason this is not `loaddata`: these rows have to survive."""
    _load()
    user = UserFactory()
    feature = Feature.objects.first()
    UserAcknowledgement.objects.create(user=user, target=feature, source="modal")

    _load()

    assert UserAcknowledgement.objects.filter(user=user, object_id=feature.pk).exists()


@pytest.mark.django_db
def test_reworded_copy_updates_in_place(tmp_path):
    _load()
    feature_key = FEATURES[0][1]["key"]
    original_id = Feature.objects.get(key=feature_key).pk

    areas = json.loads(json.dumps(AREAS))
    areas[0]["features"][0]["short_description"] = "Reworded for the release."
    areas[0]["name"] = "Renamed area"
    _load(path=_write_registry(tmp_path, areas))

    feature = Feature.objects.get(key=feature_key)
    assert feature.pk == original_id
    assert feature.short_description == "Reworded for the release."
    assert FeatureArea.objects.get(key=areas[0]["key"]).name == "Renamed area"
    assert Feature.objects.count() == len(FEATURES)


@pytest.mark.django_db
def test_entries_dropped_from_the_fixture_are_deactivated_not_deleted(tmp_path):
    _load()
    dropped_area = AREAS[-1]
    dropped_feature = dropped_area["features"][0]["key"]

    _load(path=_write_registry(tmp_path, AREAS[:-1]))

    assert FeatureArea.objects.filter(key=dropped_area["key"], is_active=False).exists()
    assert Feature.objects.filter(key=dropped_feature, is_active=False).exists()
    assert Feature.objects.count() == len(FEATURES)


@pytest.mark.django_db
def test_an_entry_that_comes_back_is_reactivated(tmp_path):
    _load(path=_write_registry(tmp_path, AREAS[:-1]))
    _load()
    assert not FeatureArea.objects.filter(is_active=False).exists()
    assert _inactive_feature_keys() == RETIRED_FEATURE_KEYS


@pytest.mark.django_db
def test_dry_run_writes_nothing():
    _load(dry_run=True)
    assert FeatureArea.objects.count() == 0
    assert Feature.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_after_a_load_leaves_the_rows_alone(tmp_path):
    _load()
    before = dict(Feature.objects.values_list("key", "short_description"))

    areas = json.loads(json.dumps(AREAS))
    areas[0]["features"][0]["short_description"] = "Not saved."
    _load(path=_write_registry(tmp_path, areas), dry_run=True)

    assert dict(Feature.objects.values_list("key", "short_description")) == before


@pytest.mark.django_db
def test_an_unknown_task_slug_warns_instead_of_failing(tmp_path, capsys):
    """A fresh or test database may have no tasks; the catalog is still useful."""
    areas = json.loads(json.dumps(AREAS[:1]))
    areas[0]["features"][0]["task"] = "no-such-task"

    call_command("load_feature_registry", path=_write_registry(tmp_path, areas))

    assert "no-such-task" in capsys.readouterr().out
    assert Feature.objects.get(key=areas[0]["features"][0]["key"]).task is None


@pytest.mark.django_db
def test_a_task_that_arrives_later_gets_linked_on_the_next_run(tmp_path):
    """A release can add a task and a feature together, in either order."""
    slug = _make_late_task().slug
    Task.objects.filter(slug=slug).delete()

    areas = json.loads(json.dumps(AREAS[:1]))
    feature_key = areas[0]["features"][0]["key"]
    areas[0]["features"][0]["task"] = slug
    path = _write_registry(tmp_path, areas)
    _load(path=path)
    assert Feature.objects.get(key=feature_key).task is None

    _make_late_task()
    _load(path=path)

    assert Feature.objects.get(key=feature_key).task.slug == slug


# ---------------------------------------------------------------------------
# Bad input
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_missing_fixture_is_reported(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        _load(path=str(tmp_path / "nope.json"))


@pytest.mark.django_db
def test_unreadable_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CommandError, match="not valid JSON"):
        _load(path=str(path))


@pytest.mark.django_db
def test_an_entry_without_a_key_is_reported(tmp_path):
    with pytest.raises(CommandError, match="needs a 'key'"):
        _load(path=_write_registry(tmp_path, [{"name": "Nameless", "description": "x"}]))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("audience", "everyone", "audience"),
        ("roles", ["chief bottle washer"], "roles"),
    ],
)
def test_an_invalid_feature_value_stops_the_load(tmp_path, field, value, expected):
    """`loaddata` would have written these; calling `full_clean` is the point."""
    areas = json.loads(json.dumps(AREAS[:1]))
    areas[0]["features"][0][field] = value
    with pytest.raises(CommandError, match=expected):
        _load(path=_write_registry(tmp_path, areas))
    assert not Feature.objects.exists()


@pytest.mark.django_db
def test_a_failed_load_leaves_the_previous_registry_intact(tmp_path):
    _load()
    areas = json.loads(json.dumps(AREAS))
    areas[0]["features"][0]["audience"] = "everyone"
    areas[0]["features"][0]["short_description"] = "Should not survive."

    with pytest.raises(CommandError):
        _load(path=_write_registry(tmp_path, areas))

    assert Feature.objects.count() == len(FEATURES)
    assert not Feature.objects.filter(short_description="Should not survive.").exists()


@pytest.mark.django_db
def test_the_loader_only_touches_tasks_it_is_told_about():
    """Loading the registry must not renumber or reassign seeded task rows."""
    before = list(Task.objects.values_list("slug", "id").order_by("id"))
    _load()
    assert list(Task.objects.values_list("slug", "id").order_by("id")) == before
