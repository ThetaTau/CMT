# Task: Candidate-chapter Initiation Report blocked by required Badge field

## Bug report (production)
Candidate chapters (colonies) could not submit the Initiation Report. They
have no badge to order and should not need one; other badge-consuming code
paths were expected to already skip gracefully when there is no badge --
verify that.

## Root cause (thetatauCMT/forms/views.py, InitiationView)
1. `Initiation.badge` is `null=True` but NOT `blank=True`, so the ModelForm-
   generated `badge` field on `InitiationForm` defaults to `required=True`.
   `get_context_data()` narrows the queryset to
   `Badge.objects.filter(Q(name__icontains="Candidate Chapter"))` for
   candidate chapters -- no such `Badge` row exists (confirmed empty in the
   local dev DB too), so the dropdown has nothing valid to select and the
   required field always fails validation.
2. **The sneaky one:** `InitiationFormSet.form` IS the `InitiationForm` CLASS
   itself (`formset_factory` does not copy it), so
   `formset.form.base_fields["badge"]` is a class-level, process-shared,
   mutable field object. `get_context_data()` (GET) mutated it per-request,
   but `post()` built a fresh formset and called `.is_valid()` WITHOUT ever
   reapplying that mutation -- so POST validation ran against whatever
   chapter's config happened to be left over in that worker process from the
   last GET.
3. Secondary latent bug (`InitiationProcess.sync_badge_shingle_invoice`,
   forms/models.py): `if badge_guard_code == "None": continue` compared
   against the STRING `"None"`, but `values_list("badge__code", flat=True)`
   yields Python `None` for a null FK -- never matches, so it would have hit
   `create_line(..., name=None, ...)` and raised a QuickBooks `ValueError`.
   Unreachable for candidate chapters today (the method early-returns for
   them) but reachable for a chartered chapter whose `Initiation.badge` went
   null after the fact (Badge row deleted, `on_delete=SET_NULL`).

## Fix
- `thetatauCMT/forms/views.py`: extracted
  `InitiationView._configure_badge_field(formset)` (sets `.queryset` +
  `.required`, `required=False` for candidate chapters) and call it from
  BOTH `get_context_data()` and `post()` (before `formset.is_valid()`).
  **General lesson: any view that mutates `<formset>.form.base_fields[...]`
  per-request must reapply that mutation on EVERY code path that
  instantiates+validates that formset, not just the GET-render path.**
- `thetatauCMT/templates/forms/initiation.html`: Badge column header only
  shows the required asterisk when `not is_candidate_chapter` (new context
  var set alongside the formset).
- `thetatauCMT/forms/models.py`: `sync_badge_shingle_invoice`'s skip check is
  now `if not badge_guard_code or badge_guard_code == "None":`.

## Tests
- New: `test_initiation_view_post_candidate_chapter_without_badge_succeeds`
  in `forms/tests/test_views.py` -- POSTs the initiation report for a
  candidate chapter with `initiates-0-badge` blank, asserts 302 +
  `Initiation.badge is None`. Empirically confirmed it FAILS without the
  `required = False` fix (temporarily reverted it, reran -> failed; restored
  it, reran -> passed).
- Full `forms` app + `core/tests/test_finances.py`: 584 passed, 10 skipped,
  0 failed. `manage.py check`: no issues (3 silenced).

