# The feature registry

Everything the Feature Catalog, the Role Guides, the Forms landing page and the
What's New feed show comes out of one file:

    thetatauCMT/guides/fixtures/feature_registry.json

It is content, not code. Adding a page to the catalog, rewording a description, retiring a feature or
announcing a release is a JSON edit and a command — no template change, no deploy of Python.

```bash
docker exec thetataucmt_local_django python manage.py load_feature_registry --dry-run
docker exec thetataucmt_local_django python manage.py load_feature_registry
```

`--dry-run` reports exactly what would change and writes nothing. `dbseed` runs the loader, so a fresh
environment gets the registry automatically.

## How the loader behaves

- **Upsert by natural key**, never `loaddata`. Areas and features match on `key`, role guides on
  `role`, and guide steps on their position in the list. Primary keys stay stable across
  runs, which matters because `UserAcknowledgement` points at them — a
  delete-and-recreate would re-show every dismissed announcement.
- **Removing an entry deactivates it; nothing is ever deleted.** A retired feature keeps its history.
- **Display order comes from list position.** There is no `order` field to keep in sync by hand.
- **Every row is validated with `full_clean()`** before it is written, and the whole load runs in one
  transaction. An invalid audience, an unknown role or a malformed URL name fails the command and
  names the offending key; the previous registry is left exactly as it was.
- A `task` or `feature` reference that does not resolve is a **warning**, not an error — a fresh
  database may not have `tasks/fixtures/tasks.json` loaded yet, and the entry is still useful without
  its due-date link.

## File shape

```jsonc
{
  "version": "2026.07",
  "areas": [
    {
      "key": "finances",                    // stable identity; renaming orphans the row
      "name": "Finances",
      "description": "…",
      "icon": "fa-solid fa-file-invoice-dollar",
      "audience": "member",
      "feature_flag": "",
      "features": [ /* … */ ]
    }
  ],
  "role_guides": [ /* … */ ]
}
```

### Area fields

| Field | Notes |
|---|---|
| `key` | Unique, and in practice immutable. |
| `name`, `description`, `icon` | `icon` is a Font Awesome class string. |
| `audience` | `public` / `member` / `officer` / `natoff`. Features inherit it when theirs is blank. |
| `feature_flag` | A `Config` key such as `FEATURE_AWARDS`. Blank means always on. |

### Feature fields

| Field | Notes |
|---|---|
| `key`, `name`, `short_description` | `short_description` is the card text; keep it to one sentence. |
| `long_description` | Optional; rendered under the short description on the card. |
| `url_name` | A Django URL name. Omit for a concept with no page of its own. **It must answer `GET`** — "Take me there" is a link, so a POST-only action endpoint is a 405. Link the page hosting the form and use `url_fragment`. A test enforces this over the whole file. |
| `url_kwargs` | Values may be the tokens `@username`, `@chapter_slug`, `@region_slug`, resolved per viewer. An unresolvable token renders the card without a link rather than erroring. |
| `url_fragment` | Element id on the destination page, without the `#`, for a feature that is a control on a larger page. A test checks the id exists in some template. |
| `external_url` | For destinations with no Django URL (Vector LMS, the national training portal). Wins over `url_name`. |
| `audience`, `feature_flag` | Blank inherits the area's. |
| `roles` | **Targeting, never permission.** Drives the "who submits it" chips, the "For your role" block on the Forms landing, and the Role Guide's "Tools you have access to". Values must exist in `core.models.ALL_ROLES`. The displayed list is this field **plus every owner of the linked `task`**, so set it only for roles a task cannot express — the Risk Management Chair who prepares what the Regent formally owes. Leave it empty for anything every member files individually: "who submits it" then falls back to naming the audience ("Every member"), which is the truthful answer for the RMP. |
| `task` | A `tasks.Task` slug, always in the `slugify(name + owner)` form `Task.save()` writes (`duestreasurer`, `audittreasurer`). `Task.save()` re-derives the slug every time, including when a due date is added in the admin, so a slug in any other form changes on the next save and the entry loses its link. Gives the Forms landing its live due date and cadence. A task is one row *per owner*, so the Audit is five rows sharing a name: link any one of them and the catalog reads the whole name for its dates and its list of submitters. At most one feature may claim a given slug. |
| `released_at`, `release_version` | Setting `released_at` is what makes something "new": it appears in What's New and carries a `New` badge for `settings.NEW_FEATURE_MAX_AGE_DAYS`. **Leave it blank to add a catalog entry without announcing it.** |
| `is_highlighted` | Reserved for future emphasis. |

