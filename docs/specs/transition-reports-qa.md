# Transition Reports QA seed data (`seed_transition_reports_demo`)

`seed_transition_reports_demo` (TRWI-12) populates the database with a small, coherent
Transition Reports dataset so the whole feature (TRWI-1..11) can be QA'd end-to-end:
templates and prompts, obligations in every status, a multi-generation report chain,
tags (both prompt-derived and manual), an attachment, mixed acknowledgments, and one
named login account per TRWI-6 access role.

```bash
docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo
docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo --flush
docker exec thetataucmt_local_django python manage.py seed_transition_reports_demo --force
```

## Flags

| Flag | Purpose |
|---|---|
| `--flush` | Delete existing **`[QA] Transitions`** data (only) before seeding: seed users (by email domain), the 4 seed chapters, and the 2 seed regions. Never touches any other chapter, region, or member, and never touches the shared prompt-set templates (those are permanent content, not per-run demo data). |
| `--password <str>` | Password for every seeded login account (default `transitionsqa`). |
| `--force` | Required when `settings.DEBUG` is off (production-like). Without it the command refuses to run. |

Not randomized: there is no `--seed`/Faker option. Every name, chapter, and answer is
hand-written and identical on every run, which is more useful for a QA script than
random text would be, and the command is already fully idempotent without needing a
fixed RNG seed for reproducibility.

## Guardrails

- All generated chapters/regions are named with a `[QA] Transitions ` prefix, and all
  seeded users share the email domain `@transitions-qa.thetatau.local` -- both are only
  ever created by, and only ever removed by, this command.
- Idempotent: templates/prompts are `update_or_create`d, users/chapters/regions are
  `get_or_create`d, and reports are only ever submitted once per obligation, so
  re-running without `--flush` never duplicates anything.
- Reuses the real service layer (`generate_obligations`, `get_or_create_report`,
  `submit_report`, `close_as_na_vacant`, `acknowledge_report`, `set_manual_tags`)
  rather than hand-writing rows, so the seeded data -- tag derivation, template
  resolution, the watson search index -- is exactly what the real app would produce.
- **Side effect to expect:** the command calls the real `generate_obligations()`,
  which scans *every* chapter's officer terms, not just the QA ones. If your dev
  database already has real chapters with officer terms ending soon, you may see a
  handful of new, unrelated obligations appear for them too -- this is the same
  behavior as the daily `generate_transition_obligations` command and is not a bug.

## What gets created

- **Templates** -- the 4 position-type defaults (from `seed_transition_prompt_set`,
  called indirectly by reusing the same rows) plus **one position-specific override**:
  a "Treasurer Transition Report" for `position_key="treasurer"` with an added
  `financial_handoff` prompt, demonstrating exact-match-over-type-default resolution.
- **Regions** -- `[QA] Transitions Region` (Alpha/Beta/Gamma) and `[QA] Transitions
  Region 2` (Delta only), so RD/region scoping has something concrete to exclude.
- **Chapters:**
  - **Alpha** -- the treasurer multi-generation chain, the Regent's own obligation,
    and a missed Scribe obligation.
  - **Beta** -- a national officer, a candidate chapter director, a Council member,
    a submitted Committee Chair report, and a vacant Vice Regent obligation.
  - **Gamma** -- deliberately has **zero** Transition Report activity, so the
    national trend view's "chapters with no submissions" has something to show.
  - **Delta** -- in a **separate region**, with submitted reports for a Chapter
    Officer, a National Officer, and a Candidate Chapter Director (the latter two
    deliberately NOT the same chapter as `natoff`/`ccd`'s own obligations, so their
    own-position-nationally access rule below is demonstrably cross-chapter, not a
    same-chapter coincidence) -- RD-scoped views can be checked to exclude Delta
    while national views include it.
