# Feature Discovery, Catalog & Tours ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Copilot/Claude Work Breakdown

> ## ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â THE GUIDED TOURS ARE GONE (2026-08)
>
> **TWI-4, TWI-5 and TWI-7 have been removed from the codebase.** With the catalog and role guides in
> place, each area only ever had two or three steps, and a "Show me around" button for a three-step
> tour was not worth the machinery. Everything below about tours is **historical only** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â do not
> implement against it.
>
> Deleted: `TourStep`, `UserTourCompletion`, `services.get_tour_config`, `views.TourConfigMixin`,
> `views.TourCompleteView`, the `guides:tour-complete` URL, `static/js/tours.js`,
> `static/vendor/driverjs/`, the Driver.js CSS overrides in `project.css`, every `data-tour` /
> `data-start-tour` attribute, the `has_tour` / `tour_entry_url_name` fields, all `tour_steps` in the
> registry fixture, `docs/specs/tour-anchors.md`, and the `test_tours` / `test_tour_anchors` /
> `test_tour_assets` suites. Migration `guides/0006_remove_guided_tours` drops the tables and columns;
> `0002_tourstep_usertourcompletion` stays where it is because later migrations depend on its name.
>
> Still live and unaffected: TWI-1, 2, 3, 6, 8, 9, 9b, 10 (minus the tour card on `/help/`), 12, 13.

> ## Follow-up polish (2026-08)
>
> Five changes on top of the delivered plan. Full suite after: **2569 passed, 17 skipped, 0 failed.**
>
> 1. **The catalog links to your own role guide.** `CatalogView` puts `get_role_guides(user)` in the
>    context; `catalog.html` renders a button per guide, or a link to the index for a member holding
>    no office. The catalog listed 122 things without ever saying which were *yours*.
> 2. **National officers get a guide.** `NAT_OFFICERS` has eighteen roles sharing one audience-gated
>    surface, so `services.NATIONAL_GUIDE_ROLE = "national officer"` is handed to anyone whose
>    `user_audience` is `NATOFF` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â one guide beats eighteen near-identical ones, and beats the Grand
>    Regent having none at all. It drops away under "hide national officer functionality" for free,
>    because `user_audience` already reads the toggle. A guide for a national role also renders a
>    second **National officer tools** list: the ~29 `natoff` features no role tags, previously
>    unreachable from any guide.
>    - Same commit fixed a real bug: `get_role_guide_detail` matched `feature.roles` directly, so the
>      Audit (tagged by `Task.owner`, not by `roles`) was missing from four of the five chapter-officer
>      guides. It now uses `feature_roles(feature, task_owners)`, the same derived set the catalog
>      chips use.
> 3. **The catalog is an accordion.** Sixteen areas collapsed on arrival, per-area tallies that follow
>    the filters, and an Expand all / Collapse all toggle. The chips and the search box **drive** the
>    accordion ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a filter that matched inside a closed panel used to look like it had done nothing.
>    `catalog.js` remembers which panels *it* opened so clearing a filter never closes one you opened
>    yourself. `#area-<key>` deep links open their panel, on load and on `hashchange`.
>    - The markup contract is now: `#tt-catalog-expand`, `[data-catalog-panel]`, `[data-catalog-tally]`
>      ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â all optional, because `forms/landing.html` shares this script with plain sections.
> 4. **`email-preferences` pointed at the wrong thing** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it described the per-email unsubscribe link
>    as the only route. It now points at `users:detail#email_prefs`; `user_detail.html` already had an
>    `openAccordionFromHash()` IIFE, so the fragment opens the right panel with no template change.
> 5. **Chapter detail links its region.** `RegionDetailView` is `LoginRequiredMixin` only, so any
>    member may open it; the `{% else %}` branch keeps the plain-text form when a region has no slug.
>
> **Gotcha for browser QA:** `page.goto(url + "#fragment")` from the same URL does *not* reload, so
> hash-driven JS never re-runs. Use `page.reload()`.

> ## Two wrong destinations in the registry (2026-08)
>
> Both entries reversed cleanly and answered GET, so every loader check passed them ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the problem was
> that neither *destination* was the thing being described. Full suite after: **2570 passed.**
>
> - **`workflow-task-inbox`** pointed at `viewflow:index` (`/workflow/`). Nothing else in the app
>   links there and it 302s to the login page even for a superuser, so the card was a dead end for
>   every reader. Repointed at `tasks:list#process-reminders` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `TaskListView.get_context_data`
>   already builds a `SignTable` of pending discipline / convention / resignation / OSM signatures and
>   renders it as **Chapter Process Reminders** above the task table, which is where a chapter officer
>   genuinely sees this. Added the matching `id` to `tasks/task_list.html`.
> - **`roll-book-page`** had no URL at all and told the reader to open one "from the member's record".
>   There *is* a direct route: Forms ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Initiation/Depledge selection (`forms:init_selection`), set the
>   candidate's status to **Roll Book**, and the next step lists them with a per-member page and a
>   download-all ZIP (`forms:roll_book_download_all`).
>
> **Rule learned ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â reversing is not reaching.** `test_registry_loader.py` verifies a `url_name`
> reverses, that the view answers GET, and that a `url_fragment` names a real `id=`; none of that
> notices an authorization wall. Superuser-only tooling stays out of the registry by convention
> (`DOCUMENTED_EXCLUSIONS` in `forms/tests/test_landing.py`, alongside `awards:import_upload`), and
> `test_no_feature_links_the_viewflow_frontend_inbox` now keeps it out.

