# Bigs, Littles and the chapter family tree

**Status (2026-10-20):** Built. Questions answered (see the [Decisions log](#decisions-log)),
all eleven work items built and tested, full suite green (3,492 passed, 16 skipped). Still
open: your manual checks in a browser (see [Verification](#verification)) and the deploy.

**How to use this document**

- Answer each question in [Questions for review](#questions-for-review) on its
  **Answer:** line. "Default" is a fine answer. Add anything else under the question.
- [Progress](#progress) is the tracker. Each work item updates its row and ticks its
  checklist when it lands.
- When a question is answered, the build session copies the answer into the
  [Decisions log](#decisions-log) and adjusts the work items it affects.
- Work items are named BLWI-n (Big/Little work item) and are written so a fresh session
  can pick one up cold. Read the [Shared preamble](#shared-preamble) first.

App: `thetatauCMT.biglittle`. URL prefix: `/biglittle/`. URL namespace: `biglittle`.

## Progress

| Item | Summary | Depends on | Waiting on | Status |
|---|---|---|---|---|
| Spec | This document | | | Done |
| BLWI-1 | App, `BigLittle` model, migration, admin, anonymizer | | | Done |
| BLWI-2 | Rules and permissions (`services.py`) | 1 | | Done |
| BLWI-3 | Shared endpoints: member picker, remove, profile redirect | 2 | | Done |
| BLWI-4 | Big column on the initiation report | 3 | | Done |
| BLWI-5 | "My Big and Littles" on Edit My Info | 3 | | Done |
| BLWI-6 | Chapter "Bigs & Littles" list and record page | 3 | | Done |
| BLWI-7 | CSV upload | 3 | | Done |
| BLWI-8 | Tree layout and Plotly figure (pure code) | 1 | | Done |
| BLWI-9 | Family tree page | 3, 8 | Manual theme check | Built and tested |
| BLWI-10 | Profile card | 5, 6, 9 | | Done |
| BLWI-11 | Role guide, QA seed command, docs, full test run | all | Manual checks | Built and tested |

Build order: BLWI-1, 2, 3, then 4, 5, 6 and 7 in any order. BLWI-8 can be built any time
after BLWI-1. Then 9, 10 and 11.

## What was asked for

| # | Requirement (owner, 2026-10-20) | Where it lands |
|---|---|---|
| R1 | Record that one roster member is another roster member's Big, which also gives each Big their Littles. | BLWI-1, BLWI-2 |
| R2 | Every chapter does Big/Little. It is part of the NME manual, so each new member has a Big Brother mentor. | Member-facing everywhere |
| R3 | Bigs sometimes change, so that has to be supported. | Q1, BLWI-2 |
| R4 | Usually one Big, but a Big can take "twins" (two Littles in one term), so the same Big can be picked more than once in an NME class. | BLWI-1 (no limit per Big), BLWI-4 |
| R5 | It is for the final Big decided at initiation, not the temporary "test" Bigs some chapters use during NME. | Q9, Q10 |
| R6 | Quick entry on the initiation report. | BLWI-4 |
| R7 | Members can add it on their own Edit My Info page. | BLWI-5 |
| R8 | Officers can add the relationship for anyone in the chapter. | BLWI-6 |
| R9 | Member selection uses the usual type-to-search member dropdown. | BLWI-3 |
| R10 | A chapter page with a Plotly tree graph (https://plotly.com/python/tree-plots/), usable as an HTML family tree / connection chart. | BLWI-8, BLWI-9 |
| R11 | Officers can upload a CSV with the headers `badge_number_big,badge_number_little`. | BLWI-7 |

## Questions for review

Each question shows the default the build is using. Write a letter or your own wording on
the **Answer:** line.

### Q1. When a member's Big changes, what happens to the old Big?

- **A (default):** Keep it. The member's profile shows "Former Big: Name". The tree shows
  only the current Big.
- **B:** Replace it. Only admins can still see the old one, in Django admin.
- **C:** Keep it and also draw former Bigs in the tree as a dashed line.

The BLWI-1 model already supports all three, so this only changes what pages show.

**Answer:** Go with B

### Q2. Who can view a chapter's family tree?

- **A (default):** Any signed-in member, for any chapter. This matches chapter pages and
  member profiles today.
- **B:** Members of that chapter, plus RDs, National Officers and Admins.
- **C:** Chapter officers, RDs, National Officers and Admins only.

**Answer:** B

### Q3. What can a member record on their own Edit My Info page?

- **A (default):** Set, change or remove their own Big. Add a Little who has no Big
  recorded yet. Remove a Little they recorded themselves. Changing a Big that someone else
  already recorded goes through an officer.
- **B:** Only their own Big.
- **C:** Their own Big, plus add or change their Littles freely, even overriding a Big
  someone else recorded.

**Answer:** A

### Q4. Who manages a whole chapter's records (record page, CSV upload, removing anyone's)?

Today the officer group is only the 5 executive officers. The New Member Educator is a
committee chair and is not in that group.

- **A (default):** Chapter officers plus the New Member Educator. The extra roles live in a
  Config setting, `BIG_LITTLE_MANAGER_ROLES`, so they can be changed without a deploy.
  National Officers and Admins can manage any chapter through the chapter switcher.
- **B:** Chapter officers only, plus National Officers and Admins.

**Answer:** A

### Q5. Do entries made by members need officer approval?

- **A (default):** No. Saved immediately, showing who entered it and how. Officers can
  correct anything.
- **B:** Yes. An officer approves each member entry. This adds a Viewflow approval step and
  a larger build.

**Answer:**A

### Q6. The Plotly tree example uses the igraph package to place the nodes. Add it?

- **A (default):** No. Use our own small layout code, so there is no new package to install
  on PythonAnywhere. The drawing itself is the same Plotly approach as the example.
- **B:** Add igraph to the requirements, as the example does.

**Answer:** B

### Q7. Can a Big be from another chapter (a transfer, or a colony's sponsoring chapter)?

- **A (default):** Same chapter only in the app. Admins can record rare cross-chapter cases
  in Django admin, and the tree labels such a Big with their chapter.
- **B:** Let officers pick a Big from any chapter.

**Answer:** A

### Q8. When a CSV row gives a member a different Big than the one on file:

- **A (default):** Replace it, keep the old one as a former Big (per Q1), and flag the row
  "changed (was Name)" in the results.
- **B:** Skip the row and report it as a conflict to fix by hand.

**Answer:** A

### Q9. Which members can be picked as a Big or a Little?

- **A (default):** Anyone on the chapter roster except PNMs and the depledge, nonmember and
  friend statuses. Alumni, and members who are away, deceased, resigned or expelled, stay
  pickable because the family line is history. PNMs cannot record a Big, which keeps the
  temporary "test" Bigs out.
- **B:** Also exclude resigned and expelled members.

**Answer:** A

### Q10. Wording on screen

- **A (default):** Labels say "Big" and "Little". Help text says "Big Brother mentor" (the
  NME manual's wording) and "final Big, chosen at initiation".
- **B:** Something else (write it in).

**Answer:** A

### Q11. Should the Big column on the initiation report be required?

- **A (default):** Optional. Blank is allowed, and the Big can be added later from Edit My
  Info or by an officer.
- **B:** Required for every new member being initiated. Note this would block a candidate
  chapter's first class, which has no initiated members to pick from.

**Answer:** A

### Q12. Should anyone be emailed about pairings?

- **A (default):** No emails in v1.
- **B:** Email the Big and the Little when someone else records their pairing.

**Answer:** A

### Smaller defaults (no answer needed unless you disagree)

- **S1.** A pairing belongs to the Little's initiation chapter (taken from the initiation
  report), or their current chapter if there is no initiation record. That decides whose
  tree it appears in, even after a transfer.
- **S2.** "Remove" deletes a pairing outright, for entries made by mistake. Recording a
  different Big is how a real change is made, so the history stays accurate.
- **S3.** The chapter "Bigs & Littles" list can be read by every member of the chapter. Only
  managers see the Change and Remove buttons. This is how External Orgs works today.
- **S4.** The tree only draws members who are in at least one pairing. A line under it
  counts initiated members with no Big recorded, with a link for managers to the list
  filtered to them.
- **S5.** Above 150 people, the tree opens on the largest family, with a picker for the
  others. A link with `?member=<id>` opens that member's family and highlights them.
- **S6.** Hovering a name shows the name, roll number, initiation term, Big and number of
  Littles. Clicking opens the member's profile. Status only appears as the legend groups
  Active, Alumni and Other.
- **S7.** CSV upload: extra columns such as names are ignored; .csv files only; 5 MB and
  5,000 rows at most; every row is checked before any row is saved; uploading the same file
  twice changes nothing the second time; a Little listed twice in one file is an error. The
  upload page offers a template file with just the two headers.
- **S8.** New Members menu items: "Bigs & Littles" and "Family Tree". A "Family tree" button
  on the chapter page. The list page also appears in the Membership group of the forms page,
  next to the initiation report.
- **S9.** No Dash. The tree is a plain Plotly chart, which avoids the stale-callback errors
  the Dash dashboards have had.
- **S10.** Links in the tree go through a small `/biglittle/member/<id>/` redirect, so the
  page never prints every member's username (usernames are email addresses).

## Shared preamble

Read this before starting any work item.

- **Local dev is docker.** Never use the host virtualenv.
  - Tests: `docker exec thetataucmt_local_django pytest <path> -v --tb=short`
  - Management: `docker exec thetataucmt_local_django python manage.py <cmd>`
- **Working style:** models and migrations first, then pause for review; then services,
  then views and templates, then tests per acceptance item. Gate every capability by role.
- **No Viewflow** (no approval step, see Q5): plain class-based views plus a `services.py`
  layer, like `notes`, `objectives` and `transitions`.
- **Feature catalog:** every new page gets an entry in
  `thetatauCMT/guides/fixtures/feature_registry.json` in the same change. Verify with
  `load_feature_registry --dry-run` and `pytest thetatauCMT/guides`. A `url_name` must answer
  a GET (link the page hosting a POST-only control, with `url_fragment`).
- **Anonymizer:** register every new model in `anonymizer/biglittle.py` in the same step as
  `makemigrations`, or `core/tests/test_anonymizer.py` fails.
- **Wording:** "Big" and "Little" (Q10). "PNM" or "new member", never "pledge" for a person.
  No em dashes in anything a user reads. Empty values show "None".
- **Every form submission shows a specific success message.**
- **Front end:** no inline `<script>` blocks or inline event handlers in new templates; pass
  data with `json_script` and use a static JS file. Everything must work in the light, dark
  and system themes.
- **Housekeeping:** `makemigrations biglittle` (scoped, so known third-party drift is not
  generated). Run black and flake8 on the files you touched only, never a whole directory.
- **Test gotchas:**
  - Use the `auto_login_user` fixture. It creates the Risk Management signature the
    middleware demands.
  - `UserFactory` leaves `current_status` blank. Pass `status="active"` (or another status).
  - Two `ChapterFactory()` calls can return the same chapter. Pass `name=` with a real
    `GREEK_ABR` value such as `"alpha"`, `"beta"` or `"delta"`.
  - Superuser tests need `@override_settings(DEBUG=True)` to get past the 2FA middleware.
  - Known order-dependent flaky tests exist (see `.github/copilot-memory/thetatauCMT-status.md`);
    re-run the file alone before blaming a change.

## Codebase facts that shape the design

- **Badge numbers are per chapter.** `Chapter.next_badge_number()` takes the highest number
  within the chapter, so a CSV badge number must be looked up in the uploader's chapter,
  never across the whole fraternity.
- **The usual member dropdown is officer-only.** `users:autocomplete` returns nothing unless
  the requester is in the officer or natoff group, so members cannot use it on their own
  page. BLWI-3 adds a chapter-scoped picker that uses the same widget.
- **The officer group is the 5 executive officers.** The New Member Educator
  (`pledge/new member educator`) is a committee chair and is not in it (Q4).
- **The initiation report shares one form class across requests.** Anything per-request must
  go through `form_kwargs` on both GET and POST. Editing `base_fields` per request is what
  broke the badge field for candidate chapters in 2026-09.
- **Edit My Info (`users.UserDetailUpdateView`) is a `MultiFormsView`.** Each form is a
  `form_classes` entry, posted with `action=<name>` and handled by `<name>_form_valid`. Its
  member information form already loads the select2 assets.
- **External Orgs is the closest existing pattern.** `UserOrgListView`, `UserOrgCreateView`
  and `UserOrgDeleteView`: any member reads the chapter list, members add their own, officers
  manage everyone's.
- **Plotly 6.8 is installed (it ships plotly.js 3.6.0); this feature adds igraph 1.0.0
  (Q6).** Today Plotly is only used through Dash dashboards. The production Content Security
  Policy is report-only and already allows `https://cdn.plot.ly`.
- **CSV upload pattern:** `attendance.forms.NationalAttendanceUploadForm` (.csv only, 5 MB cap).
- **Usernames are email addresses,** so `users:profile` links expose them (S10).

## Data model

One table, built in BLWI-1: `biglittle.BigLittle`.

| Field | Type | Notes |
|---|---|---|
| `big` | FK to User, cascade, related name `links_as_big` | The mentor. |
| `little` | FK to User, cascade, related name `links_as_little` | |
| `chapter` | FK to Chapter, cascade, related name `big_little_links` | Whose tree the pairing appears in (S1). |
| `source` | Text choice | `initiation`, `member`, `officer`, `upload` or `admin`. |
| `created_by` | FK to User, set null | Who recorded it. |
| `ended` | Date and time, nullable | Empty while this is the Little's current Big; set when the Big changes. Ended rows only show in Django admin (Q1). |
| `ended_by` | FK to User, set null | Who recorded the change. |
| `created`, `modified` | From `core.models.TimeStampedModel` | `created` is when the pairing was recorded. |

Rules enforced by the database:

- At most one current Big per Little (unique on `little` where `ended` is empty).
- Nobody is their own Big.
- No limit on how many Littles a Big has, so twins work.

Queryset helpers: `BigLittle.objects.current()` and `.former()`, also available on
`user.links_as_big` (their Littles) and `user.links_as_little` (their Bigs).

## Work items

### BLWI-1: App, model, migration, admin, anonymizer

Build:

- New app `thetatauCMT/biglittle/` (`BigLittleConfig`, shown as "Bigs and Littles"), added
  to `LOCAL_APPS` in `config/settings/base.py` after transitions and before `email_signals`.
- The `BigLittle` model from [Data model](#data-model), and migration `0001_initial`.
- `anonymizer/biglittle.py`: `register_skip([BigLittle])`. The rows only point at members
  through foreign keys, which the User anonymizer already covers.
- Django admin: Little, Big, chapter, source, recorded and ended columns; a Current/Former
  filter; search by either name or the chapter; raw ID pickers; `created_by` filled in on
  add. Admin is the escape hatch for cases the app does not allow (Q7).

Done when:

- [x] Model, migration, admin and anonymizer in place
- [x] A second current Big for the same Little is rejected by the database
- [x] A Little can have one current Big plus any number of ended ones
- [x] Nobody can be their own Big
- [x] One Big can have several current Littles (twins)
- [x] `current()` and `former()` return the right rows, including on `user.links_as_big`
- [x] Admin list loads, filters by Current/Former, and fills `created_by` on add
- [x] `core/tests/test_anonymizer.py` passes
- [x] Questions answered 2026-10-20; none of the answers needed a model change (pause point)

### BLWI-2: Rules and permissions

Build `thetatauCMT/biglittle/services.py`:

- `NOT_INITIATED_STATUSES = {"pnm", "depledge", "nonmember", "friend"}` (Q9),
  `is_initiated(user)`, and `eligible_members(chapter)`: the chapter roster minus those
  statuses, ordered by name.
- `link_chapter_for(little)`: the Little's initiation chapter, else their chapter (S1).
- Readers: `current_big_link(user)`, `current_big(user)` and `current_little_links(user)`.
  There is no former-Bigs reader, because ended pairings only show in Django admin (Q1).
- `can_view_tree(user, chapter)` (Q2): members of that chapter (their own, or the one they
  are viewing through the chapter switcher), RDs of its region, National Officers and
  Admins. "View as member" switches the RD and National Officer routes off.
- `get_manager_roles()`: reads Config `BIG_LITTLE_MANAGER_ROLES`, a comma-separated list of
  role keys, keeping only values in `core.models.ALL_ROLES`. Blank or missing means
  `{"pledge/new member educator"}`. Seed the row in
  `thetatauCMT/configs/fixtures/default_configs.json` (`"pk": null`, include `modified` and
  a description).
- `can_manage(user, chapter)`, only for `user.current_chapter`:
  - Admins (`is_admin`) and National Officers (`is_national_officer_group`).
  - A National Officer with "view as member" turned on only through a real or impersonated
    chapter role, the same rule as `core.views.OfficerRequiredMixin.check_membership`.
  - The officer group.
  - Anyone currently holding a role from `get_manager_roles()` (Q4).
- `can_remove(user, link)`: a manager of `link.chapter`, the Little, or the Big if they
  recorded it themselves (Q3).
- `would_create_cycle(little, big)`: walk up the Big's current-Big chain (with a visited set
  and a hard cap). True if it reaches the Little.
- `validate_pairing(little, big)`: the self and loop checks, shared by `set_big` and the
  forms.
- `set_big(little, big, *, actor, source)` returns the link, the outcome (`created`,
  `changed` or `unchanged`) and the previous Big. One transaction, locking the Little's
  current row. The same Big is a no-op. A different Big ends the old row (`ended`,
  `ended_by`) and creates the new one. Raises `BigLittleError` (a `ValidationError`) for
  self, for loops, and for a concurrent insert caught as an `IntegrityError`.
- `remove_link(link)`: deletes the row (S2).
- The "add a Little who has no Big yet" rule (Q3) lives in `AddLittleForm` (BLWI-5), the
  only place that needs it.

Done when:

- [x] Every rule above has tests, including the "view as member" and "hide admin" toggles, a
  Config override, an attempted three-generation loop, twins, and a change that ends the
  old pairing

### BLWI-3: Shared endpoints

Build:

- `thetatauCMT/biglittle/urls.py` (`app_name = "biglittle"`), and in `config/urls.py`
  `path("biglittle/", include("thetatauCMT.biglittle.urls", namespace="biglittle"))`.
- `BigLittleMemberAutocomplete` at `member-autocomplete/` (django-autocomplete-light
  `Select2QuerySetView`, sign-in required):
  - Choices are `eligible_members(request.user.current_chapter)`, with an optional
    `exclude_self` forward.
  - The search matches names, or an exact badge number when the term is all digits.
  - Results read "Name (#1234)" when the badge number is real (below 999999999).
  - No "create" option.
- `BigLittleManagerRequiredMixin`: sign-in required, then `can_manage(user,
  user.current_chapter)`, else an error message and a redirect to `biglittle:list`.
- `BigLittleRemoveView` at `<int:pk>/remove/`, POST only: check `can_remove`, call
  `remove_link`, show a success message naming both people, then redirect to a page chosen
  on the server (the list page for managers, otherwise `users:detail#big_little`). Never
  redirect to a URL taken from the request.
- `MemberProfileRedirectView` at `member/<int:pk>/` (sign-in required): redirects to that
  member's `users:profile` (S10).
- `thetatauCMT/static/js/biglittle.js`: one delegated handler that asks for confirmation on
  any `form[data-confirm]`. Do not copy `templates/users/org_remove_button.html`, which puts a
  member's name inside an inline `onsubmit` script (see the last section).

Done when:

- [x] Picker: signed-out gets nothing; only the requester's current chapter; PNMs and other
  chapters excluded; badge search works; a National Officer using the chapter switcher sees
  that chapter
- [x] Remove: every allowed and refused combination from `can_remove`; GET answers 405
- [x] Profile redirect works and requires sign-in

### BLWI-4: Big column on the initiation report

Build:

- `thetatauCMT/forms/forms.py`, `InitiationForm`:
  - An optional `big` field: a `ModelChoiceField` using the DAL `ModelSelect2` widget
    pointed at `biglittle:member-autocomplete`. Label "Big", help text per Q10, a
    placeholder, and `aria-label="Big"` because the table hides labels.
  - `__init__(..., chapter=None)` sets its choices to `eligible_members(chapter)`.
  - Add `"big"` to `InitiationFormHelper.layout`.
- `thetatauCMT/forms/views.py`, `InitiationView`:
  - Build `InitiationFormSet(..., form_kwargs={"chapter": chapter})` in both
    `get_context_data` and `post`. Do not touch `base_fields`.
  - After each initiation that actually saved (not the duplicates skipped on
    `IntegrityError`), call `set_big(little=member, big=..., actor=request.user,
    source="initiation")`.
  - A `BigLittleError` becomes a WARNING message. The INFO summary adds the members whose
    Big was recorded.
- `thetatauCMT/templates/forms/initiation.html`:
  - A "Big" column header after Badge. The field is last in the form, so it renders through
    the existing generic cell.
  - Rebalance the column widths.
  - One more instruction bullet: pick the final Big chosen at initiation; the same Big can
    be picked for two new members; leave it blank if it is not decided yet, since it can be
    added later.
  - Candidate chapters still work: Badge hidden, Big shown.
- Registry: reword the `initiation-report` long description to mention the Big.

Done when:

- [x] GET shows the Big column and the picker
- [x] POST with a Big creates a pairing with source "initiation", recorded by the officer, in
  the officer's current chapter
- [x] Twins: two new members with the same Big both get pairings
- [x] A Big from another chapter, or a PNM, is rejected and nothing is saved
- [x] Leaving Big blank behaves exactly as today; existing initiation tests pass unchanged
- [x] A row skipped as a duplicate initiation creates no pairing

### BLWI-5: "My Big and Littles" on Edit My Info

Build:

- `thetatauCMT/biglittle/forms.py`: `MyBigForm` (a `big` picker) and `AddLittleForm` (a
  `little` picker).
  - Both take `user`, limit choices to `eligible_members(user.chapter)` minus the user, and
    run the loop check.
  - `AddLittleForm` also runs `member_can_add_little`, with the message "Name already has a
    Big recorded (Name). Ask a chapter officer to change it."
- `thetatauCMT/users/views.py`, `UserDetailUpdateView`:
  - Add `"big"` and `"little"` to `form_classes`, with `get_big_kwargs` and
    `get_little_kwargs`.
  - `big_form_valid` and `little_form_valid` call `set_big(source="member")`, show a SUCCESS
    message (or INFO "No changes were made."), and redirect to `#big_little`.
  - Context `big_little`: whether the member is initiated, their current Big, and their
    Littles with a can-remove flag. No former Bigs (Q1).
- `thetatauCMT/templates/users/user_detail.html`: an accordion item `id="big_little"` titled
  "My Big and Littles", after External Organizations.
  - PNMs see "You can record your Big after you are initiated."
  - Initiated members see their current Big (with Remove), their Littles (Remove only on
    the ones they recorded) and the two forms.
  - Open the panel when one of its forms has errors.
  - Do not print the new forms' media. The member information form on this page already
    loads the select2 assets, and loading them twice initializes the widgets twice.
- Registry: new `my-big-little` in the Getting started area, `url_name` `users:detail`,
  `url_fragment` `big_little`.

Done when:

- [x] A PNM sees the note and no forms
- [x] A member sets their Big; changing it replaces the old one (Q1)
- [x] Themselves, another chapter's member and a PNM cannot be chosen
- [x] Adding a Little works; adding one who already has a Big shows the error; a loop is
  refused
- [x] Every path shows a message

### BLWI-6: Chapter "Bigs & Littles" list and record page

Build:

- `thetatauCMT/biglittle/filters.py`: name, status group (Active, Alumni, All) and "Big
  recorded" (yes or no), with a form helper.
- `thetatauCMT/biglittle/tables.py`, on `core.tables.CMTTable`, over the chapter's eligible
  members:
  - Name linked to the profile, status, and initiation date.
  - Current Big (a Subquery) and number of current Littles (a filtered Count).
  - An actions column only for managers: Change opens the record page with `?little=<id>`;
    Remove posts with `data-confirm`.
- `BigLittleListView(LoginRequiredMixin, PagedFilteredTableView)` at `/biglittle/`
  (`biglittle:list`): any member sees their current chapter (S3). Buttons: "Record or change
  a Big" and "Upload CSV" for managers, "Family tree" for everyone.
- `BigLittleRecordView(BigLittleManagerRequiredMixin, FormView)` at `record/`:
  - `RecordBigForm` with Little and Big pickers and `?little=` prefill.
  - One message per outcome: "Recorded A as B's Big.", "Changed B's Big from A to C." or
    "No change: A was already B's Big."
- Templates `thetatauCMT/templates/biglittle/big_little_list.html` and `record_form.html`.
- `thetatauCMT/templates/base.html` Members menu: "Bigs & Littles" and "Family Tree" (S8).
- Registry: new `big-little-list` in Roster & members (member audience, roles
  `pledge/new member educator` and `vice regent`). Add the key to the Membership group of
  `FORM_GROUPS` in `thetatauCMT/forms/views.py`, after `initiation-report`.

Done when:

- [x] A plain member sees the list with no action buttons
- [x] An officer and the New Member Educator see the actions and can record
- [x] Other chapters' members never appear
- [x] Filters work
- [x] Record shows the created, changed and unchanged messages; non-managers are redirected
  on GET and POST
- [x] A National Officer can manage another chapter through the chapter switcher

### BLWI-7: CSV upload

Build:

- `BigLittleUploadForm`: .csv only, 5 MB cap (same checks as
  `attendance.forms.NationalAttendanceUploadForm`).
- `services.import_big_little_csv(file_bytes, chapter, actor)` returns a result per line
  plus totals:
  1. Decode `utf-8-sig`. Normalize headers (trim, lower case, spaces to underscores).
     Require `badge_number_big` and `badge_number_little` and ignore other columns. Stop at
     5,000 rows.
  2. Check every row before saving any. Badge numbers must be whole numbers, and each must
     match exactly one member of the uploader's chapter:
     - none: "No member of Chapter has badge number N"
     - several: "More than one member of Chapter has badge number N. Fix the roster first."
     The Little must be initiated, cannot be their own Big, and cannot appear twice.
  3. Apply the good rows one at a time with `set_big(source="upload")`: created, changed
     (was Name), or unchanged. A loop is reported on its own line.
- `BigLittleUploadView(BigLittleManagerRequiredMixin, View)` at `upload/`:
  - GET shows the form and instructions.
  - POST shows a results table on the same page, plus a summary message.
  - `upload/template.csv` returns the header row only.
- Template `thetatauCMT/templates/biglittle/upload.html`. The list page links to it.
- Registry: new `upload-big-little` in Roster & members (officer audience, role
  `pledge/new member educator`).

Done when:

- [x] Happy path, plus a file with a byte-order mark and upper-case headers
- [x] A missing header saves nothing
- [x] Each of these gives a per-line error: not a number, unknown badge, ambiguous badge,
  another chapter's badge, a PNM, self, a Little listed twice, a loop inside the file
- [x] A change replaces the Big (the old pairing stays in admin only) and reports
  "changed (was Name)"
- [x] Uploading the same file again reports every row unchanged
- [x] A wrong extension or an oversized file is rejected; non-managers are redirected; the
  template download has the two headers

### BLWI-8: Tree layout and Plotly figure

Build `thetatauCMT/biglittle/tree.py`, with no database access so it is fast to test:

- `build_forest(links)`: people and family roots. Each Big's Littles are ordered by badge
  number, then name, which keeps an NME class together. Bad data that forms a loop must not
  hang it.
- `layout_forest(...)`: a horizontal position and a generation for every person, from
  igraph's Reingold-Tilford layout (`Graph.layout_reingold_tilford`, as in the Plotly
  example, Q6) with one root per family. People are numbered in roll order so each NME
  class stays together, and a loop in bad data is broken before the layout runs.
- `family_root(...)` and `families(...)` (each root and its family size) for the picker.
- `build_figure(...)`, built the same way as the Plotly tree-plots example:
  - One line trace for all connections (`None` between segments, no hover).
  - One marker-and-label trace per legend group (Active, Alumni, Other).
  - Hover text per S6, and `customdata` holding the profile redirect URL.
  - A highlight trace for the focused member.
  - Hidden axes, first generation at the top, height from the number of generations,
    transparent background.
  - Names go through `django.utils.html.escape` first, because Plotly renders some HTML in
    labels.
  - The figure records how many people sit on the bottom row so the page can size its width.

Done when:

- [x] Nobody overlaps within a generation; every Big is centered over their Littles; families
  are separated; output is the same every run
- [x] A long chain, twins, a single pairing, and looping bad data all work (the loop case
  finishes)
- [x] Connection segments and `None` separators are right; names are escaped

### BLWI-9: Family tree page

Build:

- `FamilyTreeView(LoginRequiredMixin, TemplateView)` at `<slug:slug>/tree/`
  (`biglittle:tree`):
  - Members of that chapter, RDs of its region, National Officers and Admins
    (`can_view_tree`, Q2). Anyone else is sent to their own chapter's tree with a message.
    An unknown chapter is a 404.
  - One query for the chapter's current pairings, read with `.values()` (both people and
    their initiation dates). Loading User objects instead costs one more query per person,
    because `User.address_changed` is a `MonitorField` that reads the address on load.
  - `?member=<id>`, `?family=<id>` and the 150-person limit per S5.
  - Context: the figure as plain JSON, the plotly.js CDN address built from
    `plotly.offline.get_plotlyjs_version()` (confirm that function exists in plotly 6.8),
    the family list, a nested outline, the counts, and `can_manage`.
- `thetatauCMT/templates/biglittle/family_tree.html`:
  - A family picker (GET form).
  - The chart container (`role="img"`, an `aria-label`, scrolls sideways when wide).
  - `{{ figure|json_script:"family-tree-figure" }}`.
  - A "Text version of the tree" `<details>` block with a nested list of profile links.
  - An empty state (members: record your Big; managers: record or upload) and the S4 count.
- `thetatauCMT/static/js/family_tree.js`:
  - `Plotly.newPlot` with a responsive config, no Plotly logo, and a PNG download named
    after the chapter.
  - Width of at least about 110 px per bottom-row person.
  - Colors from the current theme (light, dark or system).
  - Clicking a person opens their profile.
- `thetatauCMT/templates/chapters/chapter_detail.html`: a "Family tree" button in the header,
  shown only to viewers who may open that tree (Q2).
- Registry: new `family-tree` in Roster & members, `url_kwargs` `{"slug": "@chapter_slug"}`.

Done when:

- [x] Signed-out users are sent to sign in; a member of another chapter is sent to their own
  tree; an RD of the region, a National Officer and an Admin can view it (Q2)
- [x] The figure and the outline are on the page; names are escaped in the outline
- [x] `member`, `family` and the 150-person limit behave per S5
- [x] The empty state shows when there are no pairings
- [x] The number of queries does not grow with chapter size
- [ ] Works in light and dark themes (manual check)

### BLWI-10: Profile card

Build:

- `UserProfileView.get_context_data` in `thetatauCMT/users/views.py`:
  - Current Big and Littles. No former Bigs (Q1).
  - Shown to the member themselves and to viewers who may open that chapter's tree, so
    pairings are not visible across chapters (Q2).
  - A link to the tree focused on this member.
  - An edit link: the member themselves get Edit My Info `#big_little`; a manager of their
    chapter gets the record page with `?little=`.
- `thetatauCMT/templates/users/user_profile.html`: a "Big and Littles" card after Contact, so
  Basics and Contact keep their row. Hidden when empty, except for the member themselves
  (when initiated), who sees a prompt to record their Big.
- Registry: reword `my-profile` to mention Big and Littles.

Done when:

- [x] The card shows the Big and Littles, and no former Bigs
- [x] Members of other chapters do not see the card (Q2)
- [x] The member and managers get their edit links; other viewers do not
- [x] Hidden for other viewers when empty

### BLWI-11: Wrap-up

Build:

- Role guide `pledge/new member educator` in `feature_registry.json`: a step "Record each
  new member's Big" pointing at `big-little-list`, cadence each term.
- `thetatauCMT/biglittle/management/commands/seed_big_little_demo.py`:
  - Uses `core.seed_guard.ensure_seeding_allowed`; options `--chapter`, `--reset` and
    `--force`.
  - Builds a few generations from the chapter's existing initiated members in roll order,
    including twins and one changed Big.
  - Safe to re-run, and tested against a fresh test database, not only the dev container.
- Notes: a repo memory entry, a line in `.github/copilot-memory/thetatauCMT-status.md`, and a
  deploy note in `docs/deploy.md`.
- Full test run and the manual checks below.

Done when:

- [x] Registry dry run is clean and the guides tests pass
- [x] The seed command works on a fresh database
- [x] The full suite is at baseline (2026-10-20: 3,492 passed, 16 skipped, 0 failed)
- [ ] Manual checks done

## Verification

```bash
docker exec thetataucmt_local_django python manage.py makemigrations biglittle --check --dry-run
docker exec thetataucmt_local_django pytest thetatauCMT/biglittle -v --tb=short
docker exec thetataucmt_local_django pytest core/tests/test_anonymizer.py thetatauCMT/guides -q
docker exec thetataucmt_local_django pytest thetatauCMT/forms/tests/test_views.py -k initiation -q
docker exec thetataucmt_local_django pytest thetatauCMT/users -q
docker exec thetataucmt_local_django python manage.py load_feature_registry --dry-run
docker exec thetataucmt_local_django python manage.py anonymize_db --check_only
docker exec thetataucmt_local_django pytest --tb=no -q
```

Full suite on 2026-10-20 after the build: 3,492 passed, 16 skipped, 0 failed. One or two
known order-dependent flaky tests can fail on a full run; re-run that file alone.

Manual checks, after seeding a chapter you belong to
(`docker exec thetataucmt_local_django python manage.py seed_big_little_demo --chapter <slug>`;
add `--reset` to start over):

- Initiation report with twins, and for a candidate chapter (no Badge column, Big column
  present)
- Edit My Info as a PNM and as an initiated member
- List and record pages as a plain member, an officer and the New Member Educator
- CSV upload with the template, and with a file containing errors
- Tree page in light and dark themes, with `?member=`, clicking a name, and the PNG download
- Profile card as the member, as a manager and as another member

## Deployment notes

Production is PythonAnywhere (see `docs/deploy.md`). One new Python package,
`igraph==1.0.0` (Q6), in `requirements/base.txt`.

1. `pip install -r requirements/production.txt`. igraph installs from a prebuilt wheel
   (manylinux_2_28, so the server needs glibc 2.28 or newer). If pip starts compiling it
   from source, stop and check the PythonAnywhere system image first.
2. `python manage.py migrate`
3. `python manage.py collectstatic --noinput --settings=config.settings.production` for the
   new JS files, then Reload the web app
4. `python manage.py load_feature_registry`
5. Add the `BIG_LITTLE_MANAGER_ROLES` Config row in Django admin. Never run
   `loaddata default_configs` on production; it overrides values set in admin.

## Out of scope for v1

- Emails about pairings (Q12)
- Tracking the temporary "test" Bigs some chapters use during NME (R5)
- Family trees across chapters or regions, for example a colony sponsored by another chapter
- Exporting pairings, a Big column on the roster, Bigs in the initiation exports (badge
  orders, Blackbaud)
- An approval workflow (Q5)

## Decisions log

Answers move here from [Questions for review](#questions-for-review), with the date and any
follow-up they caused.

| # | Decision | Date | Follow-up |
|---|---|---|---|
| Q1 | **B.** A changed Big replaces the old one. The old pairing is ended and kept, but only Django admin shows it. | 2026-10-20 | No model change; admins use the Current/Former filter. No "Former Big" on any member page. BLWI-2 has no former-Bigs reader; BLWI-5, 6 and 10 adjusted. |
| Q2 | **B.** A chapter's tree is for members of that chapter, plus RDs, National Officers and Admins. | 2026-10-20 | New `can_view_tree` (BLWI-2), used by the tree page and the chapter page button (BLWI-9). The profile card (BLWI-10) follows the same rule so pairings are not shown across chapters. |
| Q3 | A (default). | 2026-10-20 | None. |
| Q4 | A (default): officers plus the New Member Educator, via `BIG_LITTLE_MANAGER_ROLES`. | 2026-10-20 | None. |
| Q5 | A (default): no approval step. | 2026-10-20 | None. |
| Q6 | **B.** Add igraph, as in the Plotly example. | 2026-10-20 | `igraph==1.0.0` in `requirements/base.txt`, installed in the dev container. BLWI-8 uses `Graph.layout_reingold_tilford`. Deployment notes now install the package. |
| Q7 | A (default): same chapter only in the app. | 2026-10-20 | None. |
| Q8 | A (default). | 2026-10-20 | Per Q1 the old pairing is kept for admins only; the results still say "changed (was Name)". |
| Q9 | A (default). | 2026-10-20 | Applies to the Big too: a CSV row or picker cannot name a PNM as a Big. |
| Q10 | A (default). | 2026-10-20 | None. |
| Q11 | A (default): optional. | 2026-10-20 | None. |
| Q12 | A (default): no emails. | 2026-10-20 | None. |

## Unrelated issue noticed during planning

`thetatauCMT/templates/users/org_remove_button.html` puts `{{ record.user }}` inside an
inline `onsubmit="return confirm('...')"` script without `escapejs`. Members can set their
own preferred name, which becomes their display name, so a crafted name could run script in
an officer's browser when the officer clicks Remove on that member's External Orgs row. Fix
it with `escapejs`, or move the confirmation to a `data-confirm` attribute handled by a
static script as BLWI-3 does. Not part of this feature.

Status: Open.