#### Where "when" comes from

A linked task gives a feature two facts, both for the viewer's own chapter:

- **Due** — the next `TaskDate` this chapter has not closed out, unarchived, no more than 90 days
  past. A date is outstanding until *every* officer who owes it has submitted.
- **Cadence** — how many distinct day-of-year the task falls on across every year on record, for
  this chapter's `school_type`. One is "Once a year", more is "Every term". Counting only the
  current calendar year instead would report a yearly task as never once its date had passed and
  been archived.

The recurrences themselves are seeded from
[date_data.csv](../../thetatauCMT/tasks/management/commands/date_data.csv) by `manage.py task_dates`
— that file is the record of when each office owes what, so a cadence that looks wrong is usually a
missing year of `TaskDate` rows rather than a bug here.

### Role guide fields

```jsonc
{
  "role": "treasurer",                       // must be a core.models.ALL_ROLES value
  "title": "Treasurer",
  "summary": "…",                            // 2–4 sentences
  "steps": [
    {
      "title": "Pay dues on time",
      "body": "…",
      "task": "duestreasurer",               // optional tasks.Task slug
      "feature": "chapter-invoices",         // optional registry feature key
      "cadence": "each_term"                 // once | each_term | annual | ongoing
    }
  ]
}
```

`role` doubles as the natural key and as the join to `tasks.Task.owner`, which is what lets a guide
show live, dated obligations instead of a second hand-written checklist that would immediately drift.
The slug in the URL is derived from `role`, so it is never authored by hand.

The `"national officer"` guide is a special case: `guides.services.get_role_guides` hands it to anyone
*currently acting as* a National Officer, whatever their actual office. `core.models.NAT_OFFICERS`
has eighteen roles sharing one audience-gated surface, so one guide for the audience beats eighteen
near-identical ones — and beats a Grand Regent having none at all. A guide for a national role also
renders a second **National officer tools** list: everything with `"audience": "natoff"` that no role
tags, which would otherwise be invisible from any guide.

## Common edits

**Announce a release.** Add or update the feature, set `released_at` to today's date and
`release_version`. It appears in What's New for everyone who can see it, and carries a `New` badge in
the catalog until each user acknowledges it.

**Retire a feature.** Delete its block. The next load deactivates the row; acknowledgement history
survives, and nothing 404s because the page itself is what you remove separately.

**Add a role guide for another committee chair.** Append to `role_guides` with any
`core.models.ALL_ROLES` value. No code change — the model already accepts every role.

**Hide something behind a flag.** Set `feature_flag` to the `Config` key. The entry disappears from
every surface while the flag is off, including What's New.

## Instrumentation

PostHog (authenticated, non-`DEBUG` only) receives:

| Event | Fired by | Properties |
|---|---|---|
| `catalog_viewed` | `static/js/catalog.js` | `cards` |
| `catalog_searched` | `static/js/catalog.js` | `query_length` (debounced; the query text is never sent) |
| `catalog_expand_all` | `static/js/catalog.js` | `expanded` |
| `feature_link_clicked` | `static/js/catalog.js` | `feature` (registry key) |
| `role_guide_viewed` | `static/js/catalog.js` | `role` |
| `whats_new_shown` / `whats_new_dismissed` | `static/js/whats_new.js` | `count` |
| `whats_new_acknowledged` / `whats_new_visited` | `static/js/whats_new.js` | `kind`, `id`, `source` |

Search *terms* are deliberately not sent — only the length — so the instrumentation cannot leak member
names typed into a search box.

## Related

- [feature-inventory.md](feature-inventory.md) — the audit the registry content was authored from.
- [guides-qa.md](guides-qa.md) — QA seed data and the manual walkthrough.