- **Obligations in every status:** `open` (treasurer/regent/CCD/national
  officer/council's own, not yet composed), `submitted` (8 reports, see below),
  `missed` (Scribe, past due, never submitted), `na_vacant` (Vice Regent, closed
  via `close_as_na_vacant`).
- **Reports (8 submitted):**
  - **Treasurer chain at Alpha (3 generations)** -- oldest first: a **rich**, detailed
    report; a **minimal**, bare-minimum-length report (**with a `budget.csv`
    attachment**); and the **most recent**, rich again, **acknowledged** by the
    current successor and given a **manual `expertise` tag** on top of its
    prompt-derived tags.
  - **Council** (`grand regent`, Beta), **Committee Chair** (`events chair`, Beta),
    **Chapter Officer** (`regent`, Delta, outside the QA region), **National
    Officer** (`national director`, Delta), and **Candidate Chapter Director**
    (`candidate chapter director`, Delta) -- one each, rich, covering the
    remaining 3 position types plus the two National-Officer-scoped predecessors
    `natoff`/`ccd` read via the "same position, any chapter" rule.
- **Tags** -- every submitted report gets prompt-derived tags from its real answers
  (`success`/`failure`/`calendar`/`continuity`/`advice`, plus `systems`/`contacts`
  where the template includes those prompts); the most recent treasurer report also
  gets a manual `expertise` tag, so both tag sources are represented.

## Expected visibility per role (TRWI-6)

Every account's password is `transitionsqa` (or whatever you passed to `--password`).

| Account | Role under test | Should see |
|---|---|---|
| `treasurer@transitions-qa.thetatau.local` | Successor officer (current treasurer, Alpha) | Their own open obligation (compose it); all 3 predecessor treasurer reports at Alpha via the handoff packet, with the most recent one's answers shown inline while composing (TRWI-8); **not** Beta/Gamma/Delta's reports. |
| `regent@transitions-qa.thetatau.local` | Regent (Alpha) | Every submitted report for **any** position at Alpha (the treasurer chain, the missed Scribe's obligation) plus their own open Regent obligation; **not** Beta/Gamma/Delta. |
| `rd@transitions-qa.thetatau.local` | Regional Director (`[QA] Transitions Region`) | Every submitted report at Alpha, Beta, **and** Gamma (region-wide); **not** Delta (a different region). Their own "My Reports" table is empty -- RD is assigned via `Region.directors`, not a `UserRoleChange` term, so it has no Transition Report of its own; the empty-state message says so and points at Search reports instead of the generic "you don't hold a position" text. |
| `ccd@transitions-qa.thetatau.local` | Candidate Chapter Director | Only the submitted `candidate chapter director` report at **Delta** (2026-09: no longer everything nationally -- see the access-tightening note below); **not** Alpha/Beta/Gamma's other reports. |
| `natoff@transitions-qa.thetatau.local` | National Officer (`national director`) | Only the submitted `national director` report at **Delta**, plus their own open National Officer obligation, plus the national trend view (`/transitions/trends/`) and the Search reports section on `/transitions/` with chapter/region filters visible (those two stay open to any National Officer -- aggregate counts, not report content). |
| `council@transitions-qa.thetatau.local` | Council / Grand Officer (`grand scribe`) | Every submitted report nationally, **including Delta** -- Council keeps the full "sees everything" access. |
| `outsider@transitions-qa.thetatau.local` | Unrelated member (Gamma) | Nothing -- no obligations, no readable reports, no dashboard/rates/trends links. |

**2026-09 access tightening:** a plain `NATIONAL_OFFICER` role (CCD, National
Director, etc.) used to see every submitted report nationally, same as Council.
That was broader than intended -- only `core.models.COUNCIL` (the "Grand X"
positions plus council delegate) and Admin see everything now; every other
National Officer role sees reports for the SAME position_key they hold, across
chapters, not everything. Regional Director keeps its own separate, region-based
rule unchanged. See `services.get_readable_reports`'s own docstring.

## Suggested QA walkthrough

| Feature area | Where to look |
|---|---|
| Templates/prompts + override (TRWI-2) | Django admin -> Report Templates -> Template Prompts inline; confirm "Treasurer Transition Report" is a separate row from "Chapter Officer Transition Report". |
| Obligations, every status (TRWI-3) | `/transitions/` as `regent@...` -- open, missed, and (after closing) na_vacant all visible for Alpha/Beta. |
| Compose + submit (TRWI-5) | `/transitions/` as `treasurer@...` -> compose the open Treasurer obligation; note the most recent predecessor's answers shown inline (TRWI-8), and the manual tags checklist at the bottom of the form. |
| Access control (TRWI-6) | Log in as each account above and confirm the "Expected visibility" table. |
| Handoff packet + acknowledgment (TRWI-7) | `/transitions/packet/<alpha-chapter-pk>/treasurer/` as `treasurer@...` -- 3 predecessor reports, most recent already marked read. |
| Prior answers while composing (TRWI-8) | Same compose page as above -- "What your predecessor said" under each field. |
| Compliance dashboards (TRWI-9) | `/transitions/` as `regent@...` -- own chapter merged into the one Search reports table (position/status/due date/acknowledged for every obligation, plus a link out wherever a readable report exists); `/transitions/dashboard/chapter/<alpha-chapter-pk>/` as an RD/National Officer inspecting a chapter that isn't their own; `/transitions/dashboard/rates/` as `rd@...` and `natoff@...` (national sees a region filter, RD doesn't). |
| Full history, no archiving/pinning (TRWI-10) | The treasurer handoff packet already spans 3 generations with no pin/archive controls anywhere. |
| Search (TRWI-11) | `/transitions/` (Search reports section) as `natoff@...` -- try `q=card reader`, filter by `tag=risk` or `tag=advice`, filter by `chapter`/`region` (only visible to national-scoped viewers), and `cycle=all` to include the oldest predecessor. |
| National trends (TRWI-11) | `/transitions/trends/` as `natoff@...` or `ccd@...` (denied for `rd@...`/`regent@...`) -- tag frequency table and "Chapters with no submissions" listing Gamma. |

Run with `--flush` any time to reset the demo dataset to a clean, consistent state.