> ## The forms landing gets the catalog's shell (2026-08)
>
> Full suite after: **2577 passed, 17 skipped** (`awards/tests/test_directory.py::test_filter_by_region`
> is a known order-dependent flake; it passes on its own).
>
> The catalog had already earned its accordion + chip filter, and `/forms/` was still the flat wall of
> five tables it shipped as. Rather than write a second script, `static/js/catalog.js` now drives both
> pages ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â every hook it looks for is optional, so each page opts in to the parts it wants.
>
> - **`FORM_GROUPS` gained a `chip`** beside `label`. The labels are sentences ("Members joining,
>   changing and leaving"); a filter button has to fit on one line ("Membership"). The fallback
>   "other" group is built inside `get_feature_groups` and has no `chip`, hence
>   `{{ group.chip|default:group.label }}`.
> - **Each group is an `accordion-item`, closed on arrival**, keeping its old `id="forms-<key>"` so
>   existing deep links still land. No `data-bs-parent`, so several can be open at once.
> - **"For your role" is the one panel the filters do not filter.** It indexes the viewer's duties, not
>   search results, so it is deliberately *not* a `.tt-catalog-section` and holds no
>   `.tt-catalog-card`s: the counts skip it, and a text or area filter **hides** it rather than
>   emptying it. Only the "Only show forms for my roles" switch opens it ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â which is what the user
>   asked for, and is also the only filter it can honestly answer. Expand/Collapse all still covers it
>   (`collapsibleSections()`).
>
> **New-officer email.** The welcome mail already fired per member on election and already linked the
> reader's role guide (TWI-12); the gap was that it never mentioned the catalog. `NewOfficers.context`
> now carries `catalog_url` and `forms_url`, and both `herald/html/officer_new.html` and
> `herald/text/officer_new.txt` render them ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **edit both or half your readers see nothing.** A test
> renders the real bodies, because context alone proves nothing about what a template does with it.
>
> **"The member won't show up in the officer autocomplete" is the rule working.** Both add forms
> forward `exclude_self=true` and `clean_user` calls `_reject_self`, so you cannot appoint yourself and
> you are simply absent from your own results. The national page already carried a note saying so ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but
> a note above the form does not connect to a name missing from a dropdown, which is why it was read as
> a data bug. Both `user` fields now carry `help_text` at the point of confusion. (Locally, user pk=1
> **is** `test@gmail.com`, the login itself ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â hence the report.)

> **Status:** all eight open decisions are **resolved** (see *Resolved Decisions* at the end) and are
> reflected throughout. App name is **`guides`** (`thetatauCMT/guides/`). Announcements are **merged**
> into What's New via a shared `UserAcknowledgement`. The Google-Doc help page is **replaced**, not
> preserved. TWI-9b (Forms landing rebuild) is **committed work**, not a proof of concept.
> **TWI-1 is delivered and signed off** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â [docs/specs/feature-inventory.md](docs/specs/feature-inventory.md).
> All Section A findings are resolved; awards are now member-only and `finances:chapters` is
> chapter-scoped. **TWI-2 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `thetatauCMT/guides/` exists with `FeatureArea` + `Feature`,
> migration `0001_initial`, admin, and 27 model tests. **TWI-3 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `guides/services.py`
> holds the five visibility functions every surface calls (38 tests); `get_whats_new`/`acknowledge`
> move to TWI-6 and `get_role_guides` to TWI-12, with their models. **TWI-4 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Driver.js
> 1.8.0 is vendored, `static/js/tours.js` runs tours from a `json_script` payload, and the popover is
> themed for light *and* dark (7 asset/template tests + documented browser validation).
> **TWI-5 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `TourStep` + `UserTourCompletion`, `services.get_tour_config()` serializes an
> area's filtered steps into the runner's payload, `base.html` emits it, and
> `POST /features/tour/<key>/complete/` records the outcome (30 tests).
> **TWI-6 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â announcements and new features now share one dismissible feed
> (`UserAcknowledgement`, `services.get_whats_new`/`acknowledge`, a once-per-session modal in
> `base.html`, `/features/ack/` and the `/features/whats-new/` archive, and a rebuilt home page);
> the catalog `NEW` badge moves to TWI-9 since no catalog page exists yet (62 tests).
> **TWI-7 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â 24 `data-tour` anchors across `base.html`, `pages/home.html` and
> `forms/landing.html`; `TourStep.clean()` now rejects any selector that is not `[data-tour="key"]`;
> `docs/specs/tour-anchors.md` is the anchor register and is test-checked against the templates in both
> directions (34 tests). `catalog-search`/`catalog-area` are reserved for TWI-9 and `role-guide-card`
> for TWI-12, since their pages do not exist yet.
> **TWI-8 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `guides/fixtures/feature_registry.json` now describes the whole application
> (16 areas, 122 features, 17 tour steps across 5 toured areas), `manage.py load_feature_registry`
> upserts it by `key` with `--dry-run` and deactivate-never-delete, and `dbseed` calls it (35 tests).
> **TWI-9 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `/features/` renders the registry grouped by area with `NEW` badges, duty-role
> chips, client-side search/filter and per-area tour launchers; anonymous visitors get the public area
> plus a sign-in prompt instead of a 302 (21 tests).
> **TWI-9b is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `forms:landing` is now rendered from the registry (`FORM_GROUPS` +
> `services.get_feature_groups`), with a pre-rebuild URL snapshot test so no form can silently vanish
> (13 tests).
> **TWI-12 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `RoleGuide` + `RoleGuideStep`, `/features/role/<slug>/`, live open items from
> `TaskDate`, and entry points on the home page, the account menu **and the new-officer email** (23 tests
> + 3 notification tests).
> **TWI-10 is delivered bar one bullet** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `pages/help.html` no longer iframes the Google Doc; the hub
> offers the four entry points and the `?` icon launches the current area's tour directly when one
> exists. The "What's this page for?" empty-state links are **not built** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see TWI-10 below.
> **TWI-13 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `role_guide_viewed` joins the existing PostHog events, and
> [docs/specs/feature-registry.md](docs/specs/feature-registry.md) documents the fixture, the loader and
> every event; `docs/management_commands.md` links to it.
> **TWI-11 is delivered** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `manage.py seed_guides_demo` manufactures the time-sensitive state a fresh
> DB lacks (5 tests) and [docs/specs/guides-qa.md](docs/specs/guides-qa.md) is the manual verification
> script.
> **The plan is complete bar one TWI-10 bullet** (the empty-state links). Full suite: 2632 passed,
> 17 skipped, 0 failed.

## Shared Preamble (paste once per session)

Project conventions for all Feature Discovery work items:

- **Stack:** Django 4.2 + PostgreSQL 12 in Docker containers (service `django`, container
  `thetataucmt_local_django`). Reuse existing app patterns, base templates, nav structure,
  and permission helpers. Apps live under `thetatauCMT/<app>/`; shared helpers under `core/`.
- **Audiences vs. roles (see "Role model reality" below):** every surface must be
  audience-filtered ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a user must never see catalog entries, tour steps, or announcements
  for functionality they cannot reach.
- **Working style:** Prefer configuration over hard-coded content. Start with
  migrations/models FIRST (pause for confirmation), then services, then views/templates,
  then tests by acceptance criterion.
- **Front end:** No inline `<script>` blocks in new work. Pass data to JS via Django's
  `json_script` and load behavior from external static JS files.
  *Correction to the original plan:* the app does **not** currently enforce CSP ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
  [config/settings/production.py](config/settings/production.py) sets
  `CONTENT_SECURITY_POLICY_REPORT_ONLY` with `'unsafe-inline'` and `'unsafe-eval'` in
  `script-src`, and `base.html` already ships two inline `<script>` blocks (theme bootstrap,
  PostHog). Keep the `json_script` discipline anyway so this feature does not add new debt
  when the header flips to enforcing ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but do not claim CSP breakage as a blocker.
  Vendored assets under `static/` are already covered by `script-src 'self'`; no new
  CSP entry is needed if we avoid a CDN.
- **Tour library:** Driver.js (vanilla JS, framework-agnostic), vendored into
  `thetatauCMT/static/vendor/driverjs/` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â do NOT rely on a CDN. v1.x IIFE build exposes
  `window.driver.js.driver`, called as `driver({...}).drive()`.
- **Already available globally** (from [thetatauCMT/templates/base.html](thetatauCMT/templates/base.html)):
  Bootstrap 5.3.3 bundle (`window.bootstrap`, includes Popper), jQuery 3.6.4, Font Awesome 6.7.2,
  and PostHog (authenticated + non-DEBUG only). **There is no HTMX in this project** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â drop the
  `htmx:afterSwap` requirement from the original plan. The dynamic surfaces that actually matter
  are Bootstrap dropdowns/offcanvas (see TWI-4) and django-plotly-dash panels.
- **Dark mode exists** (`data-bs-theme` on `<html>`, persisted in `localStorage['tt-theme']`).
  Any new UI ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â catalog cards, tour popovers, What's New modal ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â must be legible in both themes.
  Driver.js's default popover is hard-coded light; a small dark-mode override is required.
- **Tests:** pytest inside the container ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
  `docker exec thetataucmt_local_django pytest <path> -v --tb=short`. Baseline ~1065 passing.
  Use the existing `auto_login_user` fixture and per-app `tests/factories.py`.

### Problem statement (what we are solving)

Two distinct problems, and the original plan only addressed the first:

1. **Discovery** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â users "don't know everything the application can do," and we have no way to
   introduce new functionality when it ships.
2. **Officer onboarding** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a newly elected Regent/Treasurer/Scribe does not know *what they are
   responsible for* or *when*. This is a different question from "what can the app do," and it is
   the one with the highest cost of failure (missed audits, unsubmitted NME programs, unsigned RMP).

Individual pages are mostly simple forms and do not need walkthroughs. The goal is orientation,
not hand-holding.

### Architecture (revised)

One admin-manageable **Feature Registry** drives **four** surfaces:

| Surface | User question | Implementation |
|---|---|---|
| **Feature Catalog** | "What can the CMT do?" | Permanent, searchable, audience-filtered `/features/` page grouped by area |
| **Role Guide** | "I'm the new Treasurer ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â what am I responsible for?" | Per-role page joining registry entries + the *existing* `tasks.Task` rows keyed by `Task.owner` |
| **Area Tour Chapters** | "Show me how this works" | Short (3ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“6 step) opt-in Driver.js tours, one per feature area |
| **What's New** | "What changed since I was here?" | **Unified, per-user-dismissible feed** merging registry release metadata *and* `announcements.Announcement` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see the merge design in TWI-6 |

**Decision applied:** the existing `announcements.Announcement` is **not** kept separate. Announcements
and newly released features share one acknowledgement mechanism so a user can dismiss either and never
see it again. Details in **TWI-6** and **UserAcknowledgement**.

**Explicitly out of scope for this phase:** a single long cross-page chained tour that navigates the
user between pages while persisting server-side tour state. Tours are per-area chapters. Design the
models so a future chained "full tour" remains possible, but do not build the cross-page resume
machinery now.

**Content source:** the registry is seeded from an **in-repo JSON fixture** (matches repo convention ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
see `thetatauCMT/*/fixtures/*.json` and `configs/management/commands/dbseed.py`) that is
version-controlled and maintained by developers; admin editing remains possible for copy tweaks.
The fixture must be authored only AFTER a full audit of the application's functionality ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see TWI-1.

---

## Codebase Review ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â what already exists (do not duplicate)

This section is the main gap the original plan had: several of these surfaces already exist in
partial form and must be **absorbed**, not rebuilt alongside.

| Existing thing | Where | Implication for this work |
|---|---|---|
| **Officer task system** | [thetatauCMT/tasks/models.py](thetatauCMT/tasks/models.py) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `Task` (`owner` = a role from `ALL_ROLES_CHOICES`, `type`, `days_advance`, `resource`, `description`), `TaskDate` (per-`school_type` due dates, `archived`), `TaskChapter` (completion) | **This is already the "what must I do" engine.** The Role Guide (TWI-12) must render from it, not invent a parallel checklist. `Task.render_task_link` already resolves `resource` to a URL. |
| **Home dashboard** | `core.views.HomeView` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ [thetatauCMT/templates/pages/home.html](thetatauCMT/templates/pages/home.html) | Already shows Announcements + incomplete `TaskDate` table + embedded `RegionDashboard`. This is where a `NEW` badge / "Your role" card belongs ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no new landing page. |
| **Announcements** | [thetatauCMT/announcements/models.py](thetatauCMT/announcements/models.py) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `Announcement(content CKEditor, priority, publish_start/end)` rendered on home for **everyone, always, with no dismiss** | **Decision: merge.** Announcements gain audience/role targeting and per-user acknowledgement, and share the What's New surface with newly released features. See TWI-6. |
| **Forms landing page** | [thetatauCMT/templates/forms/landing.html](thetatauCMT/templates/forms/landing.html) | A hand-maintained ~25-row HTML table of forms, each with a name, description, and a natoff-only "All Chapters" column. **This is already a hard-coded feature catalog**, and users have said it is *not useful*. Rebuilding it from the registry is committed work ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see TWI-9b. |
| **Help page** | `path("help/", TemplateViewÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦)` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ [thetatauCMT/templates/pages/help.html](thetatauCMT/templates/pages/help.html) | Today it is a single `<iframe>` to a **badly out-of-date** published Google Doc. **Decision: this work replaces it.** The `?` icon in the nav (visible to anonymous users too) becomes the entry point for everything built here. See TWI-10. |
| **Feature flags** | `configs.Config.feature_enabled()` + `thetatauCMT/utils/context_processors.py` `feature_flags()` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `feature_awards_enabled`, `feature_jobs_enabled`, `feature_events_calendar_enabled` | **The original plan never mentions these.** The catalog will advertise switched-off features unless `Feature` carries an optional `feature_flag` key checked through `Config.feature_enabled`. |
| **Seed guard** | `core.seed_guard.ensure_seeding_allowed(force)` | TWI-11's QA seed must call this rather than re-implementing a DEBUG check. |
| **Analytics** | PostHog in `base.html`, already identifying `officer` / `natoff` / `role` / `chapter` | Free instrumentation for "did this actually help?" ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â emit catalog/tour/What's-New events. |
| **Nag pressure already on the page** | `core.middleware.RMPSignMiddleware` force-redirects unsigned users to `rmp` and pushes ERROR messages; it also nags chapter officers about the NME program | A What's New modal stacked on top of a blocking compliance redirect is exactly the annoyance to avoid. See the suppression rules in Design Rules. |

### Role model reality (the biggest correction)

The original plan's `roles = ["member", "officer", "rd", "natoff", "admin"]` does not match the codebase.
There are **two orthogonal concepts**, and conflating them into one field will produce both leaks and
useless targeting.

**1. Audience = can this user *reach* the page.** Driven by Django groups + mixins. Because there are
very few admins and no appetite for admin-only discovery surfaces (resolved decision #6), the catalog
uses a **4-value enum**, not the full six-mixin ladder:

| Audience value | Enforced in code by | Service test |
|---|---|---|
| `public` | no mixin (e.g. `UserBadgeLookupView`, `UserLookupSearchView` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â both plain `FormView`) | ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â |
| `member` | `core.views.LoginRequiredMixin` | `user.is_authenticated` |
| `officer` | `OfficerRequiredMixin` (`group_required = ["officer", "natoff"]`) | `user.is_officer_group` |
| `natoff` | `NatOfficerRequiredMixin` **or** `NationalOfficerRequiredMixin` | `user.is_national_officer_group or core.models.user_is_national_officer(user)` |

**Collapsed deliberately:** `NatOfficerRequiredMixin` (natoff group only) and
`NationalOfficerRequiredMixin` (superuser **or** natoff group **or** a `NAT_OFFICERS` role) differ, but
the difference is immaterial for *discovery* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â use the more permissive union so a National Officer who
holds the role but is not in the group still sees what they can reach. `SuperuserRequiredMixin` views
(Report Builder, award import queue, Config admin) are **excluded from the catalog as internal tooling**
per resolved decision #6.

**2. Duty role = what this user is *responsible for*.** Granular slugs from `core.models`:
`CHAPTER_OFFICER` (5: regent, vice regent, scribe, treasurer, corresponding secretary),
`CHAPTER_OFFICER_REQUIRED` (+ pledge/new member educator, risk management chair),
`COMMITTEE_CHAIR` (~24), `ADVISOR_ROLES` (4), `COUNCIL` (8), `NATIONAL_OFFICER` (10),
unioned as `ALL_ROLES` / `ALL_ROLES_CHOICES`.

> **Key insight the plan was missing:** permission audience ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â  duty role. A *Risk Management Chair* is
> a plain `member` for gating purposes but owns the H&S Education Program. A *committee chair* is not
> in the `officer` group. So role-based **guidance** must be modelled separately from role-based
> **permission** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â and `tasks.Task.owner` already uses exactly this `ALL_ROLES_CHOICES` vocabulary,
> so the Role Guide joins to it for free.

**Two impersonation mechanisms must be honored by the visibility service:**

- `natoff_hidden` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a National Officer can toggle "Hide national officer functionality" to preview the
  site as a member (`users:toggle_natoff`). Use `user.is_national_officer_group` /
  `request.is_nat_officer` (which respect the toggle), **never** `user.in_national_officer_group`
  (raw group membership). Getting this wrong leaks natoff catalog entries into member preview.
- `UserAlter` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a natoff can impersonate another chapter *and role*. `user.chapter_officer()` already
  applies the alteration; use it rather than reading `current_roles` directly.

> ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â **Critical scoping note (retained):** Attendance, Volunteer Nominations, Awards, and
> Events/Calendar are only a SUBSET of this application. The inventory below found **~200 named URLs
> across 25 apps and 14 Viewflow flows.** The fixture must cover the entire system.

---

## Target Data Model (revised)

> **App placement:** new app `thetatauCMT/guides/` (covers catalog + tours + role guides).
> Alternative considered: folding into `configs` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â rejected, `configs` is the key/value settings
> store and mixing content models into it muddies `dbseed`.
> Reuse `core.models.TimeStampedModel` (already used by `Announcement`) for audit timestamps.

### Shared field conventions

- `audience` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `CharField(choices=AUDIENCE_CHOICES)`, single value, one of
  `public | member | officer | natoff`. Mirrors the mixin used by the real view (table in "Role model
  reality"). **Single value, not a list** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the audiences are a strict hierarchy in this codebase
  (`officer` group includes `natoff`), so a list invites contradictions.
  `public` is reserved for the small **"Getting in"** set only (resolved decision #4).
- `roles` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `JSONField(default=list, blank=True)`, values validated against
  `core.models.ALL_ROLES`. **Duty-role targeting only** ("this is a Treasurer thing"). Empty = not
  role-specific. Never used for access control.
- `feature_flag` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `CharField(max_length=50, blank=True)`; when set, the entry is hidden unless
  `configs.models.Config.feature_enabled(feature_flag)` is true. Known keys today: `FEATURE_AWARDS`,
  `FEATURE_JOBS`, `FEATURE_EVENTS_CALENDAR`.

### FeatureArea (TWI-2)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| key | SlugField (unique) | e.g. `events-attendance`, `finances`; stable fixture identity |
| name | CharField(100) | Display name |
| description | TextField | Shown at top of catalog section |
| icon | CharField(50, blank) | Font Awesome 6 class, e.g. `fa-solid fa-calendar-days` (FA6 is already loaded) |
| order | PositiveSmallInteger | Catalog display order |
| audience | CharField(choices) | Minimum audience to see the area at all |
| feature_flag | CharField(50, blank) | See conventions above |
| has_tour | Boolean | Whether a tour chapter exists |
| tour_entry_url_name | CharField(200, blank) | URL name where this area's tour begins |
| is_active | Boolean | Hide without deleting |

### Feature (TWI-2)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| area | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ FeatureArea (`related_name="features"`) | |
| key | SlugField (unique) | Stable identifier used by the fixture |
| name | CharField(150) | |
| short_description | CharField(300) | Catalog card copy |
| long_description | TextField (blank) | Expanded/help copy |
| url_name | CharField(200, blank) | Deep link target. **Must support namespaces incl. Viewflow** (`viewflow:forms:hseducation:start`) |
| external_url | URLField(500, blank) | For features that live outside Django (Vector LMS, the national training portal). **Mutually exclusive with `url_name`** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â enforced in `clean()` |
| url_kwargs | JSONField (default dict) | Static kwargs **plus dynamic tokens** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see below |
| audience | CharField(choices, blank) | Blank = inherit from area |
| roles | JSONField (default list) | Duty-role targeting; drives the Role Guide |
| feature_flag | CharField(50, blank) | Blank = inherit from area |
| task | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `tasks.Task` (null, blank, `SET_NULL`) | Links a catalog entry to the recurring obligation that already exists |
| order | PositiveSmallInteger | Order within area |
| released_at | Date (null) | Drives What's New |
| release_version | CharField(20, blank) | e.g. `2026.03` |
| is_highlighted | Boolean | Show `NEW` badge |
| is_active | Boolean | |

**Dynamic URL kwargs ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a gap in the original plan.** The most link-worthy pages take arguments that
depend on the viewer, so a static `url_kwargs` dict cannot express them. Support a small token
vocabulary resolved per-request in `resolve_feature_url(feature, user)`:

| Token | Resolves to | Fails safely when |
|---|---|---|
| `@chapter_slug` | `user.current_chapter.slug` | user has no chapter |
| `@region_slug` | `user.current_chapter.region.slug` | chapter or region is `None` |
| `@username` | `user.username` | never |

Real examples requiring this: `chapters:detail` (slug), `regions:detail` / `regions:dashboard` /
`regions:officers` / `regions:advisors` / `regions:tasks` (slug), `users:profile` (username).
Static kwargs still work for things like `submissions:add-direct` (a `ScoreType` slug).
Any unresolvable token or `NoReverseMatch` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ return `None`, render a non-linked card. Never raise.

### RoleGuide + RoleGuideStep (TWI-12 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â new)

The officer-onboarding surface. Keyed on the same role vocabulary as `tasks.Task.owner`.

**RoleGuide**

| Field | Type | Notes |
|---|---|---|
| role | CharField(50, unique, choices=`ALL_ROLES_CHOICES`) | e.g. `treasurer`, `risk management chair`, `regional director` |
| title | CharField(150) | "Treasurer ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â what you're responsible for" |
| summary | TextField | 2ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“4 sentence orientation |
| order | PositiveSmallInteger | |
| is_active | Boolean | |

**RoleGuideStep** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â an ordered "first things to do" list; each row is either free-form copy, a pointer
to a `Feature`, or a pointer to a recurring `tasks.Task`.

| Field | Type | Notes |
|---|---|---|
| guide | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ RoleGuide (`related_name="steps"`) | |
| order | PositiveSmallInteger | |
| title | CharField(200) | |
| body | TextField (blank) | |
| feature | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Feature (null, blank) | "Take me there" |
| task | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `tasks.Task` (null, blank) | Renders live due dates + completion for the viewer's chapter |
| cadence | CharField(choices, blank) | `once` \| `each_term` \| `annual` \| `ongoing` |

### TourStep (TWI-5)

| Field | Type | Notes |
|---|---|---|
| area | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ FeatureArea (`related_name="tour_steps"`) | Steps belong to an area chapter |
| feature | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Feature (null, blank) | Optional link back to a catalog entry |
| order | PositiveSmallInteger | Step sequence within the chapter |
| selector | CharField(200, blank) | `[data-tour="ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"]`; BLANK = centered modal step (no element) |
| title | CharField(200) | |
| body | TextField | |
| side | CharField(10, blank) | top / right / bottom / left |
| align | CharField(10, blank) | start / center / end |
| audience | CharField(choices, blank) | Optional per-step audience gating; blank = inherit area |
| roles | JSONField (default list) | Optional per-step duty-role gating |
| feature_flag | CharField(50, blank) | Skip the step when the flag is off |
| url_name | CharField(200, blank) | Page this step belongs to (for future chaining) |

### Announcement changes (TWI-6) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â resolved decision #2

Extend the existing `announcements.Announcement` rather than building a parallel system. Additive
fields only; all defaults preserve today's behavior.

| Field | Type | Notes |
|---|---|---|
| audience | CharField(choices, default `member`) | Default = current behavior (every signed-in user). Lets an announcement be aimed at officers or natoff only. |
| roles | JSONField (default list, blank) | Optional duty-role targeting, e.g. treasurers only |
| dismissible | Boolean (default True) | Set False for a compliance notice that must stay pinned |
| feature | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `guides.Feature` (null, blank, `SET_NULL`, string ref `"guides.Feature"`) | Optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â links the announcement to the feature it is about, so "Show me" can launch that area's tour |

`announcements` gains a string-referenced FK to `guides`; `guides` must **not** import from
`announcements` at module level.

### UserAcknowledgement (TWI-6) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â replaces `UserFeatureSeen`

One acknowledgement table for **both** `Feature` and `Announcement`, so "Got it" behaves identically
wherever it appears and there is a single dismiss endpoint. `GenericForeignKey` is already an
established pattern here (`tasks.TaskChapter.submission_object`).

| Field | Type | Notes |
|---|---|---|
| user | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `settings.AUTH_USER_MODEL` (`related_name="acknowledgements"`) | |
| content_type | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `ContentType` | Limited to `guides.feature` and `announcements.announcement` |
| object_id | PositiveInteger | |
| target | GenericForeignKey(`content_type`, `object_id`) | |
| source | CharField(choices, blank) | `modal` \| `badge` \| `visited` \| `bulk` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â how it was acknowledged; feeds TWI-13 metrics |
| acknowledged_at | DateTime (auto_now_add) | |

*Unique together: (user, content_type, object_id); index on (user, content_type).*

**Query shape (keeps it bounded):** build the candidate `Feature` and `Announcement` id lists from the
registry / publish windows, then run **two** `values_list("object_id", flat=True)` queries ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â one per
content type ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â to subtract what the user already acknowledged. Never filter through the GFK.

This is the highest-volume table here (users ÃƒÆ’Ã¢â‚¬â€ announced items). Add a maintenance command that prunes
rows whose target is deactivated or whose `publish_end` is long past.

### UserTourCompletion (TWI-5)

| Field | Type | Notes |
|---|---|---|
| user | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `settings.AUTH_USER_MODEL` | |
| area | FK ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ FeatureArea | |
| status | CharField(choices) | `completed` \| `dismissed` |
| completed_at | DateTime (auto_now) | |

*Unique together: (user, area). Use `update_or_create` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a user may dismiss then later complete.*

## TWI-1 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Full application functionality audit (prerequisite, read-only)

**Work item:** Produce a complete inventory of the application's user-facing functionality. This is a
DISCOVERY task ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â make no code changes.

**Status: DELIVERED and signed off.** The artifact is
[docs/specs/feature-inventory.md](docs/specs/feature-inventory.md): ~205 named routes examined, 118
INCLUDE, ~87 EXCLUDE-with-reason, all 14 flows mapped, all uncertain gating resolved by reading each
view class. All six Section A findings are ruled on (see "Audit findings" below).

Inventory sources (all confirmed present in this repo):

- `config/urls.py` plus `thetatauCMT/<app>/urls.py` for 25 apps ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ~200 named routes.
- View gating: `core.views.{LoginRequiredMixin, OfficerRequiredMixin, NatOfficerRequiredMixin,
  NationalOfficerRequiredMixin, SuperuserRequiredMixin}` and per-view `dispatch`/`test_func` overrides.
- Nav reachability: [thetatauCMT/templates/base.html](thetatauCMT/templates/base.html) (Chapter / Members /
  Activity / Forms / Job Board / National dropdowns, the region bar, and the account menu) plus
  [thetatauCMT/templates/forms/landing.html](thetatauCMT/templates/forms/landing.html).
- Viewflow flows ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **14 flows, verified against `flows.py`**: `PrematureAlumnusFlow`,
  `InitiationProcessFlow`, `ConventionFlow`, `PledgeProcessFlow`, `OSMFlow`, `AlumniExclusionFlow`,
  `DisciplinaryProcessFlow`, `ResignationFlow`, `ReturnStudentFlow`, `PledgeProgramProcessFlow`,
  `HSEducationFlow` (all `forms`), `AwardNominationFlow` (`awards`), `NominationFlow` (`nominations`),
  `MemberUpdateFlow` (`users`).
  ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â The earlier draft of this list was wrong: there is no `RiskManagement` flow (RMP is an ordinary
  form) and status changes are **not** a flow (6 reason variants of an ordinary `CreateView`).
  Start URLs are `viewflow:<ns>:<flow>:start`, **except** `InitiationProcessFlow`, `PledgeProcessFlow`,
  and `MemberUpdateFlow`, which begin with `flow.StartFunction` and therefore have **no reversible
  `:start` URL** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â their catalog entries must point at the ordinary view that kicks them off.
  Human task nodes are reviewer-facing but live at per-task URLs that cannot be reversed generically;
  catalogue the task inbox once instead.
- Management commands with user-visible effects (~40 under `thetatauCMT/*/management/commands/`) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â e.g.
  `award_digest`, `job_search_notify`, `remind_workflow_tasks`, `monthly_chapter_officer_email`,
  `officer_update_reminder_email`, `region_officer_reminder_digest`, `nomination_follow_up`,
  `grad_anniversary_email`. These are not catalog *entries* but they explain "why did I get this email?"
  ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â capture them so the catalog copy can reference them.
- Feature flags: `FEATURE_AWARDS`, `FEATURE_JOBS`, `FEATURE_EVENTS_CALENDAR`
  (`configs/fixtures/feature_flags.json`).

**Deliverable:** `docs/specs/feature-inventory.md` with columns:
`Area | Feature key | Name | URL name | url_kwargs | Audience | Duty roles | Feature flag | Short description | Include? / Exclude reason`

### Proposed FeatureAreas (16) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â starting point for review

| # | key | Covers | Notes |
|---|---|---|---|
| 0 | `getting-in` | **The only `public` area** (resolved decision #4): sign in, find my username / badge number (`users:badge_lookup`), reset my password (`password_reset`), update my info without signing in (`users:lookup_search` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `lookup_select` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `update`) | ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â Inventory correction: `UserBadgeLookupView`, `UserLookupSearchView`, `UserLookupSelectView`, and `UserLookupUpdateView` are all plain `FormView` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **no login required**. An earlier pass mislabelled them `natoff`. |
| 1 | `getting-started` | Home, announcements, my profile, edit my info, profile picture, 2FA, terms | Audience `member` |
| 2 | `my-chapter` | Chapter home, chapter directory, chapter activity, chapter/member notes, chapter scores | |
| 3 | `roster-members` | Roster, GPAs, service hours, external orgs, member profile, member search + lookup/update review | Search/review are `natoff` |
| 4 | `events-attendance` | Events CRUD, event detail, calendar, iCal feeds + subscriptions, RSVP, attendance roster/bulk/guest/rollup, national upload, match queue, pending event reviews | Calendar gated by `FEATURE_EVENTS_CALENDAR` |
| 5 | `tasks-goals` | Task list + complete, Goals/objectives, Submissions | Feeds the Role Guide |
| 6 | `forms-workflows` | Forms landing + all 14 Viewflow flows, audit, bylaws, roll book, pledge form, collection referral | Largest area; needs sub-grouping in the UI (see TWI-9b) |
| 7 | `awards` | Award nomination flow, directory, type/cycle winners, member/chapter history, eligibility, export | `FEATURE_AWARDS`; the superuser import queue is **excluded as internal** |
| 8 | `volunteering` | Nominate for office, nominee consent, training, appointment, denial, nomination list | Consent view is a token link ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â not catalogued |
| 9 | `finances` | Invoices, chapter balances, audit, collection referral | |
| 10 | `training-education` | Trainings list, Vector, national training portal, H&S Education program | Two links are external |
| 11 | `jobs` | Job board list/search/add/copy/update, saved searches, approve/ban | `FEATURE_JOBS` |
| 12 | `ballots-voting` | Ballot list/create/copy/update/detail (natoff), my ballots, cast vote | |
| 13 | `contacts-communication` | Contact sync (Google/Microsoft/vCard), member email communication, message history, unsubscribe | Email tracking is `natoff` |
| 14 | `regions-national` | Region list/detail/dashboard/officers/advisors/tasks, national dashboard, all scores/balances/events, event+attendance dashboard | Mostly `natoff` |
| 15 | `surveys` | Depledge survey, general survey responses | Token links ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â catalogue the *concept*, not the URL |

**Dropped from the original 16:** `reports-exports`. Report Builder, the award import queue, and the
Config admin are `SuperuserRequiredMixin` internal tooling and are excluded per resolved decision #6.
Award CSV export stays, inside `awards`.

### RoleGuides ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â locked at 9 (resolved decision #1)

`regent`, `vice regent`, `scribe`, `treasurer`, `corresponding secretary`,
`pledge/new member educator`, `risk management chair`, `adviser`, `regional director`.

Each is a real value in `core.models.ALL_ROLES` and already used as `tasks.Task.owner`, so each guide
has live task rows on day one. **No other committee chairs in phase 1** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the model supports them
(`RoleGuide.role` accepts any `ALL_ROLES_CHOICES` value), so adding one later is a fixture edit and a
loader re-run, not a code change.

### Audit findings ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â all resolved

Full detail in Section A of [docs/specs/feature-inventory.md](docs/specs/feature-inventory.md).

1. **Awards were public** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `PagedFilteredTableView` has no `LoginRequiredMixin`
   ([core/views.py](core/views.py) line 156), so the award directory + history set was reachable signed
   out and `base.html` linked *Award Winners* anonymously. **Ruled member-only.** `AwardDirectoryView`
   and `_AwardHistoryView` now carry `LoginRequiredMixin`; the anonymous nav link is gone;
   `forms:pledgeform` stays public because prospective members have no account.
   The `public` audience is therefore **login help only**, exactly as resolved decision #4 intended.
2. **`Feature.external_url` added** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â approved; Vector LMS and the national training portal have no
   Django URL name.
3. **`awards:direct_grant` gates in `dispatch()` via `can_grant_awards`, not a mixin.** Its catalog
   audience is hard-coded `officer` so TWI-3 does not advertise it to members who would be bounced
   home. Only such case found ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no generic `visibility_check` mechanism.
4. **`forms:bill_of_rights` and `users:update_review` are public by design** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â owner confirmed, no
   change. `finances:chapters` **was** fixed: `ChapterBalancesListView` now scopes to
   `user.current_chapter` unless `user_is_national_officer(user)`. `scores:chapterlist` has the same
   shape but was deliberately left alone (scores are not sensitive).
5. **`OfficerRequiredMixin` means officer *or* natoff *or* superuser** (`group_required` returns True
   for any superuser). The `officer` audience in `guides/services.py` must match this, or visibility
   will silently narrow.
6. **`UserAlterView` / `ToggleNatoffView` intentionally use raw `in_national_officer_group`** so a
   hidden National Officer can unhide. These two are the only legitimate uses ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the visibility service
   must not copy the pattern (this is what TWI-3's regression test guards).

Still open for owner confirmation:
- Nothing. All rulings applied.

**Acceptance:** every named URL in the project is explicitly marked include-in-catalog or
exclude-with-reason. No tests (documentation deliverable). ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ met.

---

## TWI-2 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Registry models + admin

**Status: DELIVERED.** `thetatauCMT/guides/` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â [models.py](thetatauCMT/guides/models.py),
[admin.py](thetatauCMT/guides/admin.py), migration `0001_initial`, and 27 passing model tests in
[tests/test_models.py](thetatauCMT/guides/tests/test_models.py). Registered as
`thetatauCMT.guides.apps.GuidesConfig` in `LOCAL_APPS`. Full suite: 2360 passed, 17 skipped, 0 failed.

Decisions made while building, worth knowing for TWI-3:
- `key` is `SlugField(max_length=100)` on both models ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the 50-char default is tight for keys like
  `viewflow-officer-transition-guide`.
- `Feature.objects.active()` filters `is_active=True` **and** `area__is_active=True`, so deactivating
  an area hides everything inside it and callers only check one thing.
- `effective_audience` / `effective_feature_flag` properties implement the documented
  blank-inherits-from-area rule. TWI-3 should use these, never the raw fields.
- `Feature` ordering is `["area__order", "order", "name"]` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ordering by the FK id would not match
  catalog order.
- Validation lives in `clean()` (called via `full_clean()`) using the module-level `validate_audience`
  and `validate_roles` helpers. Note `loaddata` does **not** call `full_clean()`, so TWI-8's loader
  must validate explicitly.
- No `autocomplete_fields` for `Feature.task` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `tasks.TaskAdmin` defines no `search_fields`, which
  would break autocomplete. Plain select is fine at this scale.

**Work item:** Create the `thetatauCMT/guides/` app with `FeatureArea` and `Feature`
(see the Target Data Model).

- Migrations first (pause for confirmation).
- Register the app in `config/settings/base.py` `LOCAL_APPS`.
- Django admin: inline `Feature` under `FeatureArea`; list filters for area, `audience`,
  `feature_flag`, `is_highlighted`, `is_active`; search on `name`/`key`/`short_description`.
  Follow the existing admin conventions in `thetatauCMT/tasks/admin.py`.
- Validate `roles` entries against `core.models.ALL_ROLES` and `audience` against the choices in a
  model `clean()` so bad fixture data fails loudly at load time, not silently at render time.
- `key` fields are the stable identity used by the fixture ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â enforce uniqueness and treat them as
  immutable in practice.

**Tests:** create areas/features; uniqueness on keys; ordering respected; inactive excluded from
active querysets; `roles`/`audience` validation rejects unknown values; `feature_flag` persists.

---

## TWI-3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Audience/role-aware registry service

**Work item:** `thetatauCMT/guides/services.py` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the single place visibility rules live.

Provide:

| Function | Behavior |
|---|---|
| `user_audience(user)` | Returns the highest of `public` / `member` / `officer` / `natoff` the user satisfies. Must use `user.is_national_officer_group` and `user.is_officer_group` (**toggle-aware**), plus `core.models.user_is_national_officer`. Superusers map to `natoff` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â there is no `superuser` audience. |
| `get_visible_areas(user)` | Active areas whose `audience` ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¤ the user's audience **and** whose `feature_flag` (if set) is enabled. |
| `get_visible_features(user, area=None)` | Active features filtered by the feature's own `audience`/`feature_flag`, inheriting the area's when blank. |
| `resolve_feature_url(feature, user)` | Reversed URL or `None`. Resolves `@chapter_slug` / `@region_slug` / `@username` tokens; catches `NoReverseMatch` and missing chapter/region. Never raises. |
| `get_whats_new(user)` | The **merged** feed ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â visible active features released within `NEW_FEATURE_MAX_AGE_DAYS`, plus currently published visible `Announcement`s, minus everything in `UserAcknowledgement`. Returns normalized dicts (see TWI-6). |
| `acknowledge(user, items, source)` | Upserts `UserAcknowledgement` for a list of `(kind, id)` pairs; silently skips anything the user cannot see. |
| `get_duty_roles(user)` | Union of `user.chapter_officer()` (applies `UserAlter`) and `user.current_roles`, intersected with `ALL_ROLES`. |
| `get_role_guides(user)` | Active `RoleGuide`s matching `get_duty_roles(user)`. |

Do not invent a second role lookup ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â reuse `users.models.User.chapter_officer()`,
`is_national_officer_group`, `is_officer_group`, and `core.models.user_is_national_officer`.

**Tests:** anonymous sees only `public` entries; member sees only member-visible entries;
officer/natoff see progressively more; feature inherits area audience when its own is blank; a natoff
with `natoff_hidden=True` sees exactly what a member/officer sees; a `UserAlter` role change is
reflected in `get_duty_roles`; a feature whose `feature_flag` is off is excluded (toggle a `Config` row
in the test); an acknowledged item is absent from `get_whats_new`; `acknowledge` skips invisible ids
without raising; unresolvable URL returns `None` rather than erroring; `@region_slug` with a chapter
that has no region returns `None`; inactive excluded.

### Status: DELIVERED (partial by design)

`thetatauCMT/guides/services.py` + `guides/tests/test_services.py` (38 tests). Guides package now
65 tests; full suite **2398 passed / 17 skipped / 0 failed**. `black` + `flake8` clean.

**Implemented:** `user_audience`, `get_visible_areas`, `get_visible_features`, `resolve_feature_url`,
`get_duty_roles`.

**Deferred ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the models they read do not exist yet:**

- `get_whats_new(user)` and `acknowledge(user, items, source)` need `UserAcknowledgement` and the
  additive `Announcement` fields from **TWI-6**. Build them there, in the same work item as the model.
- `get_role_guides(user)` needs `RoleGuide` from **TWI-12**. Same.

Writing stubs now would only be code to delete later; the five delivered functions are the ones every
other work item actually calls.

**Build decisions worth carrying forward:**

1. **`user_audience` calls `core.models.user_is_national_officer(user)` alone for the natoff rung.**
   That helper already unions superuser + natoff group + national-officer role *and* returns `False`
   while `natoff_hidden` is on, so a separate `is_national_officer_group` check would be redundant.
   `is_officer_group` is still checked for the officer rung. The raw `in_national_officer_group` is
   never used ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a module docstring says so, because that is the leak.
2. **`_audience_allows` fails closed.** An audience value not in `AUDIENCE_RANK` is treated as
   `natoff`, so a future audience added to the enum but not the rank map hides content rather than
   exposing it.
3. **`_FlagCache`** memoizes `Config.feature_enabled` per call, so filtering a list costs one query
   per *distinct* flag instead of one per entry. The regression test asserts the query count for six
   flagged features equals the count for one (`CaptureQueriesContext`) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â an absolute
   `django_assert_num_queries` number is brittle here because the group/role lookups behind
   `user_audience` are themselves several uncached queries.
4. **`resolve_feature_url` returns `None` on any miss** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â external URL wins, then `url_name`, then
   token resolution, then `NoReverseMatch`. Callers render an unlinked card.
5. **Two planned tests were dropped as structurally impossible:** `User.chapter` and `Chapter.region`
   are both non-nullable and both slugs are auto-set in `save()`, so "`@region_slug` with a chapter
   that has no region" cannot occur. The anonymous-viewer case covers the same code path and is
   tested instead. Guards for those branches were deliberately *not* written.
6. **URL names used in tests are all real:** `chapters:detail` and `regions:detail` take `<slug:slug>`,
   `users:profile` takes `<str:username>`, and `viewflow:forms:hseducation:start` reverses with no
   kwargs (verified ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it does not use `flow.StartFunction`, unlike the initiation/pledge flows).

---

## TWI-4 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Driver.js foundation

**Work item:** Vendor and wire up Driver.js.

- Add Driver.js v1.x dist files to `thetatauCMT/static/vendor/driverjs/` (JS + CSS). No CDN.
- Include CSS in `{% block css %}` and JS in `{% block javascript %}` of
  [thetatauCMT/templates/base.html](thetatauCMT/templates/base.html), after the Bootstrap bundle
  (the tour code depends on `window.bootstrap`).
- Add a **dark-mode override** for the Driver.js popover/overlay. The app toggles `data-bs-theme` on
  `<html>`; Driver.js's default popover is hard-coded light and will be unreadable in dark mode.
  Put the override in `static/css/project.css` scoped to `[data-bs-theme="dark"]`.
- Create `static/js/tours.js` that:
  - reads its configuration from a `json_script` element (never inline JS) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â follow the existing
    pattern in [thetatauCMT/templates/awards/award_nomination_form.html](thetatauCMT/templates/awards/award_nomination_form.html),
  - normalizes the global (`const driver = window.driver.js.driver;`),
  - **defensively filters out any step whose `element` selector is not present in the DOM** before
    calling `.drive()`, and aborts silently if no steps remain,
  - exposes a manual launcher bound to `[data-start-tour]` elements,
  - POSTs completion/dismissal to the TWI-5 endpoint with the CSRF token read from the
    `csrftoken` cookie (`getCookie` helper already exists in `static/js/project.js` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â reuse it).

**Bootstrap-specific gotchas the original plan missed ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â these will break tours if unhandled:**

1. **Nav items live inside collapsed `.dropdown-menu` elements.** "Chapter", "Members", "Activity",
   "National", and the account menu are all Bootstrap dropdowns. An anchor inside a closed dropdown is
   in the DOM but has zero size ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Driver.js will highlight nothing. Before highlighting, walk
   `element.closest('.dropdown-menu')` and, if found,
   `bootstrap.Dropdown.getOrCreateInstance(menu.previousElementSibling).show()`. Close it again on
   `onDeselected`.
2. **Below the `lg` breakpoint the entire nav is inside `#mainNavOffcanvas`,** which is hidden until the
   hamburger is tapped. If the target is inside it and the offcanvas is not `.show`n, call
   `bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('mainNavOffcanvas')).show()` first
   and wait for `shown.bs.offcanvas` before positioning.
3. **The region bar can be hidden** via `body.region-bar-hidden` (`localStorage['tt-region-bar-hidden']`).
   Treat its anchors as optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the defensive filter must also drop elements with zero bounding box,
   not just missing selectors.
4. **django-plotly-dash panels render asynchronously.** Never anchor a step to dashboard internals;
   anchor to the wrapping `.tt-dashboard-wrapper` instead.

**Tests:** JS asset loads; tour runs from a `json_script` payload; missing-element and zero-size steps
are dropped without error; empty payload is a no-op; completion POST includes CSRF; no new inline
`<script>` is added to any template.

### Status: DELIVERED

Files: [thetatauCMT/static/vendor/driverjs/](thetatauCMT/static/vendor/driverjs/),
[thetatauCMT/static/js/tours.js](thetatauCMT/static/js/tours.js),
[thetatauCMT/templates/base.html](thetatauCMT/templates/base.html),
[thetatauCMT/static/css/project.css](thetatauCMT/static/css/project.css),
[thetatauCMT/guides/tests/test_tour_assets.py](thetatauCMT/guides/tests/test_tour_assets.py).
Suite: **2405 passed, 17 skipped, 0 failed**.

**1. What was vendored.** Driver.js **1.8.0**, from
`https://registry.npmjs.org/driver.js/-/driver.js-1.8.0.tgz`, into
`thetatauCMT/static/vendor/driverjs/` as `driver.js.iife.js`, `driver.css`, and `LICENSE` (MIT,
kept for attribution). The IIFE build exposes **`window.driver.js.driver`** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a nested global that
an upgrade could rename, so a test asserts on it. `driver.css` contains **no `url(...)`**, which
matters because production serves static files through `CompressedManifestStaticFilesStorage`:
a missing manifest entry raises on *every* page render, and the test settings strip whitenoise so
tests would not catch it. `collectstatic` was dry-run to confirm all four files are discovered.

**2. The `json_script` contract ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â TWI-5 needs no JS changes.** Pages emit
`{{ tour_config|json_script:"tt-tour-config" }}` and `tours.js` reads it:

```json
{
  "tours": {
    "<area-key>": {
      "name": "Events & Attendance",
      "steps": [{"element": "[data-tour='nav-activity']", "title": "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦", "body": "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦",
                 "side": "bottom", "align": "start"}]
    }
  },
  "completeUrl": "/features/tour/__area__/complete/"
}
```

A step with no `element` renders as a **centered modal step** (useful for an intro/outro).
`completeUrl` is optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â without it a tour still runs, it just is not recorded. The `__area__`
token is substituted at POST time. **TWI-5's only job on the front end is to render this payload
and supply `completeUrl`.** The POST is `multipart` with `status=completed|dismissed`,
`X-CSRFToken`, `X-Requested-With: XMLHttpRequest`, `credentials: same-origin`; failures are
swallowed so a logging outage can never block the user.

**3. Public API for later work items.** `window.ttTours.start(areaKey)` returns `true`/`false`
(`false` when the area is unknown or every step was filtered out) and `window.ttTours.has(areaKey)`.
TWI-6's "Show me" links and TWI-10's `?` button should call these, or simply carry
`data-start-tour="<area-key>"` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a delegated click handler picks that up anywhere on the page.
PostHog events `tour_started` / `tour_completed` / `tour_dismissed` fire when `window.posthog`
exists.

**4. Dark mode: Bootstrap theme variables, not a `[data-bs-theme="dark"]` block.** *Deviation from
the plan, deliberate.* Driver.js's popover uses `all: unset` plus hard-coded light colours, so every
colour has to be restated regardless. Restating them once with `var(--bs-body-bg)` /
`var(--bs-body-color)` / `var(--bs-secondary-color)` / `var(--bs-border-color)` covers **both**
themes from one rule set and cannot drift as the palette changes. Two traps: `all: unset` does *not*
reset custom properties, so `--driver-popover-font-family` can be set normally; and the arrow paints
**one** visible border side with the other three transparent, so only
`.driver-popover-arrow-side-{left,right,top,bottom}` may be recoloured ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a blanket `border-color`
turns the arrow into a square. A `border` on the popover was rejected (it opens a 1px gap at the
arrow); the vendored box-shadow already separates it from the page. Overrides live at the end of
`project.css`, which is the hand-edited source of truth (its tail already holds hand-written dark
CKEditor rules absent from the `.scss`). The vendor stylesheet is linked *before* `project.css`.

**5. The plan's zero-size filter contradicts its own container-opening rule.** Gotchas 1 and 2 say to
open a closed dropdown/offcanvas around a step's target ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but a link inside a closed dropdown has a
zero bounding box, so the gotcha-3 filter would have dropped it first. Verified in the browser: the
buried item measured `width: 0`. `isReachable()` therefore exempts any element inside a container the
runner knows how to open, and applies the zero-size test only to everything else.

**6. `#mainNavOffcanvas` is a plain `.offcanvas`, but it is not always hidden.** `navbar-expand-lg` on
the parent makes Bootstrap render it static with `visibility: visible !important` at ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¥`lg`. Testing
`classList.contains("show")` alone would make the runner pointlessly "open" a drawer that is already
visible on desktop, so opening is gated on `getComputedStyle(offcanvas).visibility === "hidden"`.
Containers opened by the runner are closed again on `onDeselected`/`onDestroyed`, and `tour.refresh()`
is called from `shown.bs.*` so Driver.js re-measures after the animation.

**7. The plan is wrong about `getCookie`.** No such helper exists in `static/js/project.js` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the
repo's only CSRF idiom is `contact_sync/sync_modal.html` reading
`input[name=csrfmiddlewaretoken]`. `tours.js` reads the `csrftoken` cookie itself, which is valid
here because `CSRF_COOKIE_HTTPONLY = False` ([config/settings/base.py](config/settings/base.py)).

**8. There is no `package.json` anywhere in the repo** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no npm, no JS build, no JS test runner. So
the plan's JS-behaviour tests cannot exist as written. Verification is 7 Python tests
(`test_tour_assets.py`: vendored files present, global name intact, no `url()` in the CSS, every page
loads all three assets via a real render, and no template inlines tour code) **plus** the manual
browser validation in note 9. If a JS runner is ever added, port notes 5/6 first ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â they are the
fragile logic.

**9. Browser-validated** against the running local stack (Bootstrap 5.3, collapsed-nav viewport):
`window.driver.js.driver` and `window.ttTours.start` resolve and `driver.css` is in
`document.styleSheets`; a step whose selector is missing is dropped (progress read "1 of 2") while the
rest of the tour runs; a step with no `element` renders centered; a step targeting a link inside the
closed offcanvas **opened the drawer** and highlighted it; a step targeting an item inside a closed
dropdown opened the menu, highlighted the right node, and closed it again; finishing restored page
state (`driverActive: false`, `offcanvasShown: false`); `[data-start-tour]` launched the right tour;
`start()` returned `false` for an unknown area and for an area whose steps were all filtered;
no page errors. Screenshots confirmed legibility in **both** light and dark.

**10. Testing gotcha for later work items.** `/help/` embeds a Google Docs `<iframe>` that never fires
`load`, so Playwright `page.goto` times out on it ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â use `/accounts/login/` with
`{ waitUntil: "domcontentloaded" }` for anonymous front-end checks. Also note `tours.js` memoizes the
config on first read, so an injected `#tt-tour-config` must be in place before the first
`start()`/`has()` call.

---

## TWI-5 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Per-area tour chapters

**Work item:** Short, opt-in tour chapters, one per feature area. See **TourStep** and
**UserTourCompletion** tables.

- Migrations first (pause).
- Serialize an area's audience/role/flag-filtered steps into Driver.js shape server-side; deliver via
  `json_script`. Serialization belongs in `guides/services.py`, not the template.
- Steps with a blank `selector` render as **centered modal steps** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â use these for narrative context so
  chapters survive an empty database.
- **Tours are opt-in only.** Never auto-launch on page load. Launch points: the catalog page
  ("Show me" per area), the Help menu, the Role Guide, and the What's New modal.
- Completion/dismissal endpoint: `POST /features/tour/<area_key>/complete/` with
  `status=completed|dismissed`, `LoginRequiredMixin`, CSRF-protected, `update_or_create` on
  (user, area). Return `JsonResponse({"ok": true})`; the JS must not block the user if it fails.
- Keep chapters to 3ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“6 steps. Anchor to persistent navigation and page furniture, **never** to specific
  database objects (a chapter with zero events must still get a clean Events tour).

**Tests:** chapter renders correct ordered steps; per-step audience/role/flag gating applied;
blank-selector steps render as modal steps; completion recorded once per user/area; dismiss-then-complete
updates the same row; POST requires login + CSRF; no template auto-launches a tour.

### Status: DELIVERED

Files: [thetatauCMT/guides/models.py](thetatauCMT/guides/models.py) (+ migration
`0002_tourstep_usertourcompletion`), [services.py](thetatauCMT/guides/services.py),
[views.py](thetatauCMT/guides/views.py), [urls.py](thetatauCMT/guides/urls.py),
[admin.py](thetatauCMT/guides/admin.py), [config/urls.py](config/urls.py),
[thetatauCMT/templates/base.html](thetatauCMT/templates/base.html),
[thetatauCMT/guides/tests/test_tours.py](thetatauCMT/guides/tests/test_tours.py) (30 tests).
Guides package: 102 tests. Suite: **2435 passed, 17 skipped, 0 failed**.

**1. `FeatureArea.has_tour` is now an editorial on/off switch, and the service respects it.** The field
existed from TWI-2 with no behaviour attached, which risked a "Show me" button that did nothing. It
now means what `is_active` means for a feature: an admin can retire a tour without deleting its steps.
The complementary rule is that **an area with zero *visible* steps is omitted from the payload
entirely**, so `window.ttTours.has(key)` can never promise a tour the runner would refuse to start.
Between the two, `has_tour` and reality cannot drift into a dead launcher.

**2. `get_tour_config(user, areas=None)` is the whole server-side surface.** It returns exactly the
shape TWI-4 specified, so no JavaScript changed in this work item. Pass `areas=[area]` to serialize a
single chapter; omit it and every visible area with a tour is included. There is deliberately **no**
`get_tour_steps()` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it would have had one caller.

**3. Gating is applied per step, not just per area.** A step is dropped when its
`effective_audience` (blank inherits the area's) outranks the viewer, when its `roles` list misses the
viewer's duty roles, or when its `feature_flag` is off. There is deliberately **no**
`effective_feature_flag` on `TourStep`: the area's flag was already checked by `get_visible_areas`
before its steps were ever fetched, so inheriting it would re-ask the same question.

**4. Two query traps, both fixed and both regression-tested.** `select_related("area")` on the step
query is *not* optional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `effective_audience` reads `step.area`, so a blank-audience step re-fetches
its area one at a time, and this payload rides along on every page that offers a tour. And
`get_duty_roles()` costs a query or two, so it is computed only when some step actually declares
`roles`. The regression test compares query counts for 1 step vs 6 rather than asserting an absolute
number (same reason as TWI-3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the group/role lookups behind `user_audience` are several uncached
queries).

**5. Blank fields are omitted from the JSON, not sent empty.** A step with no `selector` produces
`{"title", "body"}` with **no `element` key at all** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â which is precisely how the runner recognises a
centered modal step. `side`/`align` are omitted the same way. The runner tolerates empty strings, but
the payload is on every tour-bearing page, so it is kept lean.

**6. Delivery is a one-line hook in `base.html` plus a mixin.**
`{% if tour_config %}{{ tour_config|json_script:"tt-tour-config" }}{% endif %}` sits between the
Driver.js bundle and `tours.js`; `guides.views.TourConfigMixin` supplies `tour_config`. Pages that do
not mix it in render nothing. **TWI-9/TWI-10/TWI-12 only need to add the mixin to their view** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no
template work. The hook is placed outside any `<script>` block so TWI-4's
"no inline tour code in base.html" test still passes.

**7. Completion endpoint: `POST /features/tour/<slug:area_key>/complete/`, name
`guides:tour-complete`.** New `guides/urls.py` mounted at `features/` in
[config/urls.py](config/urls.py) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **TWI-9 adds the catalog page to this same module.**
`LoginRequiredMixin` + CSRF; `status` must be `completed`/`dismissed` (else 400); an unknown key *or*
one the viewer cannot see is a 404; `update_or_create` on the unique `(user, area)` pair, so
dismiss-then-complete updates one row. Returns `JsonResponse({"ok": True})`, which the runner ignores.

**8. `completeUrl` is omitted for anonymous viewers.** The endpoint is login-required, so offering the
URL to a signed-out user would only log a redirect. TWI-4 built `tours.js` to run fine without it, so
the `getting-in` public tour still works ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it just is not recorded. A test asserts the service's
`AREA_TOKEN` constant matches the literal in `tours.js`, since the two are coupled across languages.

**9. No unique constraint on `(area, order)`.** It would make swapping two steps in the admin inline
fail mid-save and would complicate TWI-8's fixture loader. Ordering is
`["area__order", "order", "id"]`, so ties still resolve deterministically.

**10. `TourStep.feature` is `SET_NULL`.** A step is narrative copy; deleting the catalog entry it
points at should not delete the tour. `UserTourCompletion` is plain `models.Model`, not
`TimeStampedModel` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it is the highest-volume table here and `completed_at` already covers it. Its
admin is registered read-only (`has_add_permission` returns `False`) because rows come from the runner.

**11. Suite flakes are pre-existing, not from this work.** Two different tests failed one run each and
passed in isolation and on re-run (`formsÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦test_audit_form_view_get_with_pk_wrong_chapter`,
`awardsÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦test_filter_by_region`). Both look like chapter/region factory collisions under
`-n auto --reuse-db`.

---

## TWI-6 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â What's New: one dismissible feed for announcements *and* new features

**Work item:** Give users a single place to learn what changed, and \u2014 critically \u2014 a way to make it go
away. Today `announcements.Announcement` renders on the home page for everyone, forever, with no
dismiss. That is the annoyance this work item fixes. See **Announcement changes** and
**UserAcknowledgement** in the data model section.

**Migrations first (`guides.UserAcknowledgement` + the four additive `Announcement` fields), then pause
for confirmation.** The `Announcement` migration touches a live, in-use table \u2014 all four fields must
have defaults that reproduce current behavior exactly (`audience="member"`, `roles=[]`,
`dismissible=True`, `feature=None`).

### The unified feed

`get_whats_new(user)` returns one ordered list of items, each normalized to
`{kind, id, title, body, url, area_key, is_dismissible}` where `kind` is `announcement` or `feature`:

- **Announcements** \u2014 currently published (`publish_start <= now <= publish_end`, honoring nulls exactly
  as the existing home page does), ordered by `priority`.
- **Features** \u2014 `released_at` within `NEW_FEATURE_MAX_AGE_DAYS` (**30**, resolved decision #5),
  ordered newest first.
- Both filtered through the **same** TWI-3 visibility service (audience + duty roles + feature flags).
  A user must never be told about something they cannot reach.
- Both subtract the user's rows in `UserAcknowledgement`.

Announcements sort above features when priority is meaningful; otherwise newest first. Cap the
unprompted surface at ~5 items with "see all" \u2192 the What's New archive.

### Where it shows

| Surface | Behavior |
|---|---|
| **Home page** | Unacknowledged items render expanded, each with a **Got it** button (resolved decision #2). Acknowledged-but-still-published items collapse behind a "Past announcements" disclosure so nothing silently disappears. `dismissible=False` items always render expanded with no button. |
| **What's New modal** | At most one per session, listing unacknowledged items. **Show me** \u2192 deep-link or launch that area's tour chapter; **Got it** \u2192 acknowledge. Dismissing the modal acknowledges everything listed in a single POST. |
| **`NEW` badges** | On catalog cards and, where feasible, the matching nav item. **Each badge carries its own dismiss affordance** (a small \u00d7, `source="badge"`) so a user can silence one item without opening the modal (resolved decision #5). Clicking "Take me there" on a card also acknowledges it (`source="visited"`). |
| **Archive page** | `/features/whats-new/` \u2014 everything visible to the user, acknowledged or not, newest first. Linked from the help hub and from "see all". |

One `POST /features/ack/` endpoint takes `[{kind, id}, ...]` + `source` and upserts
`UserAcknowledgement` rows. CSRF required; ignore ids the user cannot see (do not 403 \u2014 just skip, so a
stale page cannot spam errors).

Shipping either kind of announcement must require **no code deploy** \u2014 an admin edit or a loader run is
sufficient.

**Anti-annoyance rules (the user's explicit constraint \u2014 these are requirements, not polish):**

1. **At most one unprompted modal per session** \u2014 gate on a session key, not just the acknowledgement
   table, so a failed POST cannot cause a re-show loop.
2. **Suppress when the page is already nagging.** `core.middleware.RMPSignMiddleware` force-redirects
   unsigned users to `rmp` and pushes ERROR messages; it separately nags chapter officers about the
   NME program. Skip the modal when the request has any `messages` at `ERROR` level.
3. **Suppress on paths in `settings.TERMS_EXCLUDE_URL_LIST`**, on any `/workflow/` (Viewflow task) URL,
   on `account/*`, and on any POST request \u2014 never interrupt a form in progress.
4. **Cap the list at ~5 items**, newest first, with "see all" linking to the archive.
5. **Never re-show for the same item.** If the acknowledgement write fails, fail closed (don't show).
6. Emit a PostHog event on show / "Show me" / "Got it" / dismiss so we can measure whether this is
   helping or irritating. PostHog is already initialized with `officer`, `natoff`, `role`, `chapter`.

**Backwards-compatibility guard:** an existing `Announcement` row, untouched, must render for exactly
the same audience as it does today \u2014 only now with a **Got it** button. Write that as an explicit
regression test against a fixture built by the current `announcements` factory.

**Tests:** new visible feature triggers modal; audience-invisible feature and flag-disabled feature do
not; a `natoff`-targeted announcement is invisible to a member; "Got it" acknowledges and does not
re-show; per-badge dismiss acknowledges only that item; "Take me there" acknowledges; badge clears on
acknowledgement and on the 30-day threshold; `dismissible=False` renders without a button and cannot be
acknowledged; ack endpoint silently skips invisible ids; users with nothing new see no modal; modal
suppressed on RMP redirect, on `/workflow/` URLs, and on POST; only one modal per session; **pre-existing
announcement behavior unchanged**.

### Status: DELIVERED

Everything above shipped except the catalog-card `NEW` badge, which is **deferred to TWI-9** because no
catalog page exists yet. The badge *mechanics* are built and in use ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the home page and archive dismiss
with `source="badge"`, and "Take me there" acknowledges with `source="visited"` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â so TWI-9 only has to
render the badge and point it at the existing endpoint.

**Delivered:**

- `guides.UserAcknowledgement` (migration `0003`) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â generic FK limited to `guides.feature` and
  `announcements.announcement`, `unique_together (user, content_type, object_id)`, index on
  `(user, content_type)`, and a `source` choice set (`modal` / `badge` / `visited` / `bulk`).
- Four additive `Announcement` fields (migration `0003_announcement_audience_ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦`) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `audience`, `roles`,
  `dismissible`, `feature` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â every default reproducing today's behavior, plus a `clean()` that reuses
  the guides validators.
- `settings.NEW_FEATURE_MAX_AGE_DAYS` (30) and `settings.WHATS_NEW_MAX_ITEMS` (5), both env-overridable.
- Six new `services.py` functions ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `get_published_announcements`, `get_new_features`, `get_whats_new`,
  `acknowledge`, `whats_new_modal_allowed`, and the `_acknowledged_ids` helper.
- `guides.context_processors.whats_new`, registered site-wide.
- `AcknowledgeView`, `WhatsNewSeenView`, `WhatsNewArchiveView` at `/features/ack/`,
  `/features/whats-new/seen/`, `/features/whats-new/`.
- Templates `guides/_whats_new_item.html` (shared card), `guides/_whats_new_modal.html`,
  `guides/whats_new.html`; `base.html` includes the modal and loads `static/js/whats_new.js`;
  `pages/home.html` now renders the feed instead of a raw announcement loop.
- `manage.py prune_acknowledgements [--days N] [--dry-run]` for the ack table's long tail.
- `announcements/tests/factories.py` (new) and 62 tests in `guides/tests/test_whats_new.py`.

**Decisions made during the build (all deviations are listed):**

1. **The client sets the session key, the server doesn't.** `whats_new.js` POSTs
   `/features/whats-new/seen/` on `shown.bs.modal`. Marking it at render time would be wrong:
   `RMPSignMiddleware` calls `get_response(request)` *first*, so a page can render fully and then be
   replaced by a redirect ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â that would burn the one allowed showing on a page nobody saw.
2. **The server does set the key when the feed is empty**, so a user with nothing new stops paying for
   the query on every page for the rest of the session. Trade-off: an announcement published
   mid-session waits for the next session to trigger the modal. The home page still shows it
   immediately.
3. **The item dict has nine keys, not the seven specified** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `date` and `is_acknowledged` were added.
   `date` preserves the home page's existing "Published:" line; `is_acknowledged` lets one service call
   drive both the expanded list and the "Past announcements" disclosure.
4. **Announcements always sort above features**, ordered by the admin-set `priority` (the spec's
   "when priority is meaningful" was made unconditional ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `priority` is non-null on every row).
5. **An announcement linked to a feature the viewer cannot see is withheld entirely.** Never advertise
   a page the reader would be bounced off of.
6. **The ack endpoint accepts a plain form POST as well as JSON**, so "Got it" still works with
   JavaScript disabled. The `next` parameter is validated with `url_has_allowed_host_and_scheme`.
7. **`dismissible=False` is enforced server-side**, not just hidden in the UI, so a hand-rolled POST
   cannot silence a compliance notice.
8. **The modal lives in `base.html`**, not on the home page ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the suppression rules (`/workflow/`,
   `TERMS_EXCLUDE_URL_LIST`, POST) only make sense for a site-wide surface.
9. **`_has_error_message` peeks at `messages` storage without iterating it.** Iterating sets `used`,
   which would silently eat the queue on any render that doesn't display messages.
10. **`services._announcement_model()` imports `Announcement` lazily.** The dependency arrow is
    one-way ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `announcements` imports `guides`, never the reverse ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â so the module-level import would
    be a cycle.
11. **The archive shows currently-published announcements and in-window features only**, acknowledged
    or not. Listing expired rows would resurrect content an author deliberately retired.
12. PostHog events emitted: `whats_new_shown`, `whats_new_acknowledged`, `whats_new_visited`,
    `whats_new_dismissed`. "Show me" is already covered by `tour_started` from TWI-4.

**Verified:** guides package 162 passed; guides + announcements 168 passed; full suite **2494 passed,
17 skipped, 0 failed**; `black`/`flake8` clean; `manage.py check` clean; `makemigrations --check`
reports no pending changes; `collectstatic --dry-run` picks up `whats_new.js`.

**Browser-validated** against the running stack: the modal auto-shows once with 5 items and a
"See all 8 updates" link; dismissing wrote exactly the four dismissible rows and skipped the pinned
one; reloading showed no modal; the home page showed the pinned item plus three unacknowledged, with a
"Past announcements (4)" disclosure; an in-place "Got it" removed the card without navigating; cards
resolve to `rgb(43,48,53)`/`rgb(222,226,230)` in dark and `rgb(248,249,250)`/`rgb(33,37,41)` in light.

---

## TWI-7 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `data-tour` instrumentation

**Work item:** Add stable tour anchors to templates.

- Add `data-tour="<stable-key>"` to nav items, key dashboard regions, and primary action controls.
- **All TourStep selectors must target `[data-tour="ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"]`** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â never CSS classes or styling IDs.
  Note that `base.html` already has a few bare ids (`#help`, `#calendar`, `#theme-toggle`,
  `#region-bar-toggle`, `#log-in-link`); do not depend on them, add `data-tour` alongside.
- Minimum anchor set, derived from the actual nav:
  `nav-home`, `nav-chapter`, `nav-members`, `nav-activity`, `nav-forms`, `nav-jobs`, `nav-national`,
  `nav-calendar`, `nav-help`, `nav-account`, `region-bar`, `home-announcements`, `home-tasks`,
  `home-dashboard`, `forms-landing-table`, `catalog-search`, `catalog-area`, `role-guide-card`.
- Anchors inside `{% if %}` blocks (flags, `request.is_officer`, `request.is_nat_officer`) will legitimately
  be absent for some users ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â TWI-4's defensive filter handles that.
- Maintain the anchor list in `docs/specs/tour-anchors.md`.

**Tests:** anchors present in rendered templates for each audience that should see them; a test that
iterates every `TourStep.selector` in the fixture and asserts the `data-tour` key appears in at least one
template under `thetatauCMT/templates/` (cheap regex scan ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â catches step-authoring rot in CI).

### Status: DELIVERED

Everything above shipped except three anchors ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `catalog-search`, `catalog-area` and `role-guide-card` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
whose pages do not exist yet. They are **reserved, not stubbed**: listed in the anchors doc under
"Reserved ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â not yet anchored" (as a bullet list, deliberately not a table, so the doc-parsing test
ignores them) and deferred to **TWI-9** and **TWI-12** respectively, where the markup they name gets
written.

**Delivered:**

- **24 anchors across three templates.**
  `base.html` (20): `nav-home`, `nav-chapter`, `nav-members`, `nav-roster`, `nav-activity`, `nav-events`,
  `nav-tasks`, `nav-goals`, `nav-submissions`, `nav-forms`, `nav-jobs`, `nav-national`, `nav-calendar`,
  `nav-help`, `nav-account`, `nav-profile`, `nav-edit-info`, `nav-sign-in`, `nav-update-info`,
  `region-bar`. `pages/home.html` (3): `home-announcements`, `home-tasks`, `home-dashboard`.
  `forms/landing.html` (1): `forms-landing-table`.
- `guides.models.validate_selector` + `TOUR_ANCHOR_PATTERN`, wired into `TourStep.clean()` as a third
  validated field. Validation only ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **no migration**.
- `docs/specs/tour-anchors.md` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the rules, a one-row-per-anchor table, and the reserved list.
- 34 tests in `guides/tests/test_tour_anchors.py`.

**Decisions made during the build (all deviations are listed):**

1. **Anchors go on dropdown *toggles* for "this nav section", and separately on the individual
   `dropdown-item`s a tour might point at directly.** TWI-4's `closedDropdownFor()` keys off
   `el.closest(".dropdown-menu")`, so a toggle needs no opening and an item inside the menu gets
   auto-opened for free. Both shapes are therefore safe to author against.
2. **The `[data-tour="ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"]`-only rule is enforced in the model, not just in a test.** The plan states it
   as an authoring rule, and `TourStep.clean()` is exactly what TWI-8's loader has to call. *Format* is
   enforced at authoring time; *existence* stays a CI concern, because a template anchor can be
   `{% if %}`-gated and so is not resolvable from the database alone.
3. **The templates are the source of truth and the doc is checked against them**, in both directions ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
   `test_the_anchor_list_in_the_docs_matches_the_templates` asserts set equality, so neither an
   undocumented anchor nor a stale doc row can survive CI.
4. **The template scanner lives in the test module, not in a `guides/anchors.py`.** It has no production
   consumer today. When TWI-8's loader wants the same existence check, it moves ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â building the module
   first would be speculative.
5. **Four anchor groups beyond the plan's minimum set** were added because each is one attribute and
   each serves a known upcoming need: `nav-roster`; the four Activity items
   (`nav-events`/`nav-tasks`/`nav-goals`/`nav-submissions`) that a per-area tour will point at;
   `nav-profile`/`nav-edit-info`; and `nav-sign-in`/`nav-update-info`, which are the only anchors an
   anonymous tour could ever use (resolved decision #4 allows a signed-out "getting in" tour).
6. **A no-duplicates test was added beyond the plan.** `document.querySelector` takes the first match,
   so the same key appearing twice on one rendered page would silently move the highlight to whichever
   element sorts earlier in the DOM. Checked on the real rendered output for member and nat-officer.
7. **The anchor regex is `(?<![\w-])data-tour="ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"`.** Without the guard, the `data-start-tour="ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"`
   attribute used by the What's New templates would register as an anchor definition.
8. **The existing bare ids were left alone** (`#help`, `#calendar`, `#theme-toggle`,
   `#region-bar-toggle`, `#log-in-link`, `#udpate-info` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the last is a pre-existing typo). Anchors sit
   alongside them, per the work item; nothing depends on the ids.

**Verified:** anchor tests 34 passed; guides + forms + core 1017 passed, 11 skipped; full suite
**2529 passed, 17 skipped, 0 failed**; `black`/`flake8` clean; `manage.py check` clean;
`makemigrations guides --check` reports no changes; `git status` shows no collateral reformatting.

**Browser-validated** against the running stack: the home page renders 21 anchors with **zero
duplicates** (the four anonymous/forms-only ones correctly absent); a live tour driven through
`window.ttTours.start()` highlighted `nav-activity`, then auto-opened the Activity dropdown and
highlighted `nav-goals` at real geometry (158ÃƒÆ’Ã¢â‚¬â€31) with the popover anchored to it. Note for future
browser checks: Driver.js leaves the `driver-active-element` class on the *previous* element after the
`tour.refresh()` that follows `shown.bs.dropdown`, so assert on the expected element's `classList`
rather than on `document.querySelector(".driver-active-element")`. It is cosmetically harmless ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the
class carries no styling; the cut-out is drawn by the overlay `<path>`, which tracks only the current
step.

---

## TWI-8 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Registry fixture + loader

**Work item:** Author the in-repo fixture that populates the registry, based on TWI-1's inventory.

- **Do not author this until TWI-1 is reviewed and approved.** It must cover the ENTIRE application.
- Format: **JSON** (matches repo convention ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â every existing fixture under `thetatauCMT/*/fixtures/` is
  JSON). Store as `thetatauCMT/guides/fixtures/feature_registry.json`.
  Structure it as a **custom document** keyed by `key` (areas ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ features ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ tour_steps ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ role_guides),
  **not** as a Django `loaddata` serialization ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â see the warning below.
- Provide `manage.py load_feature_registry`, **idempotent and upsert-by-`key`** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â safe to re-run after
  each release; updates copy/metadata without duplicating rows or losing `UserAcknowledgement` /
  `UserTourCompletion` history.
- Support `--dry-run` to report adds/updates/deactivations without writing.
- Entries removed from the fixture are **deactivated, not deleted**.
- Wire it into `configs/management/commands/dbseed.py` as a `self._manage_cmd("load_feature_registry")`
  call ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **not** as a `SEED_MODELS` entry.

> ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â **Why not plain `loaddata`:** per `/memories/repo/feature-flags-configs.md`, `loaddata` with fixed
> pks clobbers existing rows and with `"pk": null` it duplicates on every re-run. Neither is acceptable
> for content that must be re-loaded every release. A key-based upsert command is the only safe option.
> Also note: any `auto_now` field (`modified`) must be handled explicitly if you *do* use `loaddata`.

**Tests:** loader creates the full registry on an empty DB; re-running is idempotent (no duplicates, no
lost user state); `--dry-run` writes nothing; removed entries deactivate; every fixture `url_name`
reverses successfully (resolving dynamic tokens against a factory user); every selector matches a known
`data-tour` anchor; every `roles` value is in `core.models.ALL_ROLES`; every `audience` is a valid choice;
every `feature_flag` matches a `Config` key present in `configs/fixtures/feature_flags.json`; every
`Feature.task` key matches a `tasks.Task` slug.

### Status: DELIVERED

**Delivered:**

- `thetatauCMT/guides/fixtures/feature_registry.json` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **16 areas, 122 features, 17 tour steps** across
  5 toured areas. Covers the whole application as inventoried in `docs/specs/feature-inventory.md`.
- `thetatauCMT/guides/management/commands/load_feature_registry.py` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â upsert-by-`key`, `--dry-run`,
  `--path`, deactivate-never-delete, per-entry validation, add/update/unchanged/deactivated reporting.
- `configs/management/commands/dbseed.py` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â one added `self._manage_cmd("load_feature_registry")` call
  after `task_dates`, with a comment saying why it is not a `SEED_MODELS` entry.
- 35 tests in `guides/tests/test_registry_loader.py`.

**Decisions made during the build (all deviations are listed):**

1. **Display order is list position, not an `order` field.** The fixture carries no `order`; the loader
   assigns it from the index. Hand-maintained order numbers across 122 entries would be a standing
   source of duplicate and skipped values, and reordering a section would mean renumbering it.
2. **Tour steps are nested under their area in the same file**, and are matched on `(area, order)`
   rather than being deleted and recreated. A step has no natural key, but its position *is* its
   identity within an area, so this keeps primary keys stable across runs. Trailing steps beyond the
   fixture's list length are deleted ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â steps carry no user history, so a stale step is simply a broken
   tour. `UserTourCompletion` keys on the *area*, so it is untouched either way.
3. **`--dry-run` does the real work inside a transaction and then rolls back** (a private `_Rollback`
   exception). Computing a diff without writing would have needed a parallel comparison path that could
   drift from the real one, and would have had to skip `full_clean()` for features whose area does not
   exist yet. This way the dry run validates exactly what a real run would.
4. **The loader calls `full_clean()` on every instance** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â this is the main reason it exists rather than
   `loaddata`. A `CommandError` names the offending `key` and the failing field, so a fixture typo is
   diagnosable without reading a traceback. Because the whole load is one transaction, a bad entry
   anywhere leaves the previous registry completely intact (tested).
5. **`Feature.task` is linked only where the mapping is 1:1.** `Task.slug` is `slugify(name + owner)`,
   so forms owned by several officers produce several task rows ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Audit and Risk Management Form have
   five each. Linking one of them would make the card show one officer's due date as if it were the
   form's. **9 links** were made where exactly one task row exists: `initiation-report`, `pledge-form`,
   `premature-alumnus`, `submit-chapter-officers`, `osm-form`, `hs-education-program`,
   `new-member-education-program`, `gear-article`, `award-nomination`. A test asserts no task is claimed
   twice. The local demo row `seed-chapter-reportregent` is deliberately never referenced.
6. **An unknown task slug warns and leaves the link null rather than failing the load.** A fresh install
   or a test database may not have `tasks.json` loaded, and the catalog is still useful without the
   due-date link. `dbseed` loads tasks first, so the ordinary path always resolves. A test proves a task
   that arrives later gets linked on the next run.
7. **Eight features are catalogued with no link at all**, each with a `long_description` saying where to
   find the thing: `email-preferences` (per-user unsubscribe token), `take-attendance`, `rsvp-for-event`,
   `roll-book-page`, `bill-of-rights`, `approve-job-posting`, `cast-a-vote`, `ballot-results`. All of
   these need a primary key or a per-object token that no catalog card can supply. An honest unlinked
   concept card beats a link that always raises `NoReverseMatch`. A test requires every unlinked feature
   to carry a `long_description`.
8. **`scores:detail` and `submissions:add-direct` were dropped** despite the inventory marking them
   INCLUDE. `scores:detail` takes a per-`ScoreType` slug and is a drill-down from `scores:list`, which
   is the inventory's own exclusion rule. `submissions:add-direct` would have meant **one card per score
   type ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â 32 of them** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â duplicating seeded data into the catalog and going stale whenever
   `scoretypes.json` changes; `submissions:add` covers the same ground.
9. **Status changes are 5 cards, not 12.** The inventory asked for one entry per reason for *both* the
   submit form and the history table. The history table is reached from the submit page and is the same
   feature from the user's point of view, so only the submit forms are catalogued. `resignedCC` is
   omitted because it is candidate-chapter-only and there is no audience that expresses that ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it would
   be advertised to chapters that cannot use it. Graduation points at `forms:status_graduate_select`
   (the multi-select flow) rather than `forms:status_new`. Copy is taken verbatim from
   `forms.views.STATUS_CHANGE_TYPES`, so the catalog and the landing page cannot drift.
10. **`depledge-survey` lives only in the `surveys` area**, not duplicated into `forms-workflows` as the
    inventory listed it. Feature keys are the upsert identity and must be globally unique.
11. **`workflow-task-inbox` (`viewflow:index`) was moved from `regions-national` to `tasks-goals`.** It
    is where a member's assigned workflow tasks live, so it belongs next to Chapter tasks; putting it in
    a mostly-nat-officer area buried it. Discoverability is the point of the catalog.
12. **Tours were authored for 5 areas**, the ones whose anchors TWI-7 actually shipped: `getting-in`
    (3 steps, `audience: public`, entry `account_login`), `getting-started` (5, `home`),
    `events-attendance` (3, `events:list`), `tasks-goals` (4, `tasks:list`) and `forms-workflows`
    (2, `forms:landing`). The `nav-calendar` step carries `feature_flag: FEATURE_EVENTS_CALENDAR`, so it
    is skipped rather than silently missing when the flag is off. Every other area is `has_tour: false`,
    and a test asserts `has_tour` and the presence of steps always agree ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a "Take the tour" button with
    no steps is a dead end.
13. **`awards:direct_grant` is `audience: officer` and `scores:chapterlist` is `audience: natoff`**, per
    the inventory's footnotes. Neither is expressed by a mixin ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the first gates inside `dispatch()` via
    `can_grant_awards`, the second only requires login ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â so the catalog states the real audience rather
    than the one the code's decorators imply.
14. **Fixture-content tests collect every offender and assert once**, rather than parametrizing per
    entry. The parametrized version worked but added **709 test ids** for a single JSON file, inflating
    the suite by ~28%. The aggregate form gives the same diagnostics in the assertion message. This
    matches `unknown_anchor_selectors()` in TWI-7's anchor tests.
15. **The TWI-7 template scanner moved consumer, not location.** `test_registry_loader.py` imports
    `template_anchors()` from `test_tour_anchors.py`. TWI-7 decision #4 said it would move to a
    `guides/anchors.py` when a second consumer appeared ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but the second consumer is another *test*, so
    a production module would still be speculative.

**Verified:** registry tests 35 passed; guides package **231 passed**; full suite **2564 passed,
17 skipped, 0 failed**; `black`/`flake8` clean; `manage.py check` clean; `makemigrations guides --check`
reports no changes (no model edits); `git status` shows no collateral reformatting.

**Verified against the running local database**, not just in tests: first load reported
`16 added / 122 added / 17 added`, an immediate re-run reported `16 / 122 / 17 unchanged`, and a
`--dry-run` on an empty registry wrote nothing. All 112 URL-bearing features resolve for a real user
(`resolve_feature_url` returned non-`None` for every one). `get_visible_areas` gives an anonymous
visitor **1 area / 4 features** and a plain member **16 areas / 75 features**, against 122 for a
nat-officer. `get_tour_config` emits the exact shape `tours.js` consumes
(`{element, title, body, side, align}`) and offers an anonymous visitor only `getting-in`.

**Not wired to a page yet.** `TourConfigMixin` still has no consumers, so none of these tours are
reachable in a browser ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the catalog page and the help hub that expose them are TWI-9 and TWI-10.

---

## TWI-12 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Role Guide ("I'm the new Treasurer") ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â NEW

**Work item:** The officer-onboarding surface. This is the half of the user's request the original plan
did not cover, and it is the highest-value piece for chapter health.

- Migrations first (pause). See **RoleGuide / RoleGuideStep**.
- Route: `/features/role/<role_slug>/`, plus `/features/role/` which redirects to the viewer's own
  primary duty role (or lists all guides if they have none/several).
- Page contents, in order:
  1. **Summary** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â what this role is responsible for, 2ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“4 sentences.
  2. **"Your open items"** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â live, not static: `TaskDate.incomplete_dates_for_chapter(chapter)` filtered
     to `task__owner=role`, reusing `tasks.tables.TaskTable` so it looks and behaves exactly like the
     home page and `tasks:list`. Each row already renders its own form/submission link via
     `Task.render_task_link`.
  3. **"What you'll do each term"** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ordered `RoleGuideStep` rows with `cadence`, each linking to its
     `Feature` ("Take me there") or `Task`.
  4. **"Tools you have access to"** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the catalog features whose `roles` include this role.
  5. **"Show me around"** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â launches the tour chapter for the most relevant area.
- Surface it where a new officer will actually hit it:
  - a card on the home page above the task table, shown when `get_role_guides(user)` is non-empty,
  - a link from the account dropdown,
  - **on role assignment** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `forms.views.RoleChangeCreateView` creates `users.models.UserRoleChange`
    rows; the existing officer notification path (`forms/notifications.py`, and the
    `monthly_chapter_officer_email` / `officer_update_reminder_email` commands) should include a link to
    the new officer's Role Guide. This is the single highest-leverage entry point in the whole plan.
- **Advisors and committee chairs count.** `adviser` and `risk management chair` are not in the
  `officer` Django group but own real obligations ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â their guides must work for a plain `member` audience.

**Tests:** guide renders for each of the 9 seeded roles; "your open items" shows only `Task`s whose
`owner` matches the role and only for the viewer's chapter; archived `TaskDate`s excluded (respect
`TaskDate.archived`); a member with no duty role sees the index, not a 404; a `UserAlter`-impersonated
role shows that role's guide; steps with a `feature` the viewer cannot see are hidden; query count bounded.

> **Status: DELIVERED.** `RoleGuide` + `RoleGuideStep` (migration `0004`), `guides/views.py`
> `RoleGuideView` / `RoleGuideIndexView`, `templates/guides/role_guide.html`, 9 guides in the fixture.
> 23 tests in `guides/tests/test_role_guides.py` + 3 in `users/tests/test_notifications.py`.
>
> Build decisions:
> - **The new-officer email is the entry point that matters.** `users.notifications.NewOfficers` gained
>   `_role_guides()`, which unions `chapter_officer()` and `current_roles` across the recipients and
>   links each matching active guide. `RoleGuide` is imported *inside* the method, not at module scope:
>   `herald` imports every notification class at startup, and a module-level import would make the
>   notification layer depend on the guides app at boot. The link also went into
>   `officer_update_reminder.html`, which is the weekly nag every officer already reads.
> - **Open items are national, completion is per chapter.** `TaskDate` rows are not chapter-scoped;
>   only `incomplete_dates_for_chapter` filtering is. A test asserts that another chapter completing a
>   task does *not* close it out for mine ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the reverse of the assertion originally planned.
> - **`tour_area_key` is derived, not stored:** the area contributing the most tools to the guide.

---

## TWI-9 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Feature Catalog page

**Work item:** The primary discovery surface ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a permanent, browsable catalog.

- Route: `/features/`, name `guides:catalog` (namespaced like every other app in `config/urls.py`).
- Grouped by `FeatureArea` (ordered), cards per `Feature` (ordered) via `get_visible_features`.
- Each card: name, short description, `NEW` badge when applicable, "Take me there" deep link (omit when
  the URL is unresolvable), optional expand for `long_description`, and a "Part of your Treasurer
  duties" chip when the feature's `roles` intersect the viewer's duty roles.
- Each area header: description, Font Awesome icon, "Show me around" button when `has_tour`, and a
  completed indicator when `UserTourCompletion` exists.
- Client-side search/filter across name + description; filter chips by area; "only show my role's tools"
  toggle. Search is client-side over already-rendered cards ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no extra endpoint, no N+1.
- **Performance:** one query for areas, one `prefetch_related("features")`, one for the viewer's
  `UserTourCompletion` keys, and two for `UserAcknowledgement` (one per content type). Assert a bounded
  query count in tests ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `core.middleware.QueryTimingMiddleware` already exists for staging verification.
- Extends `base.html`; must render correctly in dark mode.

**Tests:** catalog renders grouped and ordered; audience filtering correct for anonymous / member /
officer / natoff; an anonymous visitor sees only the `getting-in` area; a natoff with `natoff_hidden`
sees the member view; flag-disabled areas absent; unresolvable links render as non-linked cards; tour
button present only when `has_tour`; completed state shown; query count bounded.

> **Status: DELIVERED.** `guides:catalog`, `CatalogView(TourConfigMixin, TemplateView)`,
> `templates/guides/catalog.html`, `static/js/catalog.js`. 21 tests in `guides/tests/test_catalog.py`
> (shared with TWI-10's help hub).
>
> Build decisions:
> - **Tests scope their assertions to keys they created** (`_mine(catalog, prefix)`), because the
>   catalog is registry-wide and a seeded database would otherwise swamp every assertion.
> - **`TourConfigMixin` leaves `tour_config` unset when there are no tours.** `get_tour_config` returns
>   `{"tours": {}}` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a truthy dict ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â so always assigning it made every mixin page emit an empty
>   `#tt-tour-config` payload for the runner to reject. The mixin now assigns only when `config["tours"]`
>   is non-empty, which is what `test_a_page_without_a_tour_config_emits_nothing` was written to protect.

---

## TWI-9b ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Rebuild the Forms landing page from the registry ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â COMMITTED (resolved decision #8)

**Work item:** Replace the hand-maintained table in
[thetatauCMT/templates/forms/landing.html](thetatauCMT/templates/forms/landing.html) with a
registry-driven, genuinely useful landing page for the `forms-workflows` area.

**Users have said the current page is useless**, so this is *not* a parity exercise ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â parity is only the
safety net. Ship it as a real improvement:

1. **Group by purpose, not alphabetically.** Use `FeatureArea` subgrouping ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â e.g. *Membership changes*
   (initiation, status change, depledge, transfer), *Officer & chapter administration* (officer election,
   bylaws, roll book, audit), *Risk & compliance* (RMP, event risk, collection referral),
   *Money* (invoices, balances), *Recognition* (awards, nominations).
2. **Surface what's relevant to *me* first.** A pinned "For your role" block driven by the viewer's duty
   roles (`user.chapter_officer()` + `current_roles`) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the treasurer sees invoices and the audit form at
   the top. Falls back cleanly to the grouped list for members with no role.
3. **Add the two columns people actually need:** *Who submits this* (duty role, from `Feature.roles`)
   and *When / how often* (from the linked `tasks.Task` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `TaskDate` cadence where one exists, otherwise
   the feature's `cadence` copy). This is the information the current table omits and users need.
4. **Client-side search/filter box** over name + description + role, same component as the catalog
   (TWI-9) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â one implementation, two pages.
5. **Live status where it's cheap.** If a form maps to a `tasks.Task` with an incomplete `TaskDate` for
   the viewer's chapter, show a due-date pill. Reuse `Task.incomplete_dates_for_task_chapter(chapter)`
   ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â do not write a second query. Cap this to one prefetch for the whole page.

**Constraints:**
- Keep the URL name `forms:landing` and the existing nav link unchanged.
- Model the natoff-only "All Chapters" companion link as a second `Feature` in the same area with
  `audience="natoff"` and an `admin_of` pointer (or an adjacent ordered feature) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â decide in TWI-2 and
  record the choice. It must not require `{% if request.is_nat_officer %}` in the template.
- Feature-flagged rows must respect their flags.

Doing this early also de-risks everything else: it proves the registry handles the hardest real case
(Viewflow namespaced URLs, natoff companion links, flags, role targeting) *before* the full fixture is
authored, and it converts the catalog from "a new page nobody visits" into "the thing powering a page
people already use daily."

**Tests:** **snapshot the current link set first**, then assert the new page renders at least that set
for a member, an officer, and a natoff (no form may silently disappear); "For your role" block shows
treasurer forms for a treasurer and is absent for a plain member; due-date pill appears only for a
chapter with an incomplete `TaskDate`; flags respected; page issues a bounded number of queries
(`assertNumQueries`); no regression in `thetatauCMT/forms/tests/test_views.py`.

> **Status: DELIVERED.** `forms/landing.html` is rendered from `FORM_GROUPS` via
> `guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")`.
> 13 tests in `forms/tests/test_landing.py`.
>
> Build decisions:
> - **The 36 pre-rebuild URL names are frozen in the test module** (`PRE_REBUILD_URL_NAMES`), with
>   `DOCUMENTED_EXCLUSIONS` naming the only three that legitimately changed: `alumniexclusion` and
>   `forms:pledge_program` moved to their Viewflow `ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦:start` routes, and `awards:import_upload` is
>   superuser-only. Anything else disappearing fails the suite.
> - **`forms:officer` is deliberately member-visible.** The officer *roster* is something any member may
>   read; the officer-gated entry is `forms:officer_add`. A test asserted the opposite at first ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the
>   registry was right and the test was wrong.
> - **Registry entries in `forms-workflows` that no group claims fall into an `other` group**, so adding
>   a feature to the fixture can never make it invisible on this page.
> - The verification pass added the three tests the plan asked for that the first cut missed: the
>   "For your role" pinned block (present for a treasurer, empty for a plain member), the due-date pill
>   appearing only while the chapter still owes the task, and a query-count regression proving
>   `_attach_task_schedule` does not cost a query per row.

---

## TWI-10 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Entry points & help

**Work item:** Make discovery reachable, and **retire the Google Doc** (resolved decision #3).

- **Replace `pages/help.html` outright.** `path("help/", TemplateViewÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ pages/help.html)` in
  `config/urls.py` currently serves nothing but an `<iframe>` to a published Google Doc that is badly
  out of date. **Delete the iframe.** This work replaces that content ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â do not keep a "Full
  documentation" link to it, because leaving a stale doc reachable recreates the problem.
  Keep the URL name `help` so the `#help` nav icon and the two footer links need no change.
- The new hub offers:
  - "What can the CMT do?" ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ catalog (TWI-9)
  - "What am I responsible for?" ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Role Guide (TWI-12)
  - "Show me around this page" ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ launches the tour for the area matching the referring/current URL name,
    shown only when such an area exists and has steps
  - "What's new?" ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ the What's New archive (TWI-6)
- **The `?` button is the trigger for everything built here.** Where an area has a tour, the `?` icon
  should launch that area's tour directly rather than bouncing to the hub ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â hub is the fallback.
- Add a Role Guide card to the home page above the incomplete-tasks table.
- Add "What's this page for?" links from major empty states to the relevant catalog entry or tour.

**Anonymous behavior (resolved decision #4).** The `?` icon is visible to signed-out users, so the hub
must render anonymously ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but it shows **only the `getting-in` area**: sign in, find my username / badge
number, reset my password, update my info without signing in. Nothing else is public. `/features/`
(the full catalog) requires login; an anonymous hit renders the same public block plus a sign-in prompt
rather than a bare 302, so a confused member lands somewhere useful.

> ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â **Inventory correction to carry into TWI-1/TWI-8:** `UserBadgeLookupView`,
> `UserLookupSearchView`, `UserLookupSelectView`, and `UserLookupUpdateView` in
> [thetatauCMT/users/views.py](thetatauCMT/users/views.py) are plain `FormView` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â **no login required**.
> An earlier automated inventory pass marked them `natoff`. They are the backbone of the public area.

**Tests:** help hub renders for anonymous and authenticated users; anonymous hub shows the four
`getting-in` entries and **nothing else** (explicit assertion that no `member`/`officer`/`natoff` entry
leaks); `pages/help.html` contains no iframe and no Google Docs URL anywhere in the repo; contextual
"tour this area" appears only where the URL name maps to an area with a tour; empty-state links resolve
to visible catalog entries.

> **Status: DELIVERED, with one bullet outstanding.** `pages/help.html` is rebuilt behind
> `HelpHubView(TourConfigMixin, TemplateView)` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â the iframe and the Google Docs URL are gone from the
> repo. `tour_here` on the mixin lets the `?` icon launch the current area's tour directly, falling back
> to the hub. The Role Guide card sits above the incomplete-tasks table on the home page and the account
> menu links the guides. Covered by the TWI-9 test module.
>
> **Not built:** *"Add 'What's this page for?' links from major empty states."* Thirty templates render a
> `django_tables2` empty row, and which of them count as "major" is a product call, not an engineering
> one. The mechanism it needs is small ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a tag that maps `resolver_match.view_name` to a visible
> `Feature` and links its catalog anchor ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â but the placement decision is open.

---

## TWI-11 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â QA seed & verification pass

**Work item:** Make the whole system QA-able.

- Add `manage.py seed_guides_demo`, following the shape of the existing `seed_awards_demo` /
  `seed_dashboard_data` / `seed_contact_sync_examples` commands, and **call
  `core.seed_guard.ensure_seeding_allowed(force)`** rather than re-implementing the DEBUG check.
- Seed the registry plus per-user state variations: a user who has acknowledged nothing (gets What's
  New), a user who has acknowledged everything, a user mid-way with some completed tours, one user per
  duty role (regent / treasurer / risk management chair / adviser) and a plain member. Include a
  published `Announcement` in both dismissible and `dismissible=False` variants.
- Provide `docs/specs/guides-qa.md`: per audience and per duty role, what the catalog should show, which
  tours run, what the Role Guide lists, and what What's New should list.
- Verify against every audience, **including a natoff with `natoff_hidden` toggled on** and a natoff using
  `UserAlter` to impersonate a chapter officer ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â those two paths are where leaks will happen.
- Verify in **both light and dark mode**, and at a mobile width (offcanvas nav) for tours.

**Tests:** seed is idempotent and prod-guarded; each audience's catalog snapshot matches expectations;
tours run cleanly for each audience; no tour step targets a missing anchor for any audience.

> **Status: DELIVERED.** `manage.py seed_guides_demo` (`--flush`, `--seed`, `--force`) plus
> [docs/specs/guides-qa.md](docs/specs/guides-qa.md). 5 tests in `guides/tests/test_seed_guides_demo.py`;
> verified by hand twice including a `--flush` round trip.
>
> Build decisions:
> - **The command seeds only what a fresh DB cannot produce**: it calls `load_feature_registry` for the
>   registry itself and then adds the *time-sensitive* state ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a feature released today, four
>   announcements (member / officer / role-targeted / non-dismissible pinned), and three acknowledgement
>   personas (seen nothing, seen everything, part-way through).
> - **It reports duty-role holders rather than creating `UserRoleChange` rows**, because creating them
>   fires the officer notification emails.
> - **`--flush` must forget acknowledgements explicitly.** `UserAcknowledgement` points at its target
>   through a generic FK, so deleting the announcement or feature does not cascade.
> - Field-name corrections found the hard way: there is no `UserAcknowledgement.record()`
>   (`update_or_create` with a `ContentType`), no `UserTourCompletion.Status.SKIPPED` (`DISMISSED`), and
>   no `Config.set` (create the row, then mutate `.value`).

---

## TWI-13 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Instrumentation & release workflow doc ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â NEW

**Work item:** Close the loop so we can tell whether this worked.

- Emit PostHog events (PostHog is already initialized in `base.html` for authenticated non-DEBUG users
  and identifies `officer`, `natoff`, `role`, `chapter`): `catalog_viewed`, `catalog_searched`,
  `feature_link_clicked`, `tour_started`, `tour_completed`, `tour_dismissed`, `whatsnew_shown`,
  `whatsnew_dismissed`, `item_acknowledged` (with `kind` = feature/announcement and `source` =
  modal/badge/visited/bulk), `role_guide_viewed`. Guard every call with `if (window.posthog)`.
  The `item_acknowledged` `source` breakdown is the direct measure of whether this is helping or
  irritating: heavy `badge` dismissal without `visited` means we are advertising things nobody wants.
- Write `docs/specs/feature-registry.md`: how to add a feature to the fixture, set
  `released_at` / `release_version` / `is_highlighted`, re-run `load_feature_registry`, and what the
  `NEW` badge lifecycle looks like. Add a line to `docs/management_commands.md` (which already exists).

**Tests:** none required beyond "no JS error when PostHog is absent" (DEBUG, or an ad blocker).

> **Status: DELIVERED.** Every listed event now fires. `role_guide_viewed` was the last one: rather than
> a new script, `role_guide.html` renders a `data-role-guide-page="<role>"` marker and loads the existing
> `catalog.js`, whose `ready()` emits the event **before** the `if (!cards.length) return;` early exit ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
> the Role Guide has no catalog cards.
>
> **Three events were renamed during TWI-6** and the names above are stale. The shipped names are
> `whats_new_shown`, `whats_new_dismissed`, `whats_new_acknowledged` and `whats_new_visited` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â snake_case
> throughout, and the plan's single `item_acknowledged` was split into *acknowledged* (pressed "Got it")
> versus *visited* (followed the link), because those mean opposite things about whether the item was
> wanted. `docs/specs/feature-registry.md` carries the authoritative table.
>
> [docs/specs/feature-registry.md](docs/specs/feature-registry.md) documents the fixture shape, all four
> field tables, the loader's upsert-by-natural-key / deactivate-never-delete contract, four "common
> edits" recipes, and a table mapping every PostHog event to the file that emits it.
> `docs/management_commands.md` gained *Load Feature Registry* and *Seed Guides Demo* sections.

---

## Build Order & Dependencies

All eight open decisions are **resolved** (see the table at the end) ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â TWI-0 is closed and the model
shape is settled, so migrations can proceed once TWI-1 is reviewed.

1. **TWI-1** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Full functionality audit (read-only). **Blocks TWI-8. ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Delivered** as
   [docs/specs/feature-inventory.md](docs/specs/feature-inventory.md); awaiting owner review of
   Section A, which carries the public-awards ruling and two security questions.
2. **TWI-2 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-3** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Registry models + audience/role service (foundation for every surface).
   **Pause after migrations for confirmation.**
3. **TWI-4** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Driver.js foundation (independent of the registry; can run in parallel with 2ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“3).
4. **TWI-7** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â `data-tour` instrumentation (needs TWI-1; must precede step authoring in TWI-8).
5. **TWI-9 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-9b** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Catalog page, then rebuild the Forms landing page from it. **9b is committed
   work and lands early** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â it is the fastest visible win and it stress-tests the registry against the
   hardest real case before the full fixture is authored.
6. **TWI-12** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Role Guide (needs TWI-2/3; joins to the existing `tasks` app).
7. **TWI-8** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Fixture + loader (needs TWI-1, TWI-2, TWI-7).
8. **TWI-6** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â What's New + announcement merge (needs TWI-3 + TWI-8 content to announce).
   Its `Announcement` migration touches a live table ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â treat it as its own reviewed step.
9. **TWI-5** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Area tour chapters (needs TWI-3 + TWI-4 + TWI-7).
10. **TWI-10 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-13 ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-11** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Entry points and help-page replacement, instrumentation, QA seed
    and verification.

**Highest value per effort, revised:**
**TWI-12 (Role Guide) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-9/9b (catalog + forms landing) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-6 (What's New) ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ TWI-5 (tours).**
The Role Guide is first because it addresses the more expensive of the two stated problems, it reuses an
engine that already exists (`tasks`), and it needs no JavaScript at all. TWI-9b is close behind because
users have already told us the page it replaces is useless ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â that is a known, named complaint. Tours are
the most fragile and least durable piece ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â build them last.

---

## Design Rules & Gotchas (apply throughout)

- **Never auto-launch tours.** Only the What's New modal may appear unprompted, subject to the
  suppression rules in TWI-6. Forced tours are the main source of user annoyance.
- **One dismiss mechanism, one endpoint.** Every dismissible thing ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â a new feature, a `NEW` badge, an
  announcement ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â writes `UserAcknowledgement` through the same POST. Do not add a second "seen" table
  or a second dismiss route.
- **Four audiences, not six:** `public | member | officer | natoff`. `public` is reserved for the
  `getting-in` area only. Superuser tooling is out of scope.
- **Audience filtering happens server-side** in `guides/services.py`; steps are *additionally* filtered
  client-side for missing/zero-size DOM elements. Both layers are required.
- **Respect the two impersonation mechanisms.** `natoff_hidden` ("view as member") and `UserAlter`
  (chapter/role impersonation) must both be honored, or National Officers previewing the member
  experience will see natoff-only content. Use `is_national_officer_group` and `chapter_officer()`,
  never `in_national_officer_group` or raw `current_roles`.
- **Respect feature flags.** Never advertise a feature whose `Config` flag is off
  (`FEATURE_AWARDS`, `FEATURE_JOBS`, `FEATURE_EVENTS_CALENDAR`).
- **Anchor to navigation and page furniture, not database objects** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â tours must work on an empty or
  sparse database, and on a chapter with no region.
- **`data-tour` attributes only** for selectors; treat them as a stable contract.
- **Open the container before highlighting.** Bootstrap dropdowns and the mobile offcanvas hide nav
  targets; see TWI-4.
- **Dark mode is real.** Everything must be legible under `data-bs-theme="dark"`.
- **`json_script` + external JS everywhere; no new inline handlers.** CSP is report-only today but is
  intended to become enforcing ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â do not add debt.
- **Everything resumable/abandonable:** dismissing a tour or modal must record state and never trap the
  user; a failed state-recording POST must never block navigation.
- **The catalog and the Role Guide are the durable artifacts.** Tours are transient. Prioritize the
  quality and completeness of the two permanent pages.
- **Run tests in the container:** `docker exec thetataucmt_local_django pytest thetatauCMT/guides -v --tb=short`.

---

## Resolved Decisions

All eight are answered. Each is now reflected in the work items above; this table is the record of
*why* the plan looks the way it does.

| # | Decision | Answer | Where it lands |
|---|---|---|---|
| 1 | Role Guide scope | No committee chairs beyond `risk management chair` in phase 1 | **9 RoleGuides locked** (TWI-1 Ãƒâ€šÃ‚Â§RoleGuides). Model still accepts any `ALL_ROLES_CHOICES` value, so adding one later is a fixture edit, not code. |
| 2 | `Announcement` vs What's New | **Combine.** An announcement should be dismissible per user after acknowledging | `Announcement` gains `audience`/`roles`/`dismissible`/`feature`; new generic **`UserAcknowledgement`** serves both models; TWI-6 rewritten around one merged feed. |
| 3 | `pages/help.html` | The Google Doc is so out of date this work replaces it; the `?` button triggers the new help | TWI-10 **deletes the iframe** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â no "Full documentation" fallback link. `help` URL name retained so nav/footer links are untouched. |
| 4 | Anonymous/public scope | Public help is only: getting logged in, finding your username, resetting a password, updating member info without logging in | New **`getting-in`** area, the only `audience="public"` content. Catalog requires login. Audience enum collapsed to 4 values. |
| 5 | `NEW` badge duration | 30 days is fine, **but users must be able to dismiss/acknowledge** | `NEW_FEATURE_MAX_AGE_DAYS = 30`, plus a per-badge ÃƒÆ’Ã¢â‚¬â€ dismiss and acknowledge-on-click, both writing `UserAcknowledgement` with a `source`. |
| 6 | Admin-only tooling | Very few admins ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â nothing special for them | `reports-exports` area dropped; Report Builder, award import queue, and Config admin excluded as internal. No `superuser` audience value. |
| 7 | App name | `guides` | `thetatauCMT/guides/`, `manage.py load_feature_registry`, `manage.py seed_guides_demo`, docs at `docs/specs/`. |
| 8 | Forms landing rewrite | Users say the landing page is useless ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â making it more useful would be great | **TWI-9b promoted from proof-of-concept to committed work, moved early**, and expanded well past parity: purpose grouping, "For your role" block, who-submits/when columns, search, live due-date pills. |

**Open items created by these answers ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â all now settled:**

- **The natoff "All Chapters" companion is an adjacent ordered `Feature` with `audience: "natoff"`.**
  No `admin_of` pointer was added: the pairing is already expressed by list position in the fixture
  (`chapter-audit-form` then `all-audits`, `chapter-bylaws` then `all-bylaws`, and so on), and a field
  would have to be kept in sync with that ordering for no gain. The forms landing renders both from one
  loop with no `{% if request.is_nat_officer %}` anywhere in the template.
- **An acknowledged-but-still-published announcement collapses rather than disappearing** ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
  `pages/home.html` puts the acknowledged items in a `#tt-whats-new-seen` collapse, as recommended.
- Who owns writing the actual catalog and Role Guide copy. The plan produces the machinery; the words
  are a content task and are the difference between this being useful and being ignored. **The fixture
  ships a full first draft** (16 areas, 122 features, 9 role guides); it has not had an editorial pass
  by an officer.

---

## Recommended model per work item

Asked for: best outcome, minimal review/rework. The split below is about **where a wrong answer is
expensive**, not about difficulty.

**Use the strongest available Opus-tier model for:**

| Work item | Why it needs the strongest model |
|---|---|
| **TWI-1** (functionality audit) | Pure judgement over a large, unfamiliar surface. An automated pass already got the `users` lookup views wrong (marked `natoff`; they are public `FormView`s). Errors here propagate into the fixture and into what users are told they can do. |
| **TWI-2 + TWI-3** (models + visibility service) | **This is the leak surface.** `natoff_hidden`, `UserAlter`, `chapter_officer()` vs `current_roles`, `is_national_officer_group` vs `in_national_officer_group` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â four subtle distinctions where a plausible-looking wrong choice passes naive tests and leaks natoff content to members. Also the hardest to change later. |
| **TWI-6** (announcement merge) | Migration against a live, in-use table plus a generic-FK design. Requires reasoning about backwards compatibility for existing rows. |
| **TWI-8** (fixture authoring) | Large context, high volume, needs consistent judgement across ~200 entries and correct URL-name resolution. |
| **TWI-9b** (Forms landing rebuild) | Touches a page in daily use; parity must not break while the page changes substantially. |
| **TWI-12** (Role Guide) | Cross-app reasoning over `tasks`, `core.models` role vocabularies, and chapter scoping. |

**A Sonnet-tier model is a good fit for** TWI-4, TWI-5, TWI-7, TWI-9, TWI-10, TWI-11, TWI-13 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â these are
well-specified, mostly mechanical (especially TWI-7's `data-tour` attribute pass), and verifiable by the
tests already named in each item. Escalate if a test fails twice for the same reason.

**Do not use a Haiku-tier model** for anything here except trivial doc edits; the role/permission
subtleties in this codebase punish shallow reasoning.

**Practical rework-reducers, independent of model choice:**

1. **Make TWI-3 the single gate, and test it before any UI exists.** Every surface calls it. Test it
   against all four audiences ÃƒÆ’Ã¢â‚¬â€ `natoff_hidden` on/off ÃƒÆ’Ã¢â‚¬â€ an active `UserAlter` ÃƒÆ’Ã¢â‚¬â€ each feature flag off.
   If this is right, the rest is presentation.
2. **One work item per session.** These items are individually small but the codebase context is large;
   a fresh session per TWI keeps the model's attention on the item instead of the history.
3. **Honor the migrate-then-pause rule** already in TWI-2 and TWI-6. Model/migration mistakes are the
   only ones here that are genuinely expensive to unwind.
4. **Run the container test suite after each item**, not at the end:
   `docker exec thetataucmt_local_django pytest thetatauCMT/guides -v --tb=short`, then the full
   `pytest --tb=no -q` against the ~1065-passing baseline before moving on.
5. **Give the model the two repo-memory notes** written for this work ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â
   `roles-and-audiences.md` and `frontend-base-template.md` ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â at the start of each session. They encode
   the traps (impersonation, Bootstrap containers, dark mode, CSP reality) that cause the rework.


---

## 2026-08-02: registry audience corrections, RD/NatOff guides, site-wide em dash purge

Seven asks, all landed. Full suite stayed at **2582 passed / 17 skipped / 0 failed**.

**Registry (`guides/fixtures/feature_registry.json`)**

- `export-award-data` raised to `natoff`. Note the view is looser: `AwardExportView.dispatch`
  gates on `can_grant_awards` (any national/chapter officer or RD). The catalog is now stricter
  than the view; tighten the view if that gap matters.
- Twelve member-audience form cards raised to `officer`: initiation report, pledge form,
  premature alumnus, return student, alumni exclusion, chapter bylaws, convention form, OSM form,
  HS education program, new member education program, pledge pins, gear article. The member forms
  landing dropped from 21 cards to 9. Every viewflow `:start` node has `permission=None`, so
  audience is the only thing standing between a member and a submit button.
- `depledge-survey` set `"is_active": false` rather than deleted (loader deactivates, and
  `test_registry_loader.py` guards against a shrinking registry). Its `surveys` area now renders
  nowhere because empty areas are dropped from the catalog. The pledge educator guide step that
  referenced it kept its text and lost its `feature` link.
  `test_registry_loader.py` grew `RETIRED_FEATURE_KEYS` so "no inactive features" became
  "only the deliberately retired ones".
- Both vCard cards pointed at raw `.vcf` downloads. Repointed to the pages that host the sync
  modal: `regions:officers` (with `@region_slug`) and `forms:natoff`.
- Regional Director guide 7 -> 15 steps; National Officer guide 7 -> 14. Added
  `roles: ["regional director"]` to national-dashboard, events-attendance-dashboard,
  all-chapter-scores, all-events, pending-event-reviews, chapter-balances.

**Em dashes**

Removed from every user-facing surface: ~40 templates, 20 fixture prose strings (watch `' -- '`,
not just the glyph), and Python help text / messages / email subjects / `__str__` output.
Developer comments were left alone. Empty-value placeholders are now the word `None`.

The stubborn one was django-tables2: `TableOptions` hard-codes `getattr(options, "default", "-")`
as an em dash with no settings hook, and `Meta` is rebuilt per class by the metaclass so a
`Meta`-level override does not inherit. Fix is `core/tables.py::CMTTable`, which only overrides
`__init__` to `kwargs.setdefault("default", "None")`; all 50 table classes across 15 apps now
subclass it.

## 2026-08-02 Ã¢â‚¬â€ Signed-out surfaces; goals + award nomination for RDs and NatOffs

**Nothing anonymous visitors cannot open gets advertised to them.**

`CatalogView` and `HelpHubView` are the only public views in `guides/`; role guides, What's New,
the archive, seen, and acknowledge are all `LoginRequiredMixin`. `base.html`, `pages/help.html`,
and `guides/catalog.html` already gated their mentions correctly. `pages/about.html` did not: its
`{% else %}` branch showed "Role guides ... Sign in to read them." That branch is gone rather
than reworded. Dangling a locked door in front of someone is worse than saying nothing.

`core/tests/test_about_page.py::test_about_does_not_send_an_anonymous_reader_to_a_login_wall`
now asserts the words "Role guides" are absent, not just the href.

Verified both ways with the Django test client rather than the browser (see the
`dev-container-and-local-verification` memory for why, and for the branch-switch restart):
anonymous `/about/`, `/help/`, `/features/` mention none of it; signed in, all of it returns.

**Chapter visits**

Regional Directors and National Officers visit chapters, and setting and reviewing goals is part
of that visit, as is nominating what they see for an award. Added `"regional director"` to the
`roles` of `chapter-goals`, `set-a-goal`, and `award-nomination`, and gave both the RD guide
(15 -> 17 steps) and the National Officer guide (14 -> 16) a goals step (`ongoing`) and an award
nomination step (`annual`).

This is not a permission change and does not need one. `ObjectiveCreateView.form_valid` and
`ObjectiveListView` (`filter_chapter = True`) both key off `user.current_chapter`, and
`users/models.py::current_chapter` already resolves through `UserAlter` for national officers,
which is the chapter switcher in the top bar. The `long_description` says so, because a
cross-chapter officer landing on a chapter-scoped page will otherwise wonder whose data it is.

Suite: 2583 passing (2 known order-dependent flakes, both green in isolation:
`awards/tests/test_directory.py::test_filter_by_region`,
`finances/tests/test_views.py::test_chapter_balances_view_member_sees_only_own_chapter`).

## 2026-08-02 (later) â€” `AwardExportView` tightened to administrators

The gap flagged in the audience audit is closed the other way round: rather than loosen the
card to match the view, the view now matches the tightest reading. Browsing awards a page at a
time is open; walking off with the whole set is not. `AwardExportView.dispatch` checks
`request.user.is_superuser` instead of `can_grant_awards`, and the `can_export` flag on
`AwardDirectoryView` and `_AwardHistoryView` follows, so officers no longer see an export
button that bounces them home.

`export-award-data` is retired from the catalog (`"is_active": false`). It could not simply be
re-audienced: `AUDIENCE_RANK` stops at `natoff` and `user_audience()` maps superusers to
`natoff`, so there is no audience that means "administrators only". A `natoff` card would
advertise a door that sends most of its readers home -- the same mistake as the About page
offering role guides to signed-out visitors.

Test note: `_admin()` logins need `@override_settings(DEBUG=True)`, or
`RequireSuperuser2FAMiddleware` 302s to `/setup/` before the view is reached.
`test_export_blocks_officers` is parametrized over chapter officer and national officer, since
the whole point of the change is that neither gets in.

Suite: 2585 passed, 17 skipped, 0 failed.

## 2026-08-02 (later still) — anonymizer coverage for `guides`

The whole guides app was missing from `anonymizer/`. `anonymize_db --check_only` named all
five models: `FeatureArea`, `Feature`, `RoleGuide`, `RoleGuideStep`, `UserAcknowledgement`.

All five are `register_skip`. The four catalog models are editorial content seeded from
`feature_registry.json`, and staging is exactly where that copy gets reviewed, so wiping it
would remove the thing under test. `UserAcknowledgement` reaches a person only through a
foreign key, and the User model is anonymized already, so by the house rule it stays too --
`register_clean` is reserved for tables holding raw as-uploaded identity fields
(`attendance.MatchQueueItem`, `awards.AwardImportMatchQueueItem`).

Added `core/tests/test_anonymizer.py`. This gap survived an entire feature build because the
only thing that catches it is a management command nobody runs while writing code. The test
constructs `Anonymizer(soft_mode=False)` directly rather than calling `anonymize_db`, because
`dj_anonymizer` is only in `INSTALLED_APPS` under local/staging settings -- the class itself
does not need the app installed. Verified it fails for the right reason by moving
`anonymizer/guides.py` aside: `LookupError` naming all five models.

Suite: 2586 passed, 17 skipped. One order-dependent flake this run
(`attendance/tests/test_views.py::test_guest_autocomplete_scoped_to_selected_chapter_only`),
green in isolation and unaffected by the new test when the two files run together.