## QA test data + manual verification steps
Reused the existing idempotent seed command (built for Roll Book QA, but the
same PNM/candidate-chapter data works for the Initiation Report flow -- no
new fixture needed):
```
docker exec thetataucmt_local_django python manage.py seed_rollbook_qa --chapters 1 --pnms 1
```
Creates candidate chapter `[QA] Candidate Chapter 1`, a login-able `regent`
officer (RMP pre-signed so `RMPSignMiddleware` won't bounce the login), and 1
PNM. Confirmed the local dev DB's only `Badge` rows ("Test Cheap Badge"/"Test
Expensive Badge") don't match `name__icontains="Candidate Chapter"`, so this
data genuinely reproduces the empty-badge-dropdown bug for manual QA.

Credentials (2026-09-08 seed run): `regent1@rollbook-qa.thetatau.local` /
`rollbookqa`. PNM: Imani Lozano (`pnm1-1@rollbook-qa.thetatau.local`).
Idempotent/safe to rerun; `--reset` wipes just the seeded rows; bump
`--chapters`/`--pnms` for more data; `--force` only needed if `DEBUG` is off.

Manual steps:
1. Log in as `regent1@rollbook-qa.thetatau.local` / `rollbookqa`.
2. Go to Forms -> Initiate/Depledge Members (`/forms/initiation-selection/`,
   url name `forms:init_selection`).
3. Set the PNM's state to **Initiate**, click Next.
4. On `/forms/initiation/` (`forms:initiation`): confirm the Badge column
   header has NO red required asterisk, and the Badge dropdown has no real
   options (just blank). Fill in Initiation Date, Graduation Date, GPA,
   Test A, Test B (Roll is prefilled). Leave Badge blank. Submit.
5. Expect: redirect back to the selection page with "You successfully
   submitted initiation report for: [Imani Lozano]" -- NOT a "This field is
   required" error under Badge.
6. Verify persisted data at `/admin/forms/initiation/`: her row's Badge
   field is empty.
7. Cleanup when done: `docker exec thetataucmt_local_django python
   manage.py seed_rollbook_qa --reset`.

## STATUS: COMPLETE
Fix + regression test verified (including the revert/reconfirm empirical
check); QA data seeded and wiring double-checked (`chapter.pledges()`
confirmed to return the seeded PNM, officer's RMP pre-signed, `is_officer_group`
True). Manual browser walkthrough not yet run by a human -- steps above are
ready for that.

## Follow-up: hide the Badge dropdown/table entirely for candidate chapters
User feedback after the fix: since candidate chapters never need a badge,
don't just make the field optional -- don't show the Badge dropdown column or
the "Badge Descriptions" table at all for them.

Changes (`thetatauCMT/templates/forms/initiation.html` +
`thetatauCMT/forms/views.py`):
- Badge `<th>` column header now wrapped in `{% if not is_candidate_chapter %}`
  (was: always rendered, only the asterisk was conditional).
- Formset row loop gained `{% elif field.label == "Badge" and is_candidate_chapter %}`
  (renders nothing) so the Badge `<td>` is skipped too, keeping header/row
  column counts aligned; same treatment applied to the `empty_form` row.
- The whole "Badge Descriptions" `<div>`/table block at the bottom is now
  wrapped in `{% if not is_candidate_chapter %}`.
- `InitiationView.get_context_data()`: the `BadgeTable` query + `RequestConfig`
  call only run `if not chapter.candidate_chapter` (skips a needless query for
  candidate chapters, `badge_table` key simply absent from context otherwise).

**Verification detour (informational, not a real bug):** the quickest manual
check misfired at first -- a `docker exec ... python manage.py shell -c "<multi-
line python>"` command through PowerShell got misreported as hung (PowerShell
prints a `>>` continuation prompt for every line of a multi-line `-c` string
while accumulating it; this is normal, not a stuck prompt) and produced a
confusing partial read. Switched to piping a script file via stdin instead
(`Get-Content scratchpad/foo.py | docker exec -i thetataucmt_local_django
python manage.py shell`), which is far more reliable for multi-line Django
shell snippets in PowerShell than an inline `-c "..."` argument -- avoids all
nested-quote escaping issues. Also hit `DisallowedHost`/400 using Django's test
`Client()` from a `manage.py shell` (which loads `config.settings.local`, not
`test.py`) -- `local.py`'s `ALLOWED_HOSTS` doesn't include `testserver`
(Django test Client's default `SERVER_NAME`); fixed with
`Client(SERVER_NAME="localhost")`. Separately, `formset.initial` came back
empty on a re-check because the seeded PNM had, by that point, actually
already been initiated (real `Initiation` row, `badge=None` -- itself a nice
live confirmation the original fix works) so she no longer matched
`chapter.pledges()`; NOT a template bug. Resolved by re-running
`seed_rollbook_qa --reset --chapters 1 --pnms 1` for a clean slate.

**Final confirmed-correct render** (`InitiationView` rendered directly via
`RequestFactory` + `view.render_to_response(...).render()`, bypassing
HTTP/session entirely, toggling `chapter.candidate_chapter` before each
render): candidate chapter -> Badge dropdown column ABSENT, Badge
Descriptions table ABSENT (User/Date/Roll/GPA/Test A/Test B columns still
present and correct); chartered chapter -> Badge dropdown column PRESENT,
Badge Descriptions table PRESENT. `forms` app suite: 582 passed / 10 skipped
/ 0 failed (unchanged from before this follow-up).

**QA data reset per this follow-up:** ran
`seed_rollbook_qa --reset --chapters 1 --pnms 1` -- fresh
`[QA] Candidate Chapter 1` / `regent1@rollbook-qa.thetatau.local` /
`rollbookqa` / PNM Imani Lozano, confirmed un-initiated (`current_status
== "pnm"`, 0 `Initiation` rows) and appearing in `chapter.pledges()`. Same
manual steps as above apply; the Badge column/table should now be absent
entirely on step 4 rather than merely optional.

## Follow-up 2: user reported "hit submit, no error, does not submit"
Live-tested both paths end-to-end in an actual browser (login as the seeded
officer, `forms:init_selection` -> mark Initiate -> `forms:initiation` ->
fill fields -> click Submit) since this couldn't be explained from a code
read alone:
- **Candidate chapter, 1 PNM, Badge column absent** (per Follow-up 1): filled
  User/Date/Roll/GPA/Test A/Test B, left no badge control to touch, clicked
  Submit -> redirected with "You successfully submitted initiation report
  for: [<User: Imani Lozano>]", PNM cleared from the pending list. Worked.
- **Chartered chapter (flipped `candidate_chapter` to False on the same QA
  chapter), 2 PNMs, Badge column present/required**: filled both rows
  including selecting a real Badge option for each (`page.selectOption`),
  clicked Submit -> redirected with both users listed as successfully
  submitted. Worked.

**Could not reproduce the reported bug in either scenario.** Most likely
explanation: the user's browser had the initiation page loaded from BEFORE
this session's mid-work `seed_rollbook_qa --reset` runs (run twice while
iterating/debugging Follow-up 1's verification) -- `--reset` deletes and
recreates the seeded officer AND PNM rows with new PKs, so a stale page
open in their browser at that moment would reference now-deleted user PKs
on submit (and/or their own login session could invalidate, as happened to
the agent's own browser tab mid-testing here, silently redirecting to
sign-in on the next navigation). Asked the user to do a fresh login + fresh
page load and retry; QA data re-seeded clean afterward (fresh, un-initiated
PNM, `candidate_chapter` confirmed still `True` -- `_ensure_chapter` self-
heals this even if the flag was toggled for a test in between, since it
matches on chapter `name` and corrects `candidate_chapter` back to `True`
if it finds it `False`).

## Follow-up 3: real bug found -- orphaned InitiationProcess crashes selection page
User then shared a live Werkzeug debugger page confirming an ACTUAL 500 on
`/forms/initiation-selection/`:
```
File "thetatauCMT/forms/views.py", line 432, in get_context_data
    "initiation": process.initiations.first().date,
AttributeError: 'NoneType' object has no attribute 'date'
```

**Root cause:** during Follow-up 2's live browser testing, real
`InitiationProcess` + `Initiation` rows were created via genuine form
submissions against the seeded PNMs. Immediately afterward,
`seed_rollbook_qa --reset` deleted those seed PNM `User` rows, which
CASCADE-deletes their `Initiation` row (`Initiation.user` FK is
`on_delete=CASCADE`) -- but the M2M `InitiationProcess.initiations` just
loses that one linked row; the `InitiationProcess` itself survives with
ZERO linked initiations ("orphaned"). `InitDeplSelectView.get_context_data()`
then unconditionally called `process.initiations.first().date` for EVERY
process belonging to the chapter, crashing on the orphaned one. Confirmed via
shell: `InitiationProcess.objects.filter(chapter__name="[QA] Candidate
Chapter 1")` had exactly 1 row with `initiations.count() == 0`.

This is a real, general data-integrity edge case (any Initiation row can be
deleted independently of its process -- a member removed from the system,
manual cleanup, etc.), not specific to the QA seed workflow, so it was worth
fixing rather than just avoiding in test data. Grepped for the same unguarded
pattern and found two more instances.

**Fix** (three call sites, all `.initiations.first()` used without a null
check):
- `forms/views.py` `InitDeplSelectView.get_context_data()`: now does
  `first_initiation = process.initiations.first(); if first_initiation is
  None: continue` before building the row -- skips the process entirely
  (nothing meaningful to show: no date, no member names) rather than
  crashing. Matches the sibling `PledgeProcess` loop directly below it in the
  same method, which ALREADY guarded the equivalent case
  (`last_pledge = process.pledges.last(); ... if last_pledge: ...`) --  this
  Initiation loop had simply been missed.
- `forms/models.py` `InitiationProcess.generate_blackbaud_update` and
  `generate_badge_shingle_order`: both built a CSV/badge-order filename from
  `self.initiations.first().date` before ever reaching the per-initiation
  loop. Now fall back to `self.created.date()` (the process's own creation
  timestamp) when there are no linked initiations, instead of crashing.

**Regression test:**
`test_init_selection_process_with_no_initiations_does_not_500` in
`forms/tests/test_views.py` -- creates an `InitiationProcessFactory` then
`.initiations.clear()`s it (reproducing the orphaned state), asserts
`forms:init_selection` still returns 200.

**Verified live in browser** (same session/tab as the crash): reloaded
`/forms/initiation-selection/` after the fix -- loads cleanly, "Initiation
Forms" tab shows an empty table (orphaned process correctly omitted, not
crashing). `forms` suite: 583 passed / 10 skipped / 0 failed (+1 for the new
test). Cleaned up the orphaned process by re-running
`seed_rollbook_qa --reset --chapters 1 --pnms 1` (chapter cascade-delete on
`_reset()` takes the orphaned process with it since `InitiationProcess.chapter`
is `on_delete=CASCADE`); confirmed 0 leftover processes for the QA chapter
afterward, then re-logged-in and reconfirmed the selection page loads clean.
