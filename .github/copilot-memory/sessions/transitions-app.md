# Transition Reports & Lessons Learned — Feature Spec & Work Breakdown

> **Status:** In development (2026-09-05) — TRWI-1 through TRWI-9 are implemented and tested. See "Decisions Log" at the end for the full record of resolved decisions (A-K) plus TRWI-5's (L35-L45), TRWI-6's (M46-M52), TRWI-7's (N53-N61), TRWI-8's (O62-O67), and TRWI-9's (P68-P75) choices awaiting review. Note: CSV export requirement dropped (TRWI-11 only).
> **Approach:** Purpose-built app (custom), no third-party survey dependency. App name: `thetatauCMT.transitions`.
> **File location:** `docs/specs/transition-reports.md`

---

## Shared Preamble (paste once per Copilot/Claude session)

Project conventions for all Transition Report work items:

- **Stack:** Django + PostgreSQL in **Docker** containers (corrected — not Podman; see `.github/copilot-instructions.md`). Reuse existing app patterns, permission helpers, base templates, and notification patterns. The "existing officer duties/tasks tracking system" (`thetatauCMT.tasks`) turns out NOT to fit obligations — see Codebase Review Notes below and TRWI-4.
- **Roles:** Member, Chapter Officer, RD (Regional Director), National Officer, Admin. Regent is a chapter officer position with chapter-wide oversight for this feature.
- **Position sources:** pull positions from the existing definitions in `core.models` — `CHAPTER_OFFICER` (5 exec roles), `CHAPTER_OFFICER_REQUIRED` (7 = those 5 plus pledge/new member educator + risk management chair), `COUNCIL` (8), `NATIONAL_OFFICER` (10), `COMMITTEE_CHAIR` (~19). `ADVISOR_ROLES` (adviser, faculty adviser, house corporation president/treasurer) was considered and **explicitly excluded from v1** (decision 2026-09-04). Do NOT create a duplicate position list.
- **Officer terms already exist:** `users.UserRoleChange` (fields are literally named `start`/`end`, inherited from `core.models.StartEndModel` — not `term_start`/`term_end`) records every officer's term. Obligations derive from these dates via a management command — do not invent a separate term or academic-calendar model. `Chapter.get_current_and_future()` / `get_previous_officers()` / `get_about_expired_coucil()` (`thetatauCMT/chapters/models.py`) already query this exact shape for a sibling feature — reuse the query patterns, don't reinvent them.
- **Working style:** Prefer configuration over hard-coded rules. Propose migrations/models FIRST and pause for confirmation, then services, then views/templates, then tests by acceptance criterion. Gate every capability by role/permission.
- **CSP-safe front end:** no inline `<script>`; use `json_script` + external static JS. (Production CSP is currently report-only, not enforced — still follow the convention.)
- **No Viewflow.** This feature has explicitly no approval step, so the repo's viewflow convention (used for approval workflows such as Volunteer Nominations) does not apply here — use plain `CreateView`/`UpdateView` + a `services.py` layer, matching `notes`/`objectives`, not `nominations`/`forms`.
- **Feature registry is mandatory.** Every new user-facing page must be added to `thetatauCMT/guides/fixtures/feature_registry.json` (standing repo rule, not mentioned in the original proposal) or it is invisible at `/features/` and a guarded test fails. Budget this into every work item that adds a page.
- **Scheduled commands run DAILY only.** Production is PythonAnywhere, which offers no finer-grained cron. Any "reminder schedule" must be one daily command that self-gates per obligation (see `region_officer_reminder_digest.py`'s weekday-gate pattern), not several differently-scheduled jobs.

### Codebase Review Notes (added 2026-09-04, informs every section below)

This proposal was drafted by an LLM without access to the codebase. Below is what changed after reading the actual repo; full detail is inline at each affected TRWI. Highlights:

- **Local dev is Docker, not Podman.**
- **`ADVISOR_ROLES` was considered and excluded from v1** (decision 2026-09-04) — see `CHAPTER_OFFICER_REQUIRED` above for the confirmed required-by-default set.
- **No `term_start`/`term_end` fields exist anywhere** — the source of truth is `users.UserRoleChange.start`/`.end`.
- **`TimeStampedModel` fields are `created`/`modified`, not `created_at`/`updated_at`.** Fixed throughout the data model below.
- **The "existing officer duties/tasks tracking system" (`thetatauCMT.tasks`) does not fit this feature.** `Task`/`TaskDate` are **national** definitions — one `TaskDate` due date applies to every chapter of a given `school_type` at once. There is no way to express "chapter C, position P, due on THIS chapter's own officer's term-end date" without corrupting the shared calendar. TRWI-4 has been rewritten to drop this integration.
- **A near-identical feature already exists and is the pattern to imitate:** `Chapter.get_about_expired_coucil()` + `OfficerUpdateReminder`/`RegionalDirectorOfficerDigest` (`thetatauCMT/users/notifications.py`) + two daily commands (`officer_update_reminder_email.py`, `region_officer_reminder_digest.py`) already detect officer terms ending/expired per chapter and send daily chapter emails plus a weekly RD digest. TRWI-3/4 should follow this shape.
- **Production scheduling is daily-only** (PythonAnywhere has no finer cron — see `region_officer_reminder_digest.py`'s own docstring).
- **RD scoping already exists** as `user.director_regions` (`Region.directors` M2M, used by `awards/eligibility.py`). **No equivalent scoping exists for "candidate chapter director"** — a CCD is just another `NATIONAL_OFFICER` role and lands in the `natoff` group like any national officer, with no chapter subset. **Decided:** treat CCD as a plain national officer (sees all reports); no new scoping built.
- **`guides.UserAcknowledgement`** already models "user said got it to a thing" generically (GFK over `Feature`/`Announcement`). **Decided:** build a dedicated `ReportAcknowledgement` model instead (spelling matches this codebase's `UserAcknowledgement` convention, not the original proposal's `ReportAcknowledgment`).
- **The `django-survey` rejection is reinforced, not contradicted, by the codebase.** `django-survey-and-report` IS already a dependency (`thetatauCMT.surveys` wraps `survey.models.Survey`), but its existing usage (`SurveyDetail` in `thetatauCMT/surveys/views.py`) has to match a question by `question__text__icontains="to contact you"` because the library has no stable prompt identity — exactly the fragility TRWI-8 needs to avoid, and file-upload answers (a hard requirement) aren't supported either. **Decided:** keep the purpose-built app.
- **CSV export has no library in this repo** — NO NEED FOR CSV EXPORT (see `thetatauCMT/awards/exports.py`). `watson` (django-watson) is already installed and registered for 2 models and could cover TRWI-11's full-text search instead of a hand-rolled query.
- **No dedicated nav entry — lives on the Forms landing page instead** (decision 2026-09-04, see TRWI-5). `thetatauCMT/forms/views.py`'s `FORM_GROUPS` + registry-driven `forms:landing` already lists officer/administration forms (`chapter-officers`, `submit-chapter-officers`, ...) — Transition Reports slots into that same "administration" group rather than getting a new top-level nav item.
- **No retention/archiving** (decision 2026-09-04) — full report history is kept forever so a new officer can see everything a predecessor and their predecessors wrote. TRWI-10 rewritten accordingly; `archived_at`/`retention_expires_on` dropped from the data model.
- **No post-submission edit lock** (decision 2026-09-04) — authors may edit their own report indefinitely, even long after their term ends, since new information may come to mind later. TRWI-5's grace-window config is dropped.
- **`core.models.semester_encompass_start_end_date()`/`academic_encompass_start_end_date()` already compute the current semester/academic-year window** — reuse this for the new "generic seasonal reminder" requirement (TRWI-4) instead of hard-coding calendar dates.

### Problem statement

Chapter officers and committee chairs turn over without transferring lessons learned, so chapters repeat avoidable mistakes. Encouragement alone produces sporadic compliance; share drives obscure accountability; routing everything through RDs creates a bottleneck and loses knowledge when RDs depart.

### Design decisions (agreed)

- **Purpose-built app.** Not a generic recurring-submission engine, not a new type on the general submission workflow, and not built on a third-party survey library.
  - *Rationale for rejecting `django-survey`:* no file-upload answer type (artifacts for successors are an explicit requirement), no label snapshotting for historical answers, no stable prompt identity for the prior-answers view, and no way to enforce position-scoped reads without bypassing its views. The template/prompt layer it would have replaced is small.
  - *Confirmed (2026-09-04):* `django-survey-and-report` is already a dependency here (`thetatauCMT.surveys` wraps it for the graduation/depledge surveys), so this isn't a hypothetical trade-off — and the file-upload gap is the deciding factor: some prompts explicitly need attachment uploads, which the library doesn't support. Decision: purpose-built custom app, confirmed.
- **No approval/sign-off.** Reports are submitted and immediately visible to entitled readers; Regents/RDs review after the fact for quality. This avoids the RD-as-clearinghouse bottleneck that was explicitly rejected.
- **Nudge + visibility only.** No gating of other functionality on non-submission. Compliance surfaces through reminders and dashboards. (Originally also named "the existing officer duties/tasks tracking system" — dropped; see Codebase Review Notes. The closest existing precedent is the officer-update-reminder email system, not the Task/TaskDate tracker.)
- **Hybrid content:** required structured prompts (the core intervention) + optional file attachments for artifacts.
- **No dedicated nav entry (decision 2026-09-04, supersedes the original "single nav item" plan).** Lives on the existing Forms landing page (`forms:landing`) as another form to submit, grouped with officer/administration forms. The entry point is a filterable **"Transitions" list view** (filters: position/role, and chapter vs. national scope) — the system still derives which obligation(s) a user owes from the position(s) they hold; there are still never per-position menu entries, just no menu entry at all outside Forms landing.
- **Position-scoped successor access:** the current holder of position P in chapter C can read past reports for position P in chapter C.
- **Full history, never archived or deleted (decision 2026-09-04, supersedes the original retention/archive plan).** Every past report stays visible to entitled readers indefinitely so a new officer can see everything a predecessor (and every predecessor before them) wrote. **No pinning either (decision 2026-09-04)** — every report is equally visible, sorted purely by recency; nothing is featured or exempted from anything.
- **Obligations generated by a management command** that detects upcoming officer term ends, plus a separate calendar-driven generic reminder near the end of each semester (TRWI-4).

### Explicitly out of scope for v1

- `ADVISOR_ROLES` positions (adviser, faculty adviser, house corporation president/treasurer) — excluded from v1 (decision 2026-09-04).
- Retention/archiving of reports — full history is retained indefinitely (decision 2026-09-04); see TRWI-10.
- Post-submission edit lock/grace window — reports stay editable by their author indefinitely (decision 2026-09-04); see TRWI-5.
- A dedicated nav entry — this lives on the Forms landing page instead (decision 2026-09-04); see TRWI-5.
- Confidential/private sections restricted to National Officers/Regents (decision 2026-09-04: omit from v1, see Decisions Log).
- LLM-assisted cross-chapter thematic mining (tags + search only in v1).
- Any gating of officer roster updates, certifications, or award eligibility on submission.

---

## Target Data Model

> Propose exact Django field types + migrations per work item and pause for confirmation. Reuse existing timestamp/audit mixins where present: `core.models.TimeStampedModel` gives `created`/`modified` (auto_now), `core.models.StartEndModel` gives `start`/`end`. Use these field names instead of inventing `created_at`/`updated_at`/`term_start`/`term_end`, for consistency with the rest of the codebase.

### ReportTemplate (TRWI-2)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| position_type | CharField (choices) | `CHAPTER_OFFICER` \| `COUNCIL` \| `NATIONAL_OFFICER` \| `COMMITTEE_CHAIR` (`ADVISOR_ROLES` excluded from v1) |
| position_key | CharField (blank) | Specific position from `core.models`; blank = default for the whole type |
| name | CharField | e.g. "Treasurer Transition Report" |
| description | TextField (blank) | Guidance shown at top of the form |
| is_active | Boolean | |
| version | PositiveInteger | Bump when prompts change; responses record the version used |
| created / modified | DateTime | From `core.models.TimeStampedModel` (repo convention — NOT `created_at`/`updated_at`) |

*Template resolution order: exact `position_key` match → `position_type` default → global default.*

### TemplatePrompt (TRWI-2)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| template | FK → ReportTemplate | |
| order | PositiveInteger | |
| prompt_key | SlugField | **Stable identity across templates/versions** — required for the prior-answers view (TRWI-8) |
| label | CharField | Question text shown to the officer |
| help_text | TextField (blank) | Prompting guidance |
| field_type | CharField (choices) | `text` \| `long_text` \| `list` \| `date` \| `contact` |
| is_required | Boolean | |
| min_chars | PositiveInteger (nullable) | Discourages one-word answers |
| max_chars | PositiveInteger (nullable) | Discourages textbook-pasting |
| tag | CharField (blank) | Category for trend analysis (TRWI-11) |

*`prompt_key` is the join key for "show me my predecessor's answer to this same prompt." Treat as immutable.*

### ReportObligation (TRWI-3)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| chapter | FK → Chapter | |
| position_type | CharField (choices) | `CHAPTER_OFFICER` \| `COUNCIL` \| `NATIONAL_OFFICER` \| `COMMITTEE_CHAIR` (`ADVISOR_ROLES` excluded from v1) |
| position_key | CharField | One value from the matching `core.models` set, e.g. `"treasurer"` |
| officer | FK → Member/User (nullable) | Holder at term end; nullable when vacant |
| role_change | FK → `users.UserRoleChange` (nullable, `on_delete=models.SET_NULL`) | **Loose** traceability link to the specific term this obligation was generated from, not a hard dependency — the denormalized `term_start`/`term_end`/`officer`/`position_key` fields below are authoritative for this obligation once generated, so editing or deleting the source `UserRoleChange` row never breaks or cascades into the obligation. |
| term_start | Date | Copied from `role_change.start` at generation time |
| term_end | Date | Copied from `role_change.end`; trigger for obligation generation |
| due_date | Date | `term_end` minus configured offset |
| is_required | Boolean | Derived from position-type config (TRWI-1) |
| status | CharField (choices) | `open` \| `submitted` \| `na_vacant` \| `missed` |
| generated_at | DateTime | |

*Unique together: (chapter, position_key, term_start, term_end) — guarantees command idempotency.*
*Dropped `task_ref`: there is no matching "officer duties/tasks" record type to link to — see Codebase Review Notes and TRWI-4.*

### TransitionReport (TRWI-5)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| obligation | OneToOne → ReportObligation | |
| chapter | FK → Chapter | Denormalized for query performance |
| position_type / position_key | CharField | Denormalized for successor lookup |
| author | FK → Member/User | |
| template | FK → ReportTemplate | |
| template_version | PositiveInteger | Version used at submission |
| status | CharField (choices) | `draft` \| `submitted` \| `na_vacant` |
| submitted_at | DateTime (nullable) | |
| created / modified | DateTime | From `core.models.TimeStampedModel`. `modified` matters here specifically because reports are editable indefinitely (F15) — it's the only "last touched" signal a successor sees, distinct from `submitted_at` (set once, at first submission). |

*Dropped `archived_at`/`retention_expires_on`: no retention window or archive job — full history is kept forever (decision 2026-09-04). See TRWI-10.*
*Dropped `is_pinned`/`pinned_by`/`pinned_reason`: pinning is not needed (decision 2026-09-04) — every report is equally visible. See TRWI-10.*

### ReportAnswer (TRWI-5)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| report | FK → TransitionReport | |
| prompt | FK → TemplatePrompt (nullable) | Nullable so prompt deletion never orphans history |
| prompt_key | SlugField | Denormalized stable key (join target for TRWI-8) |
| prompt_label_snapshot | CharField | Preserves original wording if the template later changes |
| value | TextField | |

### ReportAttachment (TRWI-5)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| report | FK → TransitionReport | |
| file | FileField | Validate type + size |
| description | CharField (blank) | What this document is / why it matters |
| uploaded_by | FK → User | |
| uploaded_at | DateTime | |

*File validation: reuse `upload_validator.FileTypeValidator` (already a dependency, used ~9 places in `thetatauCMT/forms/forms.py`) instead of hand-rolling type checks. There is no generic "Attachment"/"Document" app to extend — every `FileField` in this repo is bespoke, so a new model is the right call. `notes.models.get_upload_path` is a reasonable `upload_to` pattern to copy (path built from chapter slug + user id).*

### ReportAcknowledgement (TRWI-7)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| report | FK → TransitionReport | |
| user | FK → User | Successor who read it |
| acknowledged_at | DateTime | |

*Unique together: (report, user). Read-receipt metric — arguably more valuable than submission rate.*

*Decision (2026-09-04): dedicated model, NOT reusing `guides.UserAcknowledgement` — avoids a cross-app dependency from a new app into `guides`. Spelling matches the codebase's `UserAcknowledgement` convention (the original proposal's `ReportAcknowledgment` was a typo relative to repo style). Editing the report after acknowledgment does NOT reset or flag it (decision 2026-09-04) — acknowledgments persist regardless of later edits, kept simple.*

### ReportTag (TRWI-11)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| report | FK → TransitionReport | |
| tag | CharField | Controlled vocabulary (config) |
| source | CharField (choices) | `prompt` (derived from `TemplatePrompt.tag`) \| `manual` |

---

## Default Prompt Set

> **This is the highest-leverage content in the feature.** The prompts *are* the intervention — a blank text box produces nothing useful. Seeded by TRWI-2; treat `prompt_key` values as immutable once shipped.

### Design principles applied

- **`max_chars` is a feature, not a limit.** It's the primary defense against "pasting in chapters of their math texts." Keep ceilings modest.
- **`min_chars` guards against one-word answers**, but keep it low enough that a genuinely short honest answer passes.
- **Concrete beats abstract.** "Who do you call when the card reader breaks" outperforms "describe operational challenges."
- **Failures need psychological safety.** The label and help text must make candor feel expected, not incriminating.
- **Ordering matters.** Open with successes (easy, builds momentum), then failures (harder, but primed), then reference material (low effort, high value), then forward-looking.

### Core set — `CHAPTER_OFFICER` (default template)

| # | prompt_key | Label | field_type | Req | min | max | tag |
|---|---|---|---|---|---|---|---|
| 1 | `successes` | What went well this term that your successor should keep doing? | long_text | ✅ | 150 | 2000 | success |
| 2 | `failures` | What didn't go well, and what would you do differently? | long_text | ✅ | 150 | 2000 | failure |
| 3 | `campus_contacts` | Key campus contacts — who they are, what they help with, how to reach them | contact | ✅ | 80 | 2500 | contacts |
| 4 | `experts` | Who else should your successor know? (alumni, advisors, vendors, other chapters) | contact | ➖ | — | 2000 | expertise |
| 5 | `key_dates` | Recurring dates and deadlines, and how far ahead to start each | list | ✅ | 80 | 2000 | calendar |
| 6 | `systems_access` | Tools, accounts, files, and passwords-management — where everything lives | long_text | ✅ | 100 | 2000 | systems |
| 7 | `unfinished` | What's unfinished or in-flight that lands on your successor's desk on day one? | long_text | ✅ | 100 | 2000 | continuity |
| 8 | `first_30_days` | If your successor does only three things in their first 30 days, what should they be? | long_text | ✅ | 120 | 1500 | advice |
| 9 | `pitfalls` | What surprised you about this role that nobody warned you about? | long_text | ➖ | — | 1500 | risk |
| 10 | `anything_else` | Anything else your successor should know | long_text | ➖ | — | 2000 | advice |

### Help text (exact wording)

| prompt_key | Help text |
|---|---|
| `successes` | Be specific. "Recruitment went well" doesn't help — "moving the info night to the second week of classes doubled attendance" does. Include what made it work so it can be repeated. |
| `failures` | This is the most valuable box on the page and nobody will hold it against you. Every officer hits problems; the ones who write them down save the next person a semester. Include what you tried, what happened, and what you'd try instead. |
| `campus_contacts` | Name, role/office, email or phone, and — most importantly — what they actually help with. Include the person who *really* gets things done, not just the person whose title suggests they should. |
| `experts` | Alumni who've held this role, advisors, reliable vendors, counterparts at other chapters. Note what each is good for. |
| `key_dates` | One per line. Include the deadline AND the lead time — "IFC dues due Oct 1, start collecting Sept 1" is far more useful than "IFC dues, Oct 1." |
| `systems_access` | Where do documents live? Which accounts exist and who holds credentials? What's on a personal device or personal email that needs to move? Do not paste actual passwords here — say where they're stored. |
| `unfinished` | Open items, pending decisions, ongoing conversations, anything half-built. Include current status and who else is involved. |
| `first_30_days` | The highest-impact actions. Think about what you wish you'd done in your first month instead of what you actually did. |
| `pitfalls` | The unwritten rules, the thing that always takes longer than expected, the meeting that actually matters. |
| `anything_else` | Anything that doesn't fit above. |

### Variation — `COMMITTEE_CHAIR`

> **Resolved (2026-09-04):** pledge/new member educator and risk management chair are simultaneously in `core.models.COMMITTEE_CHAIR` *and* in `CHAPTER_OFFICER_REQUIRED`. Decision: these two use the `CHAPTER_OFFICER` core prompt set below, NOT this `COMMITTEE_CHAIR` variation — they are required like the 5 exec roles, so their prompts should match.

Committee chairs run programs rather than standing offices, so swap in program-specific prompts. **Inherits:** `successes`, `failures`, `campus_contacts`, `key_dates`, `unfinished`, `first_30_days`, `anything_else`.

**Replaces/adds:**

| # | prompt_key | Label | field_type | Req | min | max | tag |
|---|---|---|---|---|---|---|---|
| — | `committee_roster` | Who served on your committee, and who should be asked back? | long_text | ✅ | 80 | 1500 | continuity |
| — | `program_logistics` | Event/program logistics — venues, vendors, timelines, what to book and when | long_text | ✅ | 120 | 2500 | systems |
| — | `budget_actuals` | What did it actually cost vs. what was budgeted? Where were the surprises? | long_text | ➖ | — | 1500 | risk |
| — | `participation` | What drove (or killed) member participation? | long_text | ➖ | — | 1500 | success |

*`systems_access` is optional rather than required for committee chairs.*

### Variation — `COUNCIL` and `NATIONAL_OFFICER`

Broader, cross-chapter scope. **Inherits:** `successes`, `failures`, `experts`, `key_dates`, `unfinished`, `first_30_days`, `anything_else`.

**Replaces/adds:**

| # | prompt_key | Label | field_type | Req | min | max | tag |
|---|---|---|---|---|---|---|---|
| — | `cross_chapter` | Which chapters or regions need particular attention, and why? | long_text | ➖ | — | 2000 | risk |
| — | `external_relations` | External relationships — vendors, partners, host institutions, associations | contact | ➖ | — | 2000 | contacts |
| — | `governance` | Governance items in flight — policy changes, proposals, pending decisions | long_text | ➖ | — | 2000 | continuity |
| — | `national_systems` | National-level tools, accounts, files, and where they live | long_text | ➖ | — | 2000 | systems |

*`campus_contacts` is omitted (not campus-scoped).*

### Controlled tag vocabulary (TRWI-11)

`success` · `failure` · `contacts` · `expertise` · `calendar` · `systems` · `continuity` · `advice` · `risk`

Keep this list short and stable — it's what makes cross-chapter trend counts meaningful.

---

## TRWI-1 — Config foundation & position scope

**Work item:** Configuration for which positions owe transition reports and when.

Create admin-managed config:
- **Position-type scope:** `CHAPTER_OFFICER_REQUIRED` (7 roles: the 5 exec plus pledge/new member educator + risk management chair) = **required** by default (confirmed 2026-09-04) — this matches the existing precedent in `Chapter.get_about_expired_coucil()`, which already treats these same 7 roles as the chapter's "must keep filled" set. `COUNCIL`, `NATIONAL_OFFICER`, and the remaining `COMMITTEE_CHAIR` roles = **in scope but optional** (configurable on/off at the type level, and optionally per position). `ADVISOR_ROLES` is excluded from v1 entirely (confirmed 2026-09-04) — not even as an optional type. Pull actual position lists from `core.models` — do not duplicate them.
- **Per-position override:** mark an individual position required / optional / excluded.
- **Due-date offset:** days before `term_end` that the obligation is due (default: 14).
- **Reminder schedule:** offsets for the per-officer nudges (default: 21, 14, 7, 1 days before due; plus one after). Implementation note: since production (PythonAnywhere) only supports daily scheduled tasks, this is still ONE daily command comparing `due_date - today` against the configured offsets, not multiple cron entries.
- **Generic seasonal reminder offset (added 2026-09-04):** days before the CURRENT semester's end (from `core.models.semester_encompass_start_end_date()`) to send one broadcast nudge to everyone currently holding an in-scope position with an open obligation — separate from the per-officer due-date reminders, because chapters' officer terms don't all end on the same date but the fraternity's academic calendar does. Default: 30 days before semester end. See TRWI-4.
- Future hook (do NOT implement): boolean flag for a confidential section.

**Dropped (confirmed 2026-09-04):** retention window and post-submission edit grace window configs — reports are never archived and stay editable by their author indefinitely. See TRWI-5/TRWI-10.

**Where the config lives:** the scalar values (due-date offset, reminder offsets, generic seasonal offset) are simple admin-tunable numbers — candidates for the existing `configs.Config` key/value store (`Config.get_value(key)`) rather than a new settings model, EXCEPT that `Config.value` is a `CKEditor5Field` (rich text), so a list like the reminder offsets would need parsing out of a text field rather than being natively typed. The per-position-type/per-position required/optional/excluded table is inherently relational (one row per position) and needs its own small model — `Config` is a flat key/value store, not a fit for that part. Propose which values go where before migrating.

Deliver migrations first (pause), then Django admin.

**Tests:** required/optional resolution per position type; `ADVISOR_ROLES` unavailable as a choice; per-position override wins; positions sourced from `core.models`; offset defaults present.

---

## TRWI-2 — Report templates & prompts

**Work item:** Per-position questionnaire templates. See **ReportTemplate** / **TemplatePrompt** tables and the **Default Prompt Set** section.

- Template resolution: exact `position_key` → `position_type` default → global default.
- Versioning: bump `version` when prompts change; reports record the version used and snapshot prompt labels into `ReportAnswer`.
- `prompt_key` is a **stable, immutable identity** used to join a prompt across templates and versions (required by TRWI-8). Enforce uniqueness within a template; reuse the same key across templates when the prompt means the same thing.
- **Seed the Default Prompt Set** exactly as specified above (core `CHAPTER_OFFICER` set plus the `COMMITTEE_CHAIR` and `COUNCIL`/`NATIONAL_OFFICER` variations), including help text, field types, char bounds, and tags.
- **Admin usability matters here.** The national committee will maintain these prompts without developer help: use inline editing under `ReportTemplate`, drag-to-reorder, visible help text on `min_chars`/`max_chars` explaining their purpose, and a warning when editing a `label` on a template that already has submitted responses. `guides.FeatureArea`/`Feature` (Django admin `TabularInline`) is a reasonable precedent for the `ReportTemplate` → `TemplatePrompt` inline.

Deliver migrations first (pause), then admin + resolution service + prompt-set seed.

**Tests:** resolution order correct; version bump does not mutate existing responses; required prompts enforced; char bounds enforced; default prompt set seeded with correct keys/tags; duplicate `prompt_key` within a template rejected.

---

## TRWI-3 — Obligation generation management command

**Work item:** Generate obligations from upcoming officer term ends. See **ReportObligation** table.

**Grounding:** query `users.UserRoleChange` directly (`role__in=<in-scope positions>`, `end__gte`/`end__lte` the lookahead window), the same shape as `Chapter.get_current_and_future()` / `get_previous_officers()` (`thetatauCMT/chapters/models.py`). Don't invent a parallel notion of "term" — `UserRoleChange.start`/`.end` (not `term_start`/`term_end`) IS the term.

Management command (daily, e.g. `generate_transition_obligations`):
- Scan `UserRoleChange` rows for in-scope positions (per TRWI-1) whose `end` falls within the configured lookahead window.
- For each, create a `ReportObligation` with `due_date = term_end - offset`, `role_change` FK'd to the source row.
- **Idempotent** — safe to run daily; never duplicates (unique constraint).
- **Vacant positions:** if no holder at term end, create the obligation with `officer = NULL` so the Regent can close it as `na_vacant`. Note `UserRoleChange` has no direct "this position is vacant" row — vacancy is the ABSENCE of a current/future `UserRoleChange` for that position, the same detection `Chapter.get_about_expired_coucil()` already does (`current_and_future` empty → `officers_to_update.append(position)`).
- **Mid-term turnover — resolved (2026-09-04):** every `UserRoleChange` row generates its own obligation from its own `end`, not a single "chapter's nominal term end." If a position turns over mid-term, the outgoing officer's own (earlier) `end` already generates their obligation, and the incoming replacement's row independently generates its own obligation when THEIR term ends — no special-casing needed. Accepted reality: some obligations will go unanswered because the officer becomes unreachable (e.g. graduates/leaves school) — that's an acceptable `missed` outcome, not a blocker.
- Mark past-due unsubmitted obligations as `missed` (visibility only — no gating).
- Support `--dry-run` and `--lookahead-days`.
- **Scheduling constraint:** production (PythonAnywhere) only runs DAILY scheduled tasks (see `region_officer_reminder_digest.py`'s docstring) — this command is designed to run daily and be a no-op most days, not to be scheduled per-offset.

**Tests:** obligations generated for upcoming term ends; each `UserRoleChange` row (including a mid-term partial term) generates its own obligation; idempotent on re-run; vacant positions produce a closable obligation; optional position types excluded when config off; `missed` applied after due date; `--dry-run` writes nothing.

---

## TRWI-4 — Nudges & reminder emails

**Work item:** Surface obligations to the people who owe them and send reminders. Two mechanisms (decided 2026-09-04): **per-officer** (each officer's own term-end-derived due date) and **generic seasonal** (a calendar-driven broadcast near the end of each semester, since chapters' officer terms don't all end on the same day but the academic calendar is shared).

**Corrected from the original proposal:** `thetatauCMT.tasks` (`Task`/`TaskDate`/`TaskChapter`) is the ONLY "officer duties/tasks tracking system" in this codebase, and it does not fit here — a `TaskDate` is a single due date shared by every chapter of a `school_type` (e.g. "Audit due April 15" applies nationally), with completion tracked per chapter against that ONE date. There is no way to express "this specific chapter's treasurer, due on a date derived from THAT chapter's own officer term" without either polluting the shared calendar with one `TaskDate` per chapter/officer (defeating the model) or bypassing it entirely (defeating the reuse). Drop the Task/`task_ref` integration; there is no "surface it in the existing system" shortcut available.

**Reuse instead:** the officer-update-reminder system already solves the adjacent "detect an officer term ending/expired, remind the right people, don't spam daily, escalate to the RD" problem end to end:
- `Chapter.get_about_expired_coucil()` (`thetatauCMT/chapters/models.py`) — the detection query to imitate.
- `OfficerUpdateReminder` / `RegionalDirectorOfficerDigest` (`thetatauCMT/users/notifications.py`) — herald `EmailNotification` classes; daily chapter email + weekly RD digest, not a daily RD email.
- `officer_update_reminder_email.py` / `region_officer_reminder_digest.py` (`thetatauCMT/users/management/commands/`) — the two daily commands; `region_officer_reminder_digest.py` self-gates to one weekday for its "weekly" cadence.
- **Dedupe (decided 2026-09-04):** an explicit field, not herald's fragile `SentNotification.recipients__icontains` string-matching — mirrors `nominations`' `nomination_follow_up.py`, which tracks a plain `last_contacted` timestamp and re-fires only after an interval. Give `ReportObligation` its own tracking (e.g. `last_reminder_offset_sent`).

**Mechanism 1 — per-officer reminders** (unchanged from the original plan):
- Email/notification reminders at configured offsets (one daily command evaluates every open obligation's `due_date` against today); stop once submitted or closed as `na_vacant`.
- **Escalation = visibility, not enforcement.** Past due, include the Regent; a later offset includes the RD (via `chapter.region.directors`/`user.director_regions`).

**Mechanism 2 — generic seasonal reminder** (added 2026-09-04):
- Once per semester, near the end of the CURRENT semester (`core.models.semester_encompass_start_end_date()` gives the window; trigger the configured number of days before its end — TRWI-1), broadcast a reminder to everyone currently holding an in-scope position who still has an open obligation — a calendar-anchored nudge independent of any one chapter's specific due dates.
- Same daily command, same dedupe philosophy: track "generic reminder already sent for the semester ending `<date>`" (e.g. a small log row, or a `Config` value updated after sending) so it fires once per semester, not once per day within the window.

Both mechanisms:
- Reminders are **nudges only** — never block other functionality.
- Idempotent: no duplicate reminders if run multiple times per day.
- **Separately, for in-app visibility** (not the same thing as a Task): add a "My Transition Report Obligations" card to `core.views.HomeView` (`pages/home.html`), which already composes the incomplete-`TaskDate` table, What's New feed, and Role Guide card — same page, new card, no shared model.

**Tests:** per-officer reminders fire at configured offsets; generic seasonal reminder fires once near semester end and not again the same semester; reminders stop on submission/closure; past-due escalation includes Regent then RD; no duplicate sends; home dashboard card shows only the viewer's own open obligations.

---

## TRWI-5 — Compose & submit report

**Work item:** The authoring experience. See **TransitionReport**, **ReportAnswer**, **ReportAttachment** tables.

- **Entry point — Forms landing, not a nav item (decided 2026-09-04, supersedes the original "single nav entry" plan).** Add a "Transition Reports" row to `thetatauCMT/forms/views.py`'s `FORM_GROUPS` (the "administration" group is the natural fit — it already lists `chapter-officers`/`submit-chapter-officers`), backed by the required `thetatauCMT/guides/fixtures/feature_registry.json` entry (the SAME entry is what makes it appear on both `/features/` and the Forms landing page — registering it once covers both). The page itself is a filterable **"Transitions" list view**: filter by position/role, and by chapter vs. national scope. It shows the user's own obligations (derived from positions held), reports they're entitled to read, and their submission history — an officer holding two in-scope positions sees both obligations in the one list, no per-position rows in any menu.
- **No viewflow.** There is no approval step, so this is a plain `CreateView`/`UpdateView` + `services.py`, matching `notes`/`objectives` (`MultiFormsView` or a single `ModelForm`), not the viewflow `CreateProcessView` pattern used by `nominations`/`forms`.
- Compose form renders the resolved template's prompts with help text; supports **save as draft** and **submit**.
- **Optional attachments** for artifacts (budgets, contact sheets, calendars) with file-type and size validation — reuse `upload_validator.FileTypeValidator`.
- **`N/A — vacant` path** (Regent or RD only) closes an obligation without a report.
- On submit: write `ReportAnswer` rows including `prompt_key` and `prompt_label_snapshot`; set `submitted_at`; mark obligation `submitted`.
- Reports are **immediately visible** to entitled readers on submission — no approval step.
- **Author may edit at any time, indefinitely — no lock, no grace window (decided 2026-09-04).** An officer often thinks of something to add well after their term ends; don't cut that off. Editing after a successor has already acknowledged the report does NOT reset or flag that acknowledgment (decided 2026-09-04) — kept simple.
- Any date field (e.g. an admin-facing due date override) needs `core.forms.DatePicker` via `Meta.widgets` plus `{{ form.media }}` in the template — the repo's one date-picker convention.

Deliver migrations first (pause), then forms/views.

**Tests:** required prompts enforced; char bounds enforced; draft persists; submit closes obligation; answers store `prompt_key` + label snapshot; attachments validated; `na_vacant` restricted to Regent/RD; editable indefinitely (including well after term end, no lock); multi-position holder sees all obligations in one list; the Transitions row appears on Forms landing under "administration".

---

## TRWI-6 — Access control service

**Work item:** Centralized read-access rules — one service, called by every read surface.

Rules:
- **Successor access:** current holder of position P in chapter C may read ALL reports ever submitted for position P in chapter C — full history, since nothing is archived (see TRWI-10).
- **Regent:** all positions' reports for their own chapter.
- **RD:** all reports for chapters in their region, via the EXISTING `user.director_regions` property (`Region.directors` M2M reverse accessor) — same pattern as `awards/eligibility.py`'s regional scoping. Do not build a new region-scope lookup.
- **CCD:** **decided 2026-09-04 — treated as a plain national officer.** "Candidate chapter director" is just another `NATIONAL_OFFICER` role value with no chapter-scoping mechanism anywhere in the codebase; a CCD sees all reports nationally, same as any other national officer/council role. No new scoping built.
- **National Officer / Admin:** all reports (for trend analysis).
- **Author:** always their own reports.

Provide `can_read_report(user, report)` and `get_readable_reports(user, **filters)`. Reuse existing role/scope helpers (`user.is_officer_group`, `user.is_national_officer_group`, `user.director_regions`); do not create a second role lookup or a raw group-membership check (respect the `natoff_hidden`/`admin_hidden` impersonation toggles).

**Tests:** treasurer reads past treasurer reports for own chapter only, ALL of them not just recent ones; cannot read other positions or chapters; Regent reads all own-chapter positions; RD scoped to region; CCD (like any natoff) reads all; National reads all; author reads own.

---

## TRWI-7 — Successor handoff packet & acknowledgment

**Work item:** The payoff experience. **This is what drives compliance — do not treat it as optional.**

- When a member takes office in an in-scope position, generate a **handoff packet view**: ALL readable predecessor reports for that position/chapter (full history — nothing archived, see TRWI-10), reverse-chronological. No pinning (decision 2026-09-04) — every report sorts purely by recency.
- Notify the incoming officer that the packet is available (reuse existing notification patterns).
- **Acknowledgment:** "I've read this" per report, recorded in `ReportAcknowledgement`. Surface acknowledgment rate alongside submission rate on dashboards.
- Packet is permanently reachable from the Transitions list (Forms landing) — not a one-time notification.

**Tests:** packet contains only readable reports (full history); acknowledgment recorded once per user/report; notification fires on taking office; packet remains accessible later.

---

## TRWI-8 — Prior answers while composing

**Work item:** Show predecessors' answers inline while the current officer writes.

- In the compose view, each prompt optionally displays the previous holder's answer to the **same `prompt_key`** (collapsed by default).
- Purpose: officers build on and correct prior knowledge rather than restating it — and it visibly demonstrates the value of writing a good report.
- Respect TRWI-6 access rules; show nothing if the user isn't entitled.
- **Display only — never pre-fill.** Pre-filling produces copy-forward padding.
- Join on `prompt_key`; fall back to `prompt_label_snapshot` matching when a historical answer predates the key.

**Tests:** prior answers shown for matching `prompt_key`; hidden when not entitled; not pre-filled; label-snapshot fallback works across template version changes.

---

## TRWI-9 — Compliance dashboards

**Work item:** Visibility-driven accountability (no gating), building on top of the Transitions list from TRWI-5 (which already filters by role and chapter/national scope) with rate/trend analytics for roles that need the bigger picture.

- **Chapter view (Regent/officers):** current-cycle obligations with status (open / submitted / missed / n-a), due dates, acknowledgment status.
- **Regional view (RD/CCD):** submission + acknowledgment rates by chapter and position.
- **National view:** rates by region/chapter/position, plus trend across cycles.
- Highlight `missed` clearly — this is the primary accountability lever.
- Performance: `select_related`/`prefetch_related`; paginate; no N+1. Follow the repo's query-count regression-test convention (compare N=1 vs N=6+ rows with `CaptureQueriesContext`, per the `guides` app tests) rather than asserting an absolute count.
- Use `core.views.PagedFilteredTableView` + `django_tables2` + `django_filter` for the list-style views (the repo's one table/filter stack), with `{% collapsible_filter %}` for the filter accordion — matches every other list page in the app.

**Tests:** correct counts/rates per scope; role scoping enforced; missed items surfaced; query count bounded.

---

## TRWI-10 — Full history (no retention, archiving, or pinning)

**Work item:** Long-term institutional memory with NO expiry — decided 2026-09-04, supersedes the original retention/archive design.

- **No retention window, no archive job, no `retention_expires_on`/`archived_at` fields.** Every submitted report stays fully visible to every entitled reader (per TRWI-6) forever. Explicit reason: a new officer should be able to see everything a predecessor — and every predecessor before them — wrote, not just the last few years.
- **No pinning (confirmed 2026-09-04).** `is_pinned`/`pinned_by`/`pinned_reason` are dropped entirely — every report is equally visible, sorted purely by recency (TRWI-7).
- No management command needed for this item at all — there is no archive job and no pin state to maintain.

**Tests:** full history remains queryable/visible with no time-based cutoff; no pinning-related fields, filters, or behavior exist anywhere in the feature.

---

## TRWI-11 — Tags, search, trends

**Work item:** Mine inputs for best practices and blind spots.

- Derive `ReportTag` rows from `TemplatePrompt.tag` on submission; allow manual tags from the controlled vocabulary.
- **Search** across readable reports: full-text over answers; filters by position, chapter, region, tag, cycle — no `pinned`/`archived` filters needed, since neither exists (decisions 2026-09-04). `watson` (django-watson) is already a dependency, already registered for 2 models (`jobs.Job`, `users.User` — see their `apps.py` `ready()`), and is a better fit than a hand-rolled `icontains` chain across `ReportAnswer.value`. Registering a new model needs `manage.py buildwatson` after deploy — budget that into the rollout, not just the migration.
- **National trend view:** tag frequency by position/region/cycle; most common failure themes; chapters with no submissions.
- **CSV export** NO NEED FOR CSV EXPORT
- Every query must call the TRWI-6 access service — search and export are the easiest places to leak data.
- v1 is deterministic (tags + search). No LLM summarization.

**Tests:** tags derived on submission; search and export respect access rules; filters correct; trend counts accurate; no cross-chapter leakage for chapter-level roles.

---

## TRWI-12 — QA seed data

**Work item:** Seed realistic data so the feature can be QA'd end to end.

Management command `seed_transition_reports_demo` generating:
- Templates for several positions across all four in-scope position types (`ADVISOR_ROLES` excluded), including one position-specific override, using the real Default Prompt Set.
- Obligations across multiple chapters/regions in every status: `open`, `submitted`, `missed`, `na_vacant`.
- Reports including: a rich complete report, a minimal/low-quality one, one with attachments, and a **multi-generation chain** for one position (so the handoff packet and prior-answers view are meaningful — no "pinned" or "archived" example needed, since neither exists).
- Users in each role for access testing: successor officer, Regent, RD, CCD, National Officer, and an unrelated member (must see nothing).
- Acknowledgments on some reports, none on others.

Requirements: idempotent; `--seed` for reproducibility; `--flush` scoped to this domain only; prod-guarded (`DEBUG` check or `--force`); reuse existing members/chapters where present.

Deliver the command + `docs/specs/transition-reports-qa.md` listing expected visibility per role.

**Tests:** runs clean on empty and populated DBs; idempotent; reproducible with `--seed`; every status and access scenario represented; refuses to run in production without `--force`.

---

## Build Order & Dependencies

1. **TRWI-1 → TRWI-2** — Config + templates + prompt set (foundation).
2. **TRWI-3 → TRWI-4** — Obligation generation + reminder emails (dropped the task-system integration — see TRWI-4).
3. **TRWI-5 → TRWI-6** — Compose/submit + access control (the access service must exist before any read surface).
4. **TRWI-7 → TRWI-8** — Handoff packet + prior answers. **The compliance payoff — do not defer.**
5. **TRWI-9** — Compliance dashboards.
6. **TRWI-10** — Full history (no archiving, no pinning).
7. **TRWI-11** — Tags, search, trends. NO NEED FOR CSV EXPORT
8. **TRWI-12** — QA seed (buildable once TRWI-5/6 land; extend as later items ship).

**Minimum viable slice:** TRWI-1 → TRWI-8. That delivers capture + accountability + handoff, which is the core of the request.

**If scope must be cut:** cut TRWI-11 (trends/search) before TRWI-7/8. Reminders and dashboards create *obligation*; the handoff packet creates *motivation*.

---

## Design Rules & Gotchas

- **No dedicated nav item.** Lives on Forms landing instead (decided 2026-09-04) — never add per-position menu items regardless; obligations derive from positions held.
- **The successor experience drives compliance.** Officers write real reports when they personally benefited from a predecessor's. Prioritize TRWI-7/8 over dashboards.
- **Prompts are the intervention.** A blank text box produces nothing useful. Char bounds are a quality control, not a nicety.
- **No gating in v1.** Gating produces garbage submissions to clear the gate.
- **No approval bottleneck.** Visible on submission; Regent/RD review after the fact — explicitly requested to avoid the RD clearinghouse problem.
- **Never archive, never delete.** Full history is the point (decided 2026-09-04) — a new officer must see everything every predecessor wrote, not a windowed subset.
- **Term dates vary by campus — for the per-officer due date.** Derive that from each officer's recorded term end, never hard-code an academic calendar. The NEW generic seasonal reminder (TRWI-4) is deliberately the opposite: calendar-anchored on purpose, as an additional nudge, not a replacement.
- **`prompt_key` is a contract.** TRWI-8's prior-answers view depends on it. Never mutate shipped keys.
- **Access rules live in one service** (TRWI-6). Search, export, and trends are the easiest places to leak data.
- **Candor risk:** officers may write critically about named individuals. Help text sets a constructive tone. Revisit if it becomes a problem in practice — there is no retention window to bound exposure anymore (TRWI-10), so this risk is now open-ended; flag if it becomes a real issue.
- **No Task/TaskDate shortcut for per-officer obligations.** Confirmed by reading `tasks/models.py`: due dates there are national, not per-chapter-per-officer. The generic seasonal reminder (TRWI-4) legitimately IS calendar-based, but still isn't modeled as a `TaskDate` — it's a plain daily-command check against `semester_encompass_start_end_date()`.
- **Daily-only scheduling in production.** PythonAnywhere has no finer-grained cron than daily. Any command in this feature must be designed to run daily and be a safe no-op most days (see `region_officer_reminder_digest.py` for the self-gating pattern), never assumed to run at a specific hour/offset.
- **Feature registry entries are not optional polish.** `guides/tests/test_registry_loader.py::test_every_fixture_url_name_answers_get` and the catalog page both depend on it; budget it per work item. The same registry entry is also what makes the Transitions row appear on Forms landing.
- **Editable forever.** No grace window, no lock — authors can revise their report indefinitely, even long after their term ends (decided 2026-09-04).

---

## Decisions Log (2026-09-04)

Every question from the codebase review has been answered. Recorded here for traceability — don't reopen without a new reason.

### A. Architecture
- **A1 — Purpose-built app confirmed**, not `django-survey-and-report`. File-upload prompts were the deciding factor on top of the earlier reasons (no stable prompt identity, no label snapshotting).
- **A2 — App name:** `thetatauCMT.transitions`.

### B. Position scope
- **B3 — `ADVISOR_ROLES`:** excluded from v1 entirely, not even as an optional type.
- **B4 — Required-by-default set:** `CHAPTER_OFFICER_REQUIRED` (7 roles), not the bare 5.
- **B5 — Pledge educator / risk management chair prompt set:** use the `CHAPTER_OFFICER` core prompt set, not the `COMMITTEE_CHAIR` variation.
- **B6 — Position scope confirmed:** `CHAPTER_OFFICER_REQUIRED` required; `COUNCIL`/`NATIONAL_OFFICER`/remaining `COMMITTEE_CHAIR` optional; no `ADVISOR_ROLES`.

### C. Obligations & reminders
- **C7 — Mid-term turnover:** every `UserRoleChange` row generates its own obligation from its own `end` date — no special-casing for outgoing mid-term holders. An officer becoming unreachable (e.g. graduating) is an accepted `missed` outcome, not a blocker.
- **C8 — Task/TaskDate integration dropped, replaced by TWO reminder mechanisms:** (1) per-officer, from each `ReportObligation.due_date`; (2) a NEW generic seasonal broadcast near the end of each semester (via `core.models.semester_encompass_start_end_date()`), to everyone with an open obligation. See TRWI-4.
- **C9 — Reminder dedupe:** an explicit field/log on `ReportObligation` (matches `nominations`' `last_contacted` pattern), not herald `SentNotification` string-matching.

### D. Access control
- **D10 — CCD scoping:** treated as a plain national officer — sees all reports, same as any `NATIONAL_OFFICER`/`COUNCIL` role. No new chapter-to-CCD scoping built.

### E. Data model
- **E11 — `ReportAcknowledgement`:** dedicated model, NOT reusing `guides.UserAcknowledgement`. Spelling corrected to match the codebase's `UserAcknowledgement` convention.
- **E12 — `ReportObligation.role_change`:** a loose, nullable FK (`on_delete=models.SET_NULL`) to `users.UserRoleChange` — traceability only, not a hard dependency. The obligation's own denormalized fields are authoritative once generated.

### F. Retention & editing
- **F13 — Retention window: dropped entirely.** No archiving, no deletion — full history stays visible to every entitled reader forever. See TRWI-10.
- **F14 — Confidential/private section:** confirmed omitted from v1.
- **F15 — Edit grace window: dropped entirely.** Authors may edit their own report at any time, indefinitely, even long after their term ends.
- **F16 — Prompt set review:** confirmed needed — added to the Pre-Launch Checklist below.

### G. Navigation
- **G17 — Nav entry: dropped entirely.** Lives on the Forms landing page (`forms:landing`) as another form, via a filterable "Transitions" list (filters: position/role, chapter vs. national scope). See TRWI-5.

### H. Handoff packet (resolved 2026-09-04)
- **H18 — Pinning:** dropped entirely. No `is_pinned`/`pinned_by`/`pinned_reason` fields anywhere in the data model; every report sorts purely by recency in the handoff packet, search, and QA seed data.
- **H19 — Edit-after-acknowledgment:** acknowledgments persist unchanged. Editing a report after a successor has acknowledged it does NOT reset or flag the acknowledgment — kept simple, per your answer.

### I. TRWI-3 — Obligation generation (resolved 2026-09-05)
- **I20 — Vacancy-detection algorithm:** confirmed the two-trigger design (term-ending-soon attaches `officer=role_change.user`; the `CHAPTER_OFFICER_REQUIRED`-only safety net attaches `officer=None` from a stale role change), **with one correction: the safety net's stale role change must be no more than 1 year old.** Implemented as `VACANCY_MAX_STALENESS_DAYS = 365` in `services.py`.
- **I21 — `--lookahead-days` default:** confirmed 45 days is fine, but tied it explicitly to the configured reminder offsets rather than a bare constant, per your note that the offsets (14/7/1/-1/-7/etc.) are "what this was for." Implemented `get_default_lookahead_days()` = `due_date_offset + max(configured reminder offsets) + a 10-day buffer` — 14+21+10=45 under default config, but now widens automatically if the reminder offsets are ever configured larger.
- **I22 — Backward grace window:** widened from 7 days to **365 days** ("look back up to a year") — `LOOKBACK_GRACE_DAYS = 365` in `services.py`. Catches up to a year of missed/late daily command runs.
- **I23 — Missed-marking timing:** confirmed — same `generate_transition_obligations` run, immediately after both generation triggers.

**Consequence discovered while implementing I20+I22 together (see J24 below):** since both windows are now 365 days, trigger 1 (term-ending-soon) ends up covering every role change within the last year anyway, so it always claims the natural key first with `officer=role_change.user` — the vacancy safety net's `officer=None` path is now only reachable for a required position that's been vacant for **more than** a year, which I20 says NOT to use. In practice: a required position vacant for up to a year still gets an obligation, just with the last known holder as `officer`, not `None`. Flagged as J24 for your review rather than silently deciding.

### J. TRWI-3 — Vacancy-safety-net reachability (resolved 2026-09-05)
- **J24 — Confirmed acceptable.** A required position vacant for up to a year still gets an obligation via trigger 1 (`officer=<last known holder>`, not `None`); only a position vacant for MORE than a year, or never held at all, produces nothing. No code change needed — this is already the implemented, tested behavior.

### K. TRWI-4 — Nudges & reminder emails (resolved 2026-09-05)

TRWI-4 is implemented, migrated, and tested (112 tests passing in the transitions app; 480 across the full regression sweep including configs/core/users). **Confirmed by you 2026-09-05: "Design decisions reviewed and are good."**

- **K25 — New field:** `ReportObligation.last_reminder_offset_sent` (nullable `IntegerField`), exactly as the work item itself suggested, tracking the most recent (most urgent) configured offset already acted on so the daily command never double-sends a threshold.
- **K26 — New Config key `TRANSITIONS_RD_ESCALATION_OFFSET_DAYS`** (default **-7**, seeded in `default_configs.json`): once a reminder offset at/below this is reached, the Regional Director is escalated in addition to the Regent. Not called for explicitly in TRWI-1's original config list — added because "a later offset includes the RD" needed a concrete threshold. -7 was chosen as the middle of the three default past-due offsets (-1/-7/-14): Regent alone at -1, Regent+RD from -7 onward.
- **K27 — Reminder-eligible statuses are `open` AND `missed`, not just `open`.** TRWI-3 flips `open` -> `missed` the very first day something is past due, which would otherwise silence every negative-offset reminder (-1/-7/-14) immediately once due_date passes. Resolved via the acceptance criterion's own wording — "reminders stop on submission/closure" — closure means `submitted`/`na_vacant` only; `missed` is a visibility flag (decision C7), not a stopping condition.
- **K28 — Threshold-detection algorithm:** for each obligation, `days_until_due = due_date - today`; the applicable threshold is the SMALLEST (most urgent) configured offset with `days_until_due <= offset`. A daily command that missed several days jumps straight to the correct current threshold rather than replaying every skipped one.
- **K29 — Recipient tiers:** officer's own email(s) always (if an officer is set); + the chapter's generic Regent email (`chapter.generic_email_for_role("regent")`) once the threshold is past due (< 0); + the region's RD email(s)/region mailbox (mirrors `RegionalDirectorOfficerDigest`'s own recipient gathering) once the threshold is at/below the K26 RD-escalation offset. A vacant obligation (`officer=None`) not yet past due resolves NO recipients and sends nothing, but still records the threshold so it's never re-evaluated; once past due it still escalates to the Regent (there's no officer to email, but the Regent needs to know to close it `na_vacant`).
- **K30 — One daily management command** `send_transition_report_reminders`, running both mechanisms in sequence, matching the work item's own "Same daily command" instruction for mechanism 2 and the repo's daily-only-scheduling constraint.
- **K31 — Mechanism 2 dedupe:** a NEW Config key `TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR` (system-managed bookkeeping, not an admin-tunable despite living in the `Config` table) storing the ISO date of the semester-end last sent for. A NEW row is created to record it (never an update) since `Config.get_value` already reads the latest row by `created` — matches how every other Config value in this codebase is written, not a special case.
- **K32 — `dry_run` is an explicit skip, NOT a rolled-back transaction**, unlike `generate_obligations`'s TRWI-3 sibling. An actual email send is a real external side effect a DB transaction rollback cannot undo, so both reminder functions explicitly skip every `.send()` and every write when `dry_run=True`, computing and returning the same counts either way.
- **K33 — Home dashboard card** "My Transition Report Obligations" added to `pages/home.html` (via `guides/_role_guide_card.html`'s exact pattern) showing the viewer's own `open`/`missed` obligations (positions THEY hold, not chapter-wide) — no new page, so no feature-registry entry needed (TRWI-5's page will need one).
- **K34 — Fixed a pre-existing gap found while regression-testing:** `PositionOverride`/`ReportTemplate`/`TemplatePrompt`/`ReportObligation` (TRWI-1/2/3) had never been registered with `dj_anonymizer`, failing `core/tests/test_anonymizer.py::test_every_model_is_registered_with_the_anonymizer`. This wasn't caught earlier because only `thetatauCMT/transitions` tests had been run, not the full suite. Added `anonymizer/transitions.py` (`register_skip` for all four — admin-managed config/prompt content, plus `ReportObligation` which only references a person through FKs, matching `guides/_role_guide_card.html`'s `UserAcknowledgement` precedent).

### L. TRWI-5 — Compose & submit report (implemented autonomously 2026-09-05 — please review)

TRWI-5 is implemented, migrated, and tested (159 tests passing in the transitions app; 1867 passed / 15 skipped across a full regression sweep of configs/core/users/guides/forms/chapters/regions/transitions). This work item had the most genuinely underspecified design surface so far — flagging every material choice below.

- **L35 — `na_vacant` creates NO `TransitionReport` row at all**, taken literally from the spec's own wording ("closes an obligation WITHOUT a report"). It is purely a `ReportObligation.status` transition. `TransitionReport.Status` still includes `na_vacant` for schema completeness (matches the spec's field table exactly), but no code path ever actually sets it — every real row is `draft` or `submitted`.
- **L36 — Fixed invariant: `report.author == obligation.officer`, always.** Only the position's assigned officer may compose their own obligation (`ComposeReportView` redirects anyone else with an error). There is no "someone else fills it in for you" path — simpler than solving "who else may author" with no spec guidance either way.
- **L37 — `TransitionReport.template` uses `on_delete=PROTECT`** (spec didn't say). `ReportAnswer.prompt` is `SET_NULL` by the spec's own explicit "nullable so prompt deletion never orphans history" language, but `template` isn't marked nullable, so PROTECT (block deletion rather than orphan/null it) was the more conservative, data-integrity-preserving reading. `author`/`uploaded_by` use plain `on_delete=CASCADE`, matching `notes.ChapterNote.created_by`'s exact precedent (non-nullable "who did this" FKs elsewhere in the repo).
- **L38 — `ReportAnswer` has an added `unique_together = (report, prompt_key)`** not explicit in the spec table, but a natural integrity constraint (one answer per prompt per report) matching the app's established unique-constraint conventions elsewhere.
- **L39 — `ReportAttachment.ALLOWED_FILE_TYPES` invented**: PDF, JPEG, PNG, CSV, DOCX, XLSX. No file-size validator exists anywhere in this codebase to pair with `FileTypeValidator`, so none was added here either (would be a new precedent, not a reused one).
- **L40 — The Transitions list view is scoped to "my own" only for now** (my own obligations, any status, doubling as submission history) — deliberately NOT the full "reports I'm entitled to read" breadth (successor/Regent/RD/national visibility), since that needs TRWI-6's access service, which doesn't exist yet (Build Order: "the access service must exist before any read surface"). The "chapter vs. national scope" filter from the spec is deferred to TRWI-6 for the same reason; only a simple position/role filter exists today.
- **L41 — Built a narrow, self-contained "vacant obligations for closer" query now**, rather than waiting for TRWI-6: a Regent sees their own chapter's officer-less open obligations, an RD sees their own region's, via `services.get_vacant_obligations_for_closer()`. This was necessary because a vacant obligation (`officer=None`) can never appear in "my own obligations" (filtered by `officer=user`), yet the na_vacant path is explicitly part of TRWI-5's own acceptance criteria ("na_vacant restricted to Regent/RD") — so it needed *some* visibility surface now, just not the full TRWI-6 one.
- **L42 — No `django_tables2`/`django_filter`/`PagedFilteredTableView` stack yet** — a plain `TemplateView` with a manual GET-param position filter, since "my own obligations" is typically 1-3 rows per user right now. Deferred the heavier list/filter stack (the repo's established convention for larger datasets) to TRWI-6/9 once the dataset actually grows to "all chapter/region reports."
- **L43 — `template_version` is re-resolved and re-stamped at SUBMIT time**, not fixed at draft creation, so it reflects what was actually current "at submission" per the spec's own field description, even if an admin changed the template while a draft sat unfinished.
- **L44 — Anonymizer split by content risk, not by TRWI grouping:** `TransitionReport` is `register_skip` (pure metadata), but `ReportAnswer`/`ReportAttachment` are `register_clean` (delete all rows) — the plan's own "candor risk" note (officers may write critically about NAMED INDIVIDUALS) means the actual authored content is raw as-uploaded identity data, the same category as `attendance.MatchQueueItem`, not a simple FK reference.
- **L45 — Feature registry:** one new entry `transition-reports` (audience `officer`, no `roles` — every in-scope position owes one, not just Regents), added to `FORM_GROUPS`'s "administration" group and to `docs/specs`'s forms-workflows area. Verified with `load_feature_registry --dry-run` (clean, `1 added` then `0 added/0 updated` on the second dry-run) and the full `guides` test suite (216 passed).

### M. TRWI-6 — Access control service (implemented autonomously 2026-09-05 — please review)

TRWI-6 is implemented and tested (179 tests passing in the transitions app, up from 159; 1887 passed / 15 skipped across the full regression sweep of configs/core/users/guides/forms/chapters/regions/transitions). This is the smallest work item so far in terms of new surface area (two functions), but it carries the most consequential correctness responsibility in the whole feature, since every future read surface depends on it.

- **M46 — Drafts are never visible to anyone but their author, even to someone who otherwise has full read access to the position/chapter.** The spec doesn't say this in TRWI-6's own section, but it follows directly from the Design decisions section's "reports are submitted and immediately visible to entitled readers" (no approval step, but visibility is gated on submission, not authorship) — a report is not yet "submitted and immediately visible" while still a draft. Every rule EXCEPT "author reads their own" is therefore restricted to `status=submitted`; only the author sees their own in-progress draft. This is a meaningful interpretive choice, not just an implementation detail, so it's called out explicitly rather than buried in a docstring.
- **M47 — `can_read_report(user, report)` is implemented as `get_readable_reports(user, pk=report.pk).exists()`**, not as a separate, independently-written rule set. "Can I read this one" is just "is it in my readable queryset" — this guarantees the single-object check and the bulk query can never drift apart as the rules evolve (the spec's own instruction: "Access rules live in one service").
- **M48 — CCD and Council need no special-casing.** `core.models.NAT_OFFICERS = COUNCIL | NATIONAL_OFFICER`, and `UserRoleChange.save()` already adds anyone holding an ``is_national_officer()`` role (which checks against `NAT_OFFICERS`) to the `natoff` Django group. So `user.is_national_officer_group` alone already covers Council positions (e.g. "grand regent") and CCD ("candidate chapter director") identically to any other National Officer — confirmed with a dedicated test for each, per the spec's explicit CCD callout.
- **M49 — Successor/Regent access uses direct `current_roles`/`current_chapter` checks, not `user.is_officer_group`.** `is_officer_group` (`is_national_officer_group or is_chapter_officer_group`) is a coarse "officer of SOME kind" flag backed by Django group membership; it can't answer "holds THIS SPECIFIC position in THIS SPECIFIC chapter", which is what successor access actually requires. Per the spec's own instruction ("do not create a second role lookup or a raw group-membership check"), this reuses the exact `user.current_chapter.pk == report.chapter_id` / `REGENT_ROLE_KEY in user.current_roles` pattern already established by TRWI-5's `can_close_na_vacant` — not a new lookup, the same one extended to a new table.
- **M50 — RD scoping matches `get_vacant_obligations_for_closer`'s exact style**: `chapter__region__in=user.director_regions.all()`, not `awards/eligibility.py`'s `chapter__region_id__in=[...]` (materialized pk list) style. Both are correct; this file's own established TRWI-5 precedent won out over the other app's for internal consistency.
- **M51 — `TransitionsListView` was extended, not left as a bare service with zero callers.** The spec's own "chapter vs. national scope" filter (Design decisions section) was explicitly deferred to TRWI-6 by decision L40, and TRWI-9's own text assumes the Transitions list "already filters by role and chapter/national scope" by the time dashboards start — so closing that gap now, rather than leaving it for TRWI-7/9, keeps the spec's own forward references true. Added a **"Reports you can read"** section (`services.get_readable_reports`) plus a `scope=chapter` GET param that narrows to the viewer's own current chapter. The toggle itself is only rendered when it would narrow anything (admin, national officer, or RD) — a Regent's or successor's readable set is already chapter-scoped, so the toggle would be a no-op for them. This is intentionally a binary toggle ("my chapter" vs. "everything I can read"), not a per-chapter picker dropdown — the fuller rate/trend breakdown by chapter belongs to TRWI-9's dashboards, not this list view.
- **M52 — No query-count regression test added for `get_readable_reports` in TRWI-6 itself** — the spec assigns that performance discipline (`select_related`/`prefetch_related`, `CaptureQueriesContext` N=1 vs N=6+ comparison) explicitly to TRWI-9. `select_related("chapter", "chapter__region", "obligation")` is already applied here so TRWI-9 inherits a reasonably query-light base rather than starting from zero.

### N. TRWI-7 — Successor handoff packet & acknowledgment (implemented autonomously 2026-09-05 — please review)

TRWI-7 is implemented, migrated, and tested (207 tests passing in the transitions app, up from 179; 1915 passed / 15 skipped across the full regression sweep). This work item's spec left the "notify on taking office" trigger mechanism unspecified beyond "reuse existing notification patterns," which drove most of the judgment calls below.

- **N53 — A SEPARATE new daily command, `send_transition_handoff_notices`, not folded into TRWI-4's existing `send_transition_report_reminders`.** The Design Rules say scheduled commands must be daily-only, but not that every daily concern must share ONE command/function. Reminders (nudging the outgoing officer) and handoff notices (informing the incoming officer) are different audiences and different triggers; more importantly, `send_transition_report_reminders` is already a live, presumably-scheduled production command — changing its behavior or name to absorb a second concern risked disrupting an existing PythonAnywhere scheduled task for no real benefit. Cost: one more daily task to schedule, called out in the Pre-Launch Checklist below.
- **N54 — Handoff notices cover the FULL in-scope position set** (`POSITION_KEY_TO_TYPE`, filtered through `resolve_position_status` for required/optional, excluding "excluded"), not the narrower 5-role `CHAPTER_OFFICER` set the existing `users.notifications.NewOfficers` "welcome new officer" email happens to use. TRWI-7's own wording ("a member takes office in an in-scope position") means council/national_officer/committee_chair positions too, matching `generate_obligations`' own trigger-1 scope exactly — not a new, narrower rule invented for notifications specifically.
- **N55 — The notice EMAIL is skipped when there are zero predecessor reports to read, but `HandoffNotice` is still recorded either way.** An empty "here's your packet!" email the moment someone takes a brand-new-to-the-feature position (which will be EVERY position for a long while after rollout) is noise, not a nudge, and risks training recipients to ignore the notification entirely. Mirrors K29's exact reasoning (TRWI-4: "resolves no recipients... but still records the threshold so it's never re-evaluated").
- **N56 — New `HandoffNotice` model (OneToOne to `UserRoleChange`) is pure dedupe bookkeeping**, tracking only that the one-time notice already fired for a specific role change — it is NOT registered in Django admin, matching `ReportObligation`'s own precedent (also bookkeeping-heavy, also has no dedicated admin page; officers/committee use the front-end views, not raw table browsing, for this kind of row).
- **N57 — `get_handoff_packet` excludes the viewer's OWN report from the results**, layered on top of `get_readable_reports` (TRWI-6). The spec says "ALL readable PREDECESSOR reports" — a successor who has already drafted or submitted their own report for the same slot should see it via the Compose flow (TRWI-5) and the Transitions list (TRWI-5/6), not mixed into what's supposed to be their predecessors' history.
- **N58 — Packet view access is exactly `get_readable_reports`, scoped down — no separate 403 for an unentitled visitor.** An unentitled viewer of `/transitions/packet/<chapter>/<position>/` simply sees an empty packet ("No Transition Reports are available to read for this position yet"), the same "the queryset IS the security boundary" approach `TransitionsListView` already uses — no report CONTENT is ever at risk since the queryset itself is the enforcement point, and chapter/position names aren't confidential.
- **N59 — `AcknowledgeReportView` re-checks `can_read_report` independently**, even though its only real entry point (the packet view) already only ever shows readable reports — defense in depth for a POST endpoint that takes a bare report pk, consistent with how `CloseNAVacantView`/`AttachmentDeleteView` (TRWI-5) also each re-check their own authorization rather than trusting the referring page.
- **N60 — `send_handoff_notices` uses `role_change.user.chapter`, not `user.current_chapter`,** for the same reason `generate_obligations` does (TRWI-3): the report/obligation history this notice is about is keyed to the chapter the role was actually held in, which for a National Officer previewing via an active `UserAlter` override can differ from `current_chapter`.
- **N61 — No new feature registry entry for the packet page.** It is a sub-page reached only via a link from the already-registered `transition-reports` list page (Forms landing), never a directly-navigable top-level destination — matches TRWI-5's own precedent (`ComposeReportView`/`AttachmentDeleteView`/`CloseNAVacantView` also got no separate entries, only the list view did).

### O. TRWI-8 — Prior answers while composing (implemented autonomously 2026-09-05 — please review)

TRWI-8 is implemented and tested (220 tests passing in the transitions app, up from 207; 1928 passed / 15 skipped across the full regression sweep). No migration — this work item is pure services/forms/views/template, reusing TRWI-6/TRWI-7's existing data model and access rules.

- **O62 — "The previous holder's answer" (spec's own singular wording) means the SINGLE most recent predecessor report**, not a merge scanning further back through full history. `get_prior_answers` takes `get_handoff_packet(...).first()` (already most-recent-first) rather than searching older reports for a prompt the latest predecessor left blank. Simpler, and matches the literal wording; a prompt the most recent predecessor didn't answer just shows nothing, even if an earlier predecessor answered it.
- **O63 — Access is TRWI-6/7's existing rules, reused outright — no new derivation.** `get_prior_answers` calls `get_handoff_packet` (TRWI-7), which already excludes the composer's own report and already respects `get_readable_reports` (TRWI-6). One real consequence worth flagging: an officer editing their OWN report long after their term ends (decision F15, indefinitely editable) may no longer satisfy the TRWI-6 "successor" rule once `current_roles` no longer lists that position — at that point prior answers correctly show NOTHING, even though they can still edit their own report. Composing ability and "see prior answers" are two separate checks that can diverge; this is intentional, not a bug.
- **O64 — Compose form rendering changed from one `{{ form|crispy }}` call to a per-field loop** (`{% for field, prior in fields_with_prior_answers %}`, using crispy's `as_crispy_field` filter) so each prompt's prior answer can be interleaved directly beneath its own field. Uses a native `<details>`/`<summary>` element for "collapsed by default" — no JS, CSP-safe by construction (the Shared Preamble's own "no inline `<script>`" rule).
- **O65 — `services.py` stays Django-form-agnostic**: `get_prior_answers(user, report)` returns a plain `{prompt_key: ReportAnswer}` dict. Pairing each answer with its actual form field lives on `ComposeReportForm.fields_with_prior_answers()` instead (the form already owns the prompt-key <-> field-name mapping via `_field_name()`), not in services.py — matches TRWI-5's own established layering (`answers_data()`/`save_draft`/`submit_report` already take/return plain prompt-keyed structures, never Django form objects).
- **O66 — Never pre-filled, by construction, not by a special-case check.** `initial_from_report()` (the only thing that ever seeds a field's actual value) reads exclusively from `report.answers` — the CURRENT report's own answers. `prior_answers` is a completely separate context variable rendered as read-only display text alongside the field, never passed anywhere near `initial=`. There is no code path where a prior answer's value could leak into `cleaned_data`.
- **O67 — Label-snapshot fallback matches by exact string equality** (`prompt_label_snapshot == prompt.label`), not a fuzzy/normalized comparison. Given `prompt_key` is meant to be immutable once shipped (F16), this fallback is deliberately a defensive safety net for a scenario that should never actually happen in practice, so exact matching (simplest, least surprising) was preferred over building normalization logic for a case with no real precedent yet.

### P. TRWI-9 — Compliance dashboards (implemented autonomously 2026-09-05 — please review)

TRWI-9 is implemented and tested (255 tests passing in the transitions app, up from 220; 1963 passed / 15 skipped across the full regression sweep). This is the largest single work item so far, so the judgment calls below are more numerous than usual — please read through all of them.

- **P68 — "Cycle" is 3 fixed choices (current / previous / all time), not a dynamically-enumerated list of every historical cycle.** A cycle is one academic year (July-to-July, reusing `core.models.academic_encompass_start_end_date` — the same calendar TRWI-4's seasonal reminder already anchors to). "Current" satisfies the chapter view's own "current-cycle obligations" wording; switching to "previous" is how "trend across cycles" is surfaced for the rates view (compare the same table's numbers cycle-over-cycle) — there is no chart/graph. This avoids an extra distinct-values query per request and keeps the filter UI simple.
- **P69 — Regional view and National view are ONE view (`ComplianceRatesView`), not two**, mirroring decision M51's exact precedent (TRWI-6's `scope=chapter` toggle): the SAME "rates by chapter" table serves both audiences, scoped by role (`services.get_compliance_rate_chapters`) — an RD sees only their own `director_regions`' chapters with no region filter shown at all (their scope is already narrower than any region they'd pick); a National Officer/Admin sees every active chapter with an optional region filter to narrow down. This satisfies both TRWI-9 bullets ("Regional view: ... by chapter and position" / "National view: rates by region/chapter/position") without duplicating the view, table, template, and access logic twice.
- **P70 — Submission rate and acknowledgment rate share the SAME denominator** (`total` obligations in the cycle/position/chapter scope), making the two percentages directly comparable side by side in one row — not, say, acknowledgment rate computed only out of submitted reports. A chapter with 10 obligations and 3 submitted+acknowledged shows 30%/30%, not 30%/100%.
- **P71 — Status counts (`total`/`submitted`/`missed`) and the acknowledgment count are TWO SEPARATE aggregate queries, not one.** The acknowledgment count joins through `report__acknowledgements`, a fan-out-prone reverse relation (one report can have multiple acknowledgments); Django's own docs warn that combining a fan-out aggregate with other aggregates in the same query silently inflates all of them unless every one is *also* `distinct=True`. Splitting into two single-purpose queries sidesteps that correctness trap entirely — still exactly 2 queries total regardless of how many chapters are being scored (verified by a `CaptureQueriesContext` N=2-chapters vs. N=6-chapters regression test, per the spec's own convention).
- **P72 — The chapter dashboard takes an explicit `chapter_pk` URL param, not an implicit "current chapter."** `services.can_view_chapter_dashboard` gates it: the chapter's own officers (`is_officer_group`, matching "Chapter view (Regent/officers)" literally — a plain committee chair or member does not qualify), the chapter's RD, or any National Officer/Admin. This lets an RD or National Officer drill into any SPECIFIC chapter's obligation detail after spotting a low rate in the aggregate rates view, rather than only ever seeing their own chapter.
- **P73 — The rates view is NOT a `PagedFilteredTableView`.** Its rows are post-aggregation `services.ChapterComplianceStats` dataclasses, not a plain queryset, so `PagedFilteredTableView`'s "filter a queryset, hand `.qs` to a `SingleTableView`" flow doesn't fit — the filter is applied to the *underlying obligations* queryset manually (for validation/cleaned-data only, never evaluated as a queryset) before `get_chapter_compliance_stats` aggregates it, then a plain `django_tables2.Table(data=stats)` + `RequestConfig` wraps the resulting list directly. The chapter dashboard (`ChapterComplianceView`), whose rows genuinely are one-row-per-`ReportObligation`, DOES use the full `PagedFilteredTableView` stack as specified.
- **P74 — "Missed" highlighting is a `row_attrs` red highlight** (`table-danger`) on the chapter dashboard (obligation-level: that ONE obligation is missed) and on the rates view (chapter-level: this chapter has 1+ missed obligations this cycle) — django_tables2's standard mechanism for this, with no prior in-repo precedent to match, since no other table in this codebase highlights rows conditionally yet.
- **P75 — No new feature registry entries for either dashboard.** Both are reached only via links from the already-registered `transition-reports` list page (a "My chapter dashboard" button for officers, a "Compliance rates" button for RD/National/Admin) — matches TRWI-5/TRWI-7's own precedent (sub-pages reached by a link don't need their own entry, only the primary navigable list page does).

---

## Pre-Launch Checklist

- [ ] **Default Prompt Set review** — get a pass from someone who has actually held a chapter office before the prompt set is seeded to production; `prompt_key` values become immutable once shipped (F16).
- [x] Feature registry entry added for the Transitions page(s) and verified with `load_feature_registry --dry-run` (this is also what makes the row appear on Forms landing). Done 2026-09-05 (TRWI-5, key `transition-reports`).
- [ ] `manage.py buildwatson` run after deploy if TRWI-11's search is implemented via `watson`.
- [ ] Schedule the new `send_transition_handoff_notices` daily command on PythonAnywhere (TRWI-7) — separate from the existing `send_transition_report_reminders` task (decision N53); both must run daily.

---

## Remaining Open Questions

None from the original codebase review round, TRWI-3 (I20-I23, J24), or TRWI-4 (K25-K34, confirmed) — see Decisions Log A-K. TRWI-5's design choices (L35-L45), TRWI-6's (M46-M52), TRWI-7's (N53-N61), TRWI-8's (O62-O67), and TRWI-9's (P68-P75) are implemented and tested but not yet reviewed by you; see the Decisions Log entries above.
