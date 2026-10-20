# Transition Reports & Lessons Learned — Feature Spec & Work Breakdown

> **Status:** Feature complete (2026-09-06) — TRWI-1 through TRWI-12 are all implemented and tested. A 5-part UI/UX polish pass followed on 2026-09-06 (T97-T101, below). **TRWI-13 (structured contacts/dates from real transition documents): Phase 1 implemented autonomously 2026-09-06** — see that section for what was built vs. deferred (Phase 2) vs. confirmed out of scope. See "Decisions Log" at the end for the full record of resolved decisions (A-K, Q) plus TRWI-5's (L35-L45), TRWI-6's (M46-M52), TRWI-7's (N53-N61), TRWI-8's (O62-O67), TRWI-9's (P68-P75), TRWI-11's (R80-R89), TRWI-12's (S90-S96), and the polish pass's (T97-T101) choices awaiting review. Note: CSV export requirement dropped (TRWI-11 only).
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

## TRWI-13 (Phase 1 implemented autonomously 2026-09-06, please review) — Structured content from real transition documents

**Status: Phase 1 built and tested.** Triggered by 3 real past transition write-ups you shared (Regent, Treasurer, Vice Regent) plus a formal "Executive Board Officer Transition Worksheet" template used elsewhere. You were asked 4 clarifying questions (Phase 1 scope, Phase 2 Successor Action Plan, credential warning, chapter-playbook scope) but were unavailable to answer them live; you asked me to work autonomously and make good decisions, so I proceeded with the recommended option on each (see "Decisions actually made" below) rather than waiting. 339 tests passing in the transitions app (up from 327), 3244 passed / 16 skipped across the full regression sweep (up from 3232).

### What the real documents confirm we already got right

The core prompt set's ordering and themes (successes, then failures, then reference material, then forward-looking) match what these documents actually do. Concretely: the Treasurer doc's "Things that worked well / Things that did not work well / Things that should change" is exactly `successes`/`failures`/`anything_else`. The Regent and Vice Regent docs both end with "call me if you have trouble" and named contacts, matching `campus_contacts`/`experts`. T98's move to free-form tags (any signed-in officer can now type a new tag like "budget" or "ritual" instead of picking from the fixed 9) already covers most of the ad hoc categorization these documents would want.

### The actual gap: `contact`, `list`, and (implicitly) "who to meet"/"what to attach" are cosmetic today, not structured

Confirmed by reading the code, not just inferring: `ComposeReportForm._build_field` only special-cases `field_type="date"`. Every other field type, including `contact` and `list`, renders as a plain `CharField` + `Textarea` — same widget, same storage (one big string in `ReportAnswer.value`), just a different *label* hinting at the expected format. There is no structured "one row per contact" or "one row per date" data anywhere. This is precisely your "not just attach this document, but a way to collect this information that is searchable" concern: today, a future Treasurer trying to find "who do I call about the EMS room-booking issue" has to hope the phrase appears verbatim in a wall of text that `watson` full-text-matches, not query a contacts list.

### Proposed structured additions (Phase 1, smaller/higher-value)

| Gap (with document evidence) | Proposed model | What it buys |
|---|---|---|
| Contacts buried in prose. E.g. "Joe Krauskopf: (650)575-4242" currently holds the tabling stuff"; "cuengineering@colorado.edu... you will need the dates, last 7 digits of your Buff One, phone number." Formal template's whole "Who" section. | New child model `ReportContact` (report FK, `name`, `role_or_context`, `phone`, `email`, `notes` = what they help with). Repeatable inline on the compose form (add/remove rows), replacing the `campus_contacts`/`experts` prompts' free-text box. | Contacts become individually browsable/searchable, not just full-text-matchable. A later "chapter contacts directory" view (aggregating across every report for a chapter) becomes possible without more model work. |
| Dates buried in prose, often with the MOST useful part (lead time) least likely to survive a paraphrase. E.g. "IFC dues due Oct 1, start collecting Sept 1"; "pay for the domain name... try to do it before january"; pin orders, room reservations. | New child model `ReportKeyDate` (report FK, `label`, `timing` free text or a real `Date`, `lead_time_note`). Repeatable inline, replacing the `key_dates` prompt's one-per-line textarea. | Sortable/filterable by date instead of buried in a paragraph; opens the door to a future "upcoming deadlines across my chapter's reports" feed (not proposing that view yet, just noting the model supports it). |
| Attachments are freeform (file + description) with no guidance on what's commonly useful. Formal template's "Additional Information to Share" is a checklist of ~15 document categories (budgets, meeting minutes, vendor info, asset list, calendars, policy docs, etc.). | Add `ReportAttachment.category` (a small `choices` field: budget, minutes, vendor_info, policy, event_plan, asset_list, other) and show the template's own category list as an on-page checklist/hint (not enforced) next to the upload control. | Attachments become filterable by category; the checklist itself nudges completeness without adding a required field. |
| New structured content invisible to search. | Extend the existing `watson.register()` `fields=` list (`TransitionsConfig.ready()`) to also include `contacts__name`, `contacts__notes`, `key_dates__label` — the SAME reverse-relation-traversal mechanism already indexing `answers__value` (decision R85). | Near-zero-cost: the moment the two new models exist, one line makes them fully full-text searchable too, no separate search UI needed for v1. |

### Security note found directly in the source documents, flagged before any of this ships

All three real documents paste ACTUAL PLAINTEXT PASSWORDS in the clear. This is exactly why `systems_access`'s help text already says "Do not paste actual passwords here — say where they're stored" (Default Prompt Set section) — but these real examples show that guidance alone does not stop it happening today, outside the system. If/when this system captures more of this content, worth deciding now, not after the fact:
- Keep the text-only help-text guidance as-is (status quo, cheapest, weakest), or
- Add a lightweight heuristic warning (e.g. detect a line that looks like `word@word / password`-shaped text in `systems_access` or a new structured "systems/access" field, and show an inline caution before submit — not a hard block, since some chapters may accept the risk deliberately) plus point at using a real shared password manager instead of this system for actual credentials.
- This is a real OWASP-relevant concern (plaintext secrets at rest in an application database) if we ever build a dedicated "systems & logins" structured field; recommend NOT storing password values in any new structured model, only "where it's stored" pointers, mirroring the existing help text's own instruction.

### Proposed additions (Phase 2, bigger structural change, discuss before building)

- **Successor Action Plan.** The formal template has the INCOMING officer fill out their own worksheet section after meeting the outgoing officer: people still to meet, steps for the first month, resources to review, open questions. Today, TRWI-7/8 only give the successor a read + a binary "I've read this" acknowledgment (`ReportAcknowledgement`) — there is no place for the successor to record their OWN plan, which is itself valuable institutional knowledge for the successor AFTER them. Would need a new small model (e.g. extend `ReportAcknowledgement` with a few optional text fields, or a new `SuccessorActionPlan` tied to the acknowledgment) and a small form on the handoff packet page. This is the biggest process change in this brainstorm — it turns the one-way "predecessor writes, successor reads" flow into a two-way exchange.
- **Repeatable "project" block.** The formal template's 3x repeated "Accomplishment / Challenges-Limitations / Resources Needed / Solutions / Tasks Involved" is a richer structure than the flat `successes` prompt. Could add an optional repeatable child model (e.g. `ReportProject`) for officers who ran distinct initiatives worth breaking out individually. Lower priority than Contacts/Key Dates since `successes`/`unfinished` already capture most of this in prose form; flagging as a nice-to-have, not a gap.

### Explicitly proposed as OUT of scope for Transition Reports (separate feature idea)

The Regent document's detailed week-by-week semester schedule (decoding right after the first meeting, initiation timing around holiday weekends, rush the week after IFC rush, recurring annual events like Retreat/Campfire/Formal/Alumni Dinner) is fundamentally different from the rest of this feature's content: it is a durable, continuously-refined **operating procedure** for running the chapter every term, not a one-time reflection on what one officer's term was like. Folding it into a per-term Transition Report means it gets rewritten from scratch (or copy-pasted) by every new Regent rather than incrementally maintained. Recommend NOT building this into Transition Reports; if it's wanted, it is a separate "chapter playbook"/wiki-style feature (its own decision, its own session doc, not scoped here). In the meantime nothing stops a Regent from pasting this into `first_30_days` or `anything_else`, or as a plain attachment.

### Decisions actually made (autonomous, please review)

1. **Phase 1: built in full.** `ReportContact` and `ReportKeyDate` (migration 0009, alongside `ReportAttachment.category`), both as repeatable `modelformset_factory` sections on the compose page (prefixes `contacts`/`key_dates`; `extra=3` blank rows when a report has none yet, `extra=1` once it has some, mirroring `objectives`/`notes`' own established "child rows of a parent" convention — see `views._build_contacts_formset`/`_build_key_dates_formset`/`_save_child_formset`). Both models registered with the anonymizer immediately after `makemigrations` this time (`ReportContact` is `register_clean` — real third-party PII; `ReportKeyDate` is `register_skip` — no PII). Watson's `fields=` list (`TransitionsConfig.ready()`) extended with `contacts__name`/`contacts__notes`/`key_dates__label`/`key_dates__timing`, confirmed working with a dedicated search test. `ReportAttachmentForm` gained the `category` field, and the attachment section grew a plain-text checklist hint (not enforced) listing the formal template's own attachment categories.
2. **Phase 2 (Successor Action Plan): deferred, not built**, per the recommended option — it is the biggest behavior change proposed (turns the one-way handoff into a two-way exchange) and deserves its own dedicated pass/review rather than being bundled in here. Still fully described above if you want it next.
3. **Credential heuristic warning: built.** `forms.ComposeReportForm._build_field` tags any prompt with `tag="systems"` (`systems_access` today, `national_systems` too if/when seeded) with a `data-warn-credentials` attribute; `static/js/transitions_compose.js` (vanilla JS, external file, CSP-safe, matches `whats_new.js`'s own style) shows an inline, non-blocking warning when the field's text looks like an email line immediately followed by a password-shaped token, or contains the word "password"/"pwd" near a value — heuristic, not a hard block, exactly matching all 3 real documents' actual pattern (email on one line, bare credential-looking token on the next).
4. **Chapter playbook (weekly schedule): confirmed out of scope**, per the recommended option. No code changes; still just a paragraph in this doc for if it's ever wanted as its own feature.

**Deliberately NOT done in this pass** (kept the diff focused on the 4 decisions above): no new UI for a "chapter contacts directory" aggregating `ReportContact` rows across reports (the data model supports it; no view was requested or built), no dynamic "add another row without a page reload" JS for the two new formsets (plain `extra=3`/`extra=1` blank rows instead — simpler, zero new JS, costs an extra "Save Draft" click only if someone has more than 3 contacts or dates in one sitting), `SearchFilter`/`TrendFilter` still do not surface `ReportContact`/`ReportKeyDate` content as filter fields (only via the full-text `q` search, per the watson extension above).

### Open questions for you

---

## TRWI-13 follow-up (2026-09-06/07) — More rows, URL hardening, access refinement, tag seeding

**Status: all 4 parts built and tested.** A direct 4-part request (not routed through clarifying questions this time): "what if I need more than 3 key contacts or dates? Also it's bad practice to have a url that just increments... As admin/national officer I should be able to see all chapter officer[s' reports]. The only limitation is that national officers (other than RD) should only see the reports related for them. And the Grand National Officers can see all reports. Finally, let's seed some additional tags for production." 346 tests passing in the transitions app (up from 340), 3251 passed / 16 skipped across the full regression sweep (up from 3244).

### 1. More than 3 contacts/dates: dynamic add-row JS (supersedes TRWI-13's "deliberately not done" note)

TRWI-13 Phase 1 shipped with static `extra=3`/`extra=1` blank formset rows (see that section's "Deliberately NOT done" bullet) — this request confirmed a real chapter can exceed that. Rather than bump the static `extra=` count (still an arbitrary ceiling), built a proper "add row without a page reload" pattern: `contacts_formset`/`key_dates_formset` are now always built with `extra=1`; `compose_form.html` renders `{{ formset.empty_form }}` inside a hidden HTML5 `<template id="<prefix>-empty-form">` (browser-native inert content, never submitted), with visible rows in `<div id="<prefix>-rows">`. `static/js/transitions_compose.js` (already loaded for the credential warning) gained `addFormsetRow(prefix)`: clone the template's `innerHTML`, string-replace `__prefix__` with the current `TOTAL_FORMS` value, append to the rows container, increment the hidden `TOTAL_FORMS` input. "Remove this row" on a not-yet-saved row just deletes the DOM node — safe because Django's `empty_permitted` logic skips forms with no submitted data regardless of index gaps; a saved row instead uses the existing DELETE checkbox. Did NOT reuse `static/js/dynamic_formset.js` (existing shared file) — it hardcodes a single-formset assumption and this page needs two independent formsets side by side.

### 2. URL enumeration hardening: `public_id` UUIDs

The compose/close-vacant/attachment-delete/acknowledge URLs used the raw auto-increment `pk` — a signed-in member could increment it and *request* another chapter's report, and even though `services.get_readable_reports`/`can_read_report` should reject an unentitled view, "the views should be locked down but still just in case we should not do that" (the user's own words) called for defense in depth against IDOR/enumeration, not just relying on the access-control layer being bug-free forever. Added `public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)` to `ReportObligation`, `TransitionReport`, `ReportAttachment` (NOT `Chapter` — shared codebase-wide, out of scope). URL converters changed `<int:pk>` → `<uuid:pk>`; kept the kwarg name `"pk"` (only the VALUE changes from `.pk` to `.public_id` at every call site, not the dict key) to minimize the diff across views/templates/tests. Views now do `get_object_or_404(Model, public_id=kwargs["pk"])`. Internal ORM lookups that were never a URL parameter (`services.can_read_report`'s `pk=report.pk`, test assertions like `ReportAttachment.objects.filter(pk=attachment.pk).exists()`) were deliberately left alone — the change is scoped to values that cross the URL boundary, not every `.pk` in the codebase.

Migration gotcha hit and fixed (full details in `/memories/repo/test-suite-facts.md`): a straight `AddField(unique=True, default=uuid.uuid4)` fails on PostgreSQL with a duplicated-key `IntegrityError`, because Postgres evaluates the callable default ONCE for the `ALTER TABLE` DEFAULT clause, not per row. Fixed with Django's documented 3-step pattern (nullable `AddField` → per-row `RunPython` backfill → `AlterField` to tighten `unique=True`).

### 3. Access control refinement: Council sees everything, other National Officers see only their own position

Before this change, `get_readable_reports` treated `user.is_national_officer_group` as a single "sees every report nationally" bucket. The request draws a real distinction the code didn't have: **Grand ("Council") officers and Admin** should keep full national visibility, but a **plain National Officer** (Candidate Chapter Director, National Director, etc. — anyone in `core.models.NATIONAL_OFFICER` who ISN'T Council and ISN'T RD) should only see reports for the SAME `position_key` they themselves hold, across any chapter — not every chapter's every report. RD keeps its existing, narrower, region-scoped rule unchanged (already correct, already narrower than the old blanket rule).

Implementation: `services.NATIONAL_OFFICER_SCOPED = NATIONAL_OFFICER - {"regional director"}` (RD has its own clause already; folding RD into the generic "same position, any chapter" rule would have let an RD see every OTHER region's RD reports too, which is not what the RD-specific clause intends). The "sees everything" gate changed from `is_national_officer_group` alone to `is_national_officer_group and is_council_officer()` (both needed: the former respects the `natoff_hidden` preview-as-member toggle, the latter narrows to actual `COUNCIL` role-holders). A new clause grants `Q(position_key__in=other_national_roles)` (unscoped by chapter) whenever the user holds a role in `NATIONAL_OFFICER_SCOPED`.

QA seed command (`seed_transition_reports_demo`) extended to exercise all three tiers distinctly: a new `"council"` account (Grand Scribe, sees everything), a new `"ccd_pred"` predecessor, and `"national_pred"` repointed to a different chapter/role so both the CCD and National Officer QA accounts have a same-position report to find OUTSIDE their own home chapter, proving the new rule without relying on chapter-scoping. `docs/specs/transition-reports-qa.md` updated to match, including a dated "2026-09 access tightening" callout explaining the behavior change for anyone reading the QA doc cold.

### 4. Seed additional tags for production: `seed_transition_tags`

New idempotent, re-runnable management command (`manage.py seed_transition_tags [--dry-run]`) — deliberately NOT gated by `core.seed_guard.ensure_seeding_allowed`, unlike `seed_transition_reports_demo`: that guard exists to keep FAKE demo/QA fixtures out of production, but this command seeds real vocabulary (actual region names, actual active chapter names, plus a curated general-purpose list), so running it in production is the intended use, not an accident to prevent. Seeds one `TransitionTag` per `Region.name` (no active/inactive concept on `Region`) and per `Chapter.name` where `active=True` (skips inactive chapters/colonies-turned-dormant), plus 8 hand-picked suggestions themed from the real transition documents examined during TRWI-13 but not already covered by the original 9 `TAG_CHOICES`: `budget`, `recruitment`, `ritual`, `vendor`, `housing`, `alumni`, `events`, `committees`. Dedup is case-insensitive (`name__iexact`), mirroring `TransitionTagAutocomplete.create_object`'s own dedup, so re-running after a new chapter is added only ever creates genuinely-new rows and never collides with a tag a member already typed in by hand. Chose to store region/chapter names in their natural display casing (e.g. "Beta", "Northeast") rather than lowercasing them like the original 9 abstract tags — there's no functional reason to lowercase a proper name, and the autocomplete's own search/create path is already case-insensitive either way.

---

## Page consolidation & wording pass (2026-09-09)

**Status: built and tested.** A direct 3-part request: drop "obligations" from user-facing text ("this is just the chapter transitions reports"), give the handoff packet page a link back, and stop splitting "other people's reports" across two places -- fold "Reports you can read" and the separate `/transitions/search/` page into ONE page (`transitions:list`), ordered Handoff packets → Vacant positions → My Reports → My Submitted Reports → Search reports (readable reports with a link out) → the viewer's own chapter's compliance/obligation table (status + acknowledged, includes reports they can't read yet). 345 tests passing in the transitions app (up from 340 -- some renamed/moved, a few retired as redundant), 3272 passed / 16 skipped across the full regression sweep (up from 3251).

### Decisions made

1. **"Obligations" renamed in USER-FACING text only, not in code.** Headings ("My obligations" → "My Reports"), messages ("You have no Transition Report obligations." → "You have no Transition Reports due."), table `empty_text`/column headers (`ObligationComplianceTable`, `ChapterRateTable`'s "Obligations" column → "Total Reports"), and the home page's "My Transition Report Obligations" card heading → "My Transition Reports". Did NOT rename `ReportObligation` (the model), `obligation`/`obligations` as Python variable/context-variable/template-loop-variable names, the `generate_transition_obligations` management command, or any URL/kwarg name -- all of that is internal, and renaming it would have meant a much larger, riskier change (migrations, services, every test) for zero user-visible benefit.
2. **`handoff_packet.html` gained a back link** (`&laquo; Back to Transition Reports` → `transitions:list`), matching the pattern `search.html` already had. It had none before; every other transitions page does.
3. **`transitions:list` absorbed `transitions:search`'s content for the viewer's own chapter.** `TransitionsListView` now also resolves `self.chapter` (mirroring `ReportSearchView`'s old "elif no chapter_pk" branch) and calls two NEW module-level helpers shared with `ReportSearchView` -- `_search_context(request)` (the search filter + `SearchResultsTable`, extracted verbatim from `ReportSearchView.get_context_data`) and `_dashboard_context(request, chapter)` (the compliance table, extracted from `ReportSearchView._dashboard_context`). `transitions:search` (no `chapter_pk`) now just `redirect("transitions:list")` immediately in `dispatch()` -- kept resolvable so an old bookmark/link doesn't 404, but has no content of its own anymore. **`transitions:chapter-dashboard` (explicit `chapter_pk`, RD/National Officer/Admin inspecting a chapter that ISN'T their own) is completely unchanged** -- same view, same template, same access check -- since `transitions:list` only ever shows the VIEWER's own chapter.
4. **"Reports you can read" section removed outright**, not just re-pointed -- its job (browse/read other people's reports) is now `Search reports`' job, and `Search reports` already does it better (full-text query, tag, cycle, chapter/region filters, pagination) than the old section ever did (no filters, no pagination). The old "My chapter only" / "Everything I can read" scope toggle was ALSO removed for the same reason -- `NationalSearchFilter`'s own chapter/region dropdown fields already cover picking a specific chapter or region for anyone with that access, more flexibly than a binary toggle.
5. **The two tables stayed separate** (search results table + chapter compliance table), placed together under one "Search reports" heading rather than merged into a single django_tables2 table -- lower risk, and their column sets never really overlapped (compliance is per-obligation with status/acknowledged; search is per-submitted-report with author/tags/a link out).
6. **Test suite mechanically reshuffled**: every `test_search_view_*`/`test_chapter_dashboard_url_reaches_the_same_merged_page` test that hit `transitions:search` with NO `chapter_pk` was renamed/moved to hit `transitions:list` instead (same assertions, since the content moved verbatim); tests exercising the explicit-`chapter_pk` case were left completely untouched. Two now-meaningless tests were deleted outright (`test_transitions_list_readable_report_view_link_points_to_the_handoff_packet`, `test_transitions_list_excludes_own_report_from_readable_reports_table` -- both about "Reports you can read" specifically, fully superseded by the equivalent search-section tests) along with the two scope-toggle tests (feature removed). One pre-existing test (`test_transitions_list_does_not_show_someone_elses_obligation`) started failing not because of a real regression but because the new Search reports filter form's position dropdown always lists every `POSITION_KEY_CHOICES` value (including "grand scribe"), so its old broad `"scribe" not in body` assertion started tripping on that unrelated dropdown option -- fixed by asserting against `response.context["obligations"]` directly instead of scanning the whole rendered page for a substring.

**Deliberately NOT done in this pass**: no change to `ComplianceRatesView`/`TrendView` (separate pages, not mentioned in the request); no attempt to also merge the chapter-compliance table and search-results table into one combined table (see decision 5); no change to the underlying `services.search_reports`/`get_readable_reports` access-control logic itself (only which VIEW/TEMPLATE surfaces their results changed).

---

## One combined reports table + "completion rates" wording (2026-09-09)

**Status: built and tested.** Follow-up to the page consolidation above: "combine the tables ## Search reports and ### [QA] Transitions Chapter Alpha Transition Reports into one table" plus "the description said compliance we don't actually use that term more like completion rates." 345 tests passing in the transitions app (unchanged count -- existing tests already covered the merged behavior), 3272 passed / 16 skipped across the full regression sweep (unchanged).

### What changed

- **One table, not two.** `services.get_report_rows(user, chapter=None, **filters)` (new) replaces the separate `search_reports` call + `ObligationComplianceTable` query. It always includes every submitted report the viewer may read (`search_reports`, unchanged access rules), and -- only when narrowed to one specific `chapter` -- ALSO adds a row for every OTHER obligation in that chapter with no readable report yet (open/missed/na_vacant, or submitted but unreadable), deduplicated by obligation id so a chapter's own submitted+readable report never appears twice. Rows are a plain `ReportRow` dataclass (position, chapter name, person, status, due date, submitted date, acknowledged, tags, a link out), rendered by one new `tables.ReportRowTable` (backed by a list, like `ChapterRateTable`/`TagFrequencyTable` already were) -- `ObligationComplianceTable` and `SearchResultsTable` are both deleted, along with the now-dead `ObligationComplianceFilter` (filters.py) and `ComplianceFilterFormHelper` (forms.py) that only ever fed the old, separate compliance table.
- **The "chapter" scope now comes from ONE filter form.** The old separate "Filter reports" form (position/status/cycle-by-due-date, `obl_`-prefixed) is gone entirely -- the single "Filter search" form's own `chapter`/`region` fields (already shown to national-scoped viewers) now ALSO control which chapter's full obligation picture is merged in. A national/RD/Council viewer's explicit chapter/region pick takes priority over their own membership chapter, so switching the filter switches which chapter's complete picture is shown -- picking "no chapter" falls back to whatever `chapter` the view resolved (the viewer's own, or an explicit `chapter_pk` for `ReportSearchView`). "Status" (open/missed/etc.) is no longer a separate filter field -- it's visible directly as the row's own Status column instead.
- **Link-out logic moved into the service layer.** `_position_link` (the old `tables.py` `linkify` callable needing `table.request` set after construction) is gone -- `get_report_rows`/`_report_row`/`_obligation_row` compute `link_url` directly (own report always -> compose; someone else's readable report -> the handoff packet; the viewer's own still-open/missed obligation -> compose; anyone else's still-open obligation -> no link, nothing to act on yet), since the acting `user` is already in scope where the row is built.
- **"Compliance" -> "Completion" in visible text only.** "Compliance rates" button -> "Completion rates"; `rates_dashboard.html`'s title/H1 "Transition Report Compliance Rates" -> "...Completion Rates"; `ComplianceRatesView`'s denial message -> "You are not able to view the completion rates dashboard." Did NOT rename `ComplianceRatesView`/`can_view_compliance_rates`/`ComplianceRateFilter`/`get_chapter_compliance_stats`/`ChapterComplianceStats` (internal class/function names) or the `dashboard/rates/`/`rates-dashboard` URL name/path -- same "text only" precedent as the earlier "obligations" wording pass. `ComplianceRatesView` itself (the separate regional/national submission-rate-by-chapter page) was NOT touched structurally -- it aggregates across many chapters into one row per CHAPTER, a fundamentally different shape than the per-report/per-obligation combined table, and the user's request was specifically about the two ROW-level tables on the list/search page.
- **A stray, badly-executed edit mid-session left the file with duplicate `_search_context`/`ReportSearchView` definitions and a missing `class ComplianceRatesView(...)` declaration line** (a multi-part string replacement matched further than intended). Caught immediately via `get_errors`/grep for duplicate `^class /^def _` lines before running anything, and fixed with two precise follow-up edits (re-insert the missing class line, delete the orphaned duplicate block). Lesson for next time: after ANY edit that spans a class boundary or "through a class declaration line," re-grep for `^class |^def ` immediately and count occurrences before assuming the edit landed correctly -- `get_errors` alone did NOT catch this (the corrupted arrangement was still syntactically valid Python, just semantically wrong).

**Deliberately NOT done in this pass**: no change to `TrendView` or `ComplianceRatesView`'s own structure (only wording); no attempt to preserve a separate "status" filter for the merged table (dropped, status is now a visible column instead); no change to `get_readable_reports`/`search_reports`'s access-control rules (only how their results get combined with obligation data for display).

---

## "Why is My Reports empty" explanation + a fix for `tag_list` (2026-09-10)

**Status: built and tested.** Two small follow-ups, same day: (1) `TransitionReport.tag_list` called `tag.get_tag_display()`, which stopped existing the moment `ReportTag.tag` went free-form (no `choices=`, TRWI-11) -- 500ed `/transitions/` the moment any rendered report had a tag. Fixed to join the raw `tag.tag` values instead. (2) The empty "My Reports" state ("You have no Transition Reports due.") got a `services.get_no_obligations_reason(user)` explanation, since a member has no way to tell "too early" from "not required" from a bug. Checked in order: no current role in an in-scope position at all -> generic "you don't hold a position..."; EXCEPT Regional Director/other national-level roles with no `UserRoleChange` term (RD is `Region.directors` M2M, never a role change with dates) get their own explanation instead, since the generic one is actively misleading for someone who clearly does hold an important position -- found by the user logging in as the QA `rd@...` account and seeing the generic message; every current role "excluded" (override/Config flag) -> says so; otherwise too early -> names the soonest role, its term end, and the actual computed due date. Also fixed a **user-facing text style violation caught while writing this**: the "too early" message originally used `" -- "` (ASCII double hyphen), against the repo's own no-em-dash-or-double-hyphen convention for text a member reads -- changed to a colon.

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

### Q. TRWI-10 — Full history: no retention, archiving, or pinning (verified 2026-09-05)

Unlike L-P, this section records a VERIFICATION, not a judgment call awaiting your review — there was no ambiguity to resolve. Every retention/archive/pinning field the ORIGINAL proposal called for was already dropped from the data model back at the 2026-09-04 codebase review round (decisions F13/H18), so TRWI-1 through TRWI-9 never built any of it in the first place. TRWI-10's own job was to confirm that and lock it in with regression tests, not write new code.

- **Q76 — No code changes.** Grepped the entire `thetatauCMT/transitions` app, its templates, and its migrations for `archiv`/`pin`/`retention` — the only hit is a comment in `services.py` describing this very decision. No `is_pinned`/`pinned_by`/`pinned_reason`/`archived_at`/`retention_expires_on` field, filter, admin option, or management command exists anywhere in the feature, and none needed to be removed.
- **Q77 — Added a permanent regression guard**: a test that walks every transitions model's `_meta.get_fields()` and asserts none of the five forbidden field names are present. If anyone ever reintroduces one of them (e.g. copying a pattern from another app that DOES retain/pin), this test catches it immediately rather than relying on someone remembering this decision.
- **Q78 — Added "full history, no time-based cutoff" regression tests**: a `TransitionReport` with `created`/`submitted_at` set 10 years in the past is still returned by `get_readable_reports`/`get_handoff_packet` (service level) and still renders on the handoff packet page (view level) — proving there is no hidden lookback window anywhere in the READ path. (`send_handoff_notices`' own `LOOKBACK_GRACE_DAYS` bound, TRWI-7/N-series, is a NOTIFICATION-dedup scope, not a report-visibility cutoff — confirmed these are two different concerns that don't conflict.)
- **Q79 — Added a "sorts purely by recency" regression test**: two reports with deliberately non-chronological `created` timestamps come back most-recent-first with no reordering possible — there is no pin/feature field anywhere in the model for anything to sort by except recency.

### R. TRWI-11 — Tags, search, trends (implemented autonomously 2026-09-06 — please review)

TRWI-11 is implemented, migrated, and tested (309 tests passing in the transitions app, up from 255; 3214 passed / 16 skipped across the full regression sweep). One new model (`ReportTag`), no new daily command — everything else is services/filters/tables/views/templates on top of TRWI-6's existing access service.

- **R80 — `ReportTag` has `unique_together = (report, tag)`, not `(report, tag, source)`.** A tag is either present on a report or it isn't, regardless of HOW it got there — `source` only records provenance for display/audit, never lets the same tag value exist twice on one report under two different sources. `set_manual_tags`/`derive_prompt_tags` both use `get_or_create`, so if a manually-added tag happens to also be prompt-derivable, the existing row (whichever source added it first) is reused rather than erroring or duplicating.
- **R81 — `derive_prompt_tags` is fully destructive-and-rebuilt on every call** (`source="prompt"` rows deleted, then recreated from the CURRENT answers), called from `submit_report` unconditionally, every submission (including re-submission/edits, since TRWI-5/F15 allows editing indefinitely). This guarantees prompt-derived tags never go stale after an author changes their answers on a later edit. `source="manual"` rows are NEVER touched by this function — only `set_manual_tags` (a separate, author-driven action) adds/removes them.
- **R82 — Manual tags are edited on the EXISTING compose form** (`ComposeReportForm.manual_tags`, a `CheckboxSelectMultiple` over the controlled `TAG_CHOICES` vocabulary), not a new page/view. Saved on BOTH draft save and submit (`services.set_manual_tags` called from both branches of `ComposeReportView.post`) — same "works regardless of draft/submit state" precedent as attachments (TRWI-5).
- **R83 — Search is restricted to `status="submitted"` reports EVEN FOR THE AUTHOR'S OWN DRAFT** — the one deliberate narrowing beyond what `get_readable_reports` alone would allow (which lets an author read their own draft). Searching your own half-written draft alongside a "mine cross-chapter knowledge" query doesn't fit the feature's purpose; you're already looking at the draft in the compose view. Implemented by passing `status=<submitted>` as an EXTRA filter into `get_readable_reports(user, status=...)`, which ANDs against the author's own OR-branch too, not just the successor/Regent/RD/national branch that was already submitted-only per TRWI-6/M46.
- **R84 — `watson.register()` is called with a QUERYSET (`TransitionReport.objects.filter(status="submitted")`), not the bare model class** — mirrors `jobs.apps.JobsConfig`'s existing `model.get_live_jobs()` precedent (the only other queryset-scoped registration in this codebase, vs. `users.apps`'s bare-model registration). This means a draft can NEVER appear in the watson index at all, belt-and-suspenders on top of R83's own service-level restriction — even a future caller who queries the watson index directly instead of going through `services.search_reports` still can't surface a draft.
- **R85 — `fields=["position_key", "answers__value", "chapter__name", "author__name"]` relies on `watson.search.SearchAdapter._resolve_field`'s own reverse-relation traversal** (confirmed by reading the installed package source, then empirically with a throwaway test): when a field name resolves to a related manager/queryset instead of a scalar, `_resolve_field` recurses into each related object and joins the results with spaces. `answers__value` therefore indexes the FULL text of every `ReportAnswer` on the report, not just a single field — this is what makes "full-text over answers" (the spec's own wording) come from one `fields=` entry rather than a hand-rolled join.
- **R86 — Confirmed empirically: watson's index for a model only updates when THAT model instance itself is saved, not when a related child row changes.** Creating/updating a `ReportAnswer` alone does NOT refresh its parent `TransitionReport`'s search index; the parent's OWN `.save()` must run afterward. This is not a bug to fix — `submit_report` already calls `report.save()` unconditionally after `_save_answers()`, so production is correct by construction — but it drove a test-writing lesson: any test creating `ReportAnswer` rows directly (bypassing `submit_report`) and expecting watson to find them via `search_reports(query=...)` must explicitly call `report.save()` afterward, or the match silently fails. Recorded in `/memories/repo/test-suite-facts.md` for future sessions.
- **R87 — `search_reports`'s `cycle` defaults to `DEFAULT_CYCLE` ("current"), matching the rest of TRWI-9's cycle-bounded services, but the SEARCH VIEW itself defaults the GET param to `"all"`** (`views._default_search_cycle`, a sibling of TRWI-9's `_default_cycle` with a different default), not `"current"`. Rationale: search exists to mine PAST institutional knowledge across cycles; defaulting the user-facing page to "current cycle only" would hide most of what search is for, even though the underlying service function's own default stays "current" for callers who don't specify (consistency with `get_tag_frequency`/other TRWI-9 functions that all default to "current"). The national trend view (`TrendView`), by contrast, DOES default to "current" (`_default_cycle`, unchanged) — trends is a dashboard-style "how are we doing this cycle" surface, not a knowledge-mining one.
- **R88 — National trend view (`get_tag_frequency`/`get_chapters_with_no_submissions`) is NOT scoped through `get_readable_reports`.** Both operate directly on `TransitionReport.objects.filter(status="submitted")`, gated only at the view level by a new `can_view_trends(user)` (National Officer/Admin only — no RD branch, deliberately narrower than `can_view_compliance_rates`). This is consistent with TRWI-6's own rules, not a bypass of them: TRWI-6 already says National Officer/Admin may read ALL submitted reports, so a view restricted to that same audience showing aggregate counts over all of them needs no additional per-row filtering — the access check is "may this VIEWER see this VIEW at all," matching how `ComplianceRatesView` (TRWI-9/P69) already gates by role rather than re-filtering rows the viewer's role already entitles them to see in full.
- **R89 — No new feature registry entries for search or trends** — both are sub-pages reached only via links from the already-registered `transition-reports` list page, matching TRWI-5/7/9's own precedent (L45/N61/P75: only the primary list view gets a catalog entry). The EXISTING `transition-reports` entry's `long_description` was reworded instead (the STANDING RULE's own "reword neighbouring entries the change makes wrong" clause) to mention both new capabilities, so the catalog text stays accurate without adding two more cards for what's still fundamentally one feature area. Verified with `load_feature_registry --dry-run` (`1 updated`, everything else unchanged) and the full `guides` suite (216 passed).
- **`ReportTag` also needed a `dj_anonymizer` registration** (`register_skip`, alongside the other TRWI-1/2/3/5/7 metadata-only models) — caught by the same full-suite regression test K34 already fixed once for the earlier models (`core/tests/test_anonymizer.py::test_every_model_is_registered_with_the_anonymizer`); a new model in this app needs this every time, not just at initial rollout.

### S. TRWI-12 — QA seed data (implemented autonomously 2026-09-06 — please review)

TRWI-12 is implemented and tested (14 new tests; 3228 passed / 16 skipped across the full regression sweep, up from 3214). One new management command, one new QA spec doc — no migration, no new model.

- **S90 — No `--seed`/Faker, contrary to the work item's own "`--seed` for reproducibility" wording.** Every chapter, user, and answer is hand-written and identical on every run — there is nothing random to seed, since the whole point is a small, memorable, exactly-reproducible dataset a human can QA against ("log in as `treasurer@transitions-qa.thetatau.local`", not "log in as whichever name Faker picked this run"). The command is already fully idempotent without an RNG seed. Flagging this explicitly since it's a deliberate deviation from the work item's literal wording, not an oversight.
- **S91 — Reuses the real service layer everywhere one exists** (`generate_obligations`, `get_or_create_report`, `submit_report`, `close_as_na_vacant`, `acknowledge_report`, `set_manual_tags`) rather than hand-constructing `ReportObligation`/`TransitionReport` rows directly. Consequence worth calling out: `generate_obligations()` scans *every* chapter's officer terms, not just the QA ones — if the target database already has real chapters with officer terms ending soon, a handful of unrelated real obligations may also appear. This is identical to running the daily `generate_transition_obligations` command and is documented as an expected side effect in `docs/specs/transition-reports-qa.md`, not suppressed.
- **S92 — Discovered and fixed a real ordering bug: this command must call `seed_transition_prompt_set` itself.** It worked the first time only because the dev container already had TRWI-2's type-default templates seeded from an earlier session; a genuinely fresh database (a pytest test DB, or a real fresh install) has none of them, so every non-treasurer position (regent, scribe, grand regent, events chair, national officer) failed with `IntegrityError: null value in column "template_id"`. Fixed by calling `call_command("seed_transition_prompt_set", verbosity=0)` unconditionally at the top of `handle()` — idempotent, so always safe. Recorded in `/memories/repo/test-suite-facts.md` as a general lesson (verify new seed commands against a fresh pytest DB, not just the long-lived dev container).
- **S93 — One position-specific override, `treasurer`, distinct from `seed_transition_prompt_set`'s 4 type defaults** — adds a `financial_handoff` prompt on top of a subset of the shared core prompts, satisfying the work item's own "including one position-specific override" bullet and giving the multi-generation chain something to demonstrate exact-match-over-type-default resolution with.
- **S94 — Four dedicated chapters across two regions, not a randomized count.** Alpha (treasurer multi-generation chain + Regent + missed Scribe), Beta (national officer + CCD + Council + Committee Chair + vacant Vice Regent), Gamma (deliberately **zero** Transition Report activity, so the trend view's "chapters with no submissions" has something to show), and Delta (in a **separate** second region, so RD-scoped views have something concrete to exclude while national views include it). This was necessary to give every TRWI-6 rule (successor/Regent/RD/CCD/national/outsider) a genuinely distinguishing scenario rather than everyone seeing the same data.
- **S95 — `--flush` never touches the shared prompt-set templates** (the 4 type defaults or the treasurer override) — only seed users (matched by email domain), the 4 seed chapters, and the 2 seed regions. Templates are permanent, cross-cutting content (like any other `seed_transition_prompt_set` row), not per-run demo data, and deleting them could `ProtectedError` against a real report using them (`TransitionReport.template` is `on_delete=PROTECT`, decision L37).
- **S96 — Named login accounts, one per TRWI-6 access role, each with a real open obligation where realistic** (treasurer/Regent/CCD/National Officer all have their own composable obligation, not just read access) — so a QA reviewer can exercise BOTH the read side (TRWI-6/7/8/9/11) and the write side (TRWI-5) of each role without needing to look up or construct any additional test data by hand. Full expected-visibility-per-role table lives in `docs/specs/transition-reports-qa.md`, not duplicated here.

### T. UI/UX polish pass (implemented 2026-09-06, please review)

Follow-up request after actually using the shipped feature: 5 small fixes, all implemented and tested (3232 passed, 16 skipped across the full regression sweep, up from 3228).

- **T97, home page link fix.** The "Submit a Transition Report" button on the home page's "My Transition Report Obligations" card (`_home_obligations_card.html`, TRWI-4) linked to `forms:landing` (the general Forms landing page). It now links straight to `transitions:list` (`/transitions/`), since the viewer already sees their own open obligations right there and does not need an extra hop through Forms landing first.
- **T98, "Additional tags" is now an autocomplete-with-create dropdown, not fixed checkboxes.** New model `TransitionTag` (a free-form vocabulary, same shape as `jobs.Keyword`/`users.Position`) backs a new `transitions:tag-autocomplete` endpoint (`TransitionTagAutocomplete`, copies the established `has_add_permission`/`validate_create`/manager-based `create_object` pattern already used by `jobs.views.VocabularyAutocomplete`/`users.views.PositionAutocomplete`). `ReportTag.tag` itself stays a plain CharField (now unrestricted: `max_length` raised from 20 to 50, `choices=TAG_CHOICES` dropped), so `ComposeReportForm.manual_tags_data()` still hands `services.set_manual_tags` a list of plain tag-name strings and `services.py`/`filters.py`'s existing tag code needed no changes at all. Migration 0008 seeds the original 9 `TAG_CHOICES` names into `TransitionTag` so prompt-derived tags (still admin-curated via `TemplatePrompt.tag`'s own fixed choices, left untouched) always have a matching row, and the dropdown is not empty on first use. `TransitionTag` is registered in Django admin with `MergeableAdminMixin` (lets an admin merge near-duplicate free-form tags later) and in `anonymizer/transitions.py` (`register_skip`, same free-vocabulary category as Keyword/Major/Position).
  - **Deliberate scope boundary, flagged for awareness:** `SearchFilter.tag` (Search page) and `TrendFilter` (Trends page) still only offer the original 9 `TAG_CHOICES` values, not the full open `TransitionTag` vocabulary. A newly-created free-form tag can be attached to a report via "Additional tags" but is not yet searchable or filterable from Search or Trends. This also means TRWI-11's original "keep the tag vocabulary short and stable so cross-chapter trend counts stay meaningful" principle no longer strictly holds for manually-added tags going forward; accepted as a tradeoff per this explicit request, worth a follow-up look if trend data gets noisy with near-duplicate free-form tags.
- **T99, "My chapter dashboard" and "Search reports" condensed into one page.** `ChapterComplianceView` (the old standalone `dashboard/chapter/<pk>/` page) was folded into `ReportSearchView`. The same page now shows the obligation-compliance table (when the viewer can see it: a chapter officer for their own chapter, or an explicit `chapter_pk` for RD/National Officer/Admin) above the existing search section. Both URL names still resolve (`transitions:chapter-dashboard` and `transitions:search` route to the same view and template, so the access-control tests written against the old URL kept working unchanged). The dashboard filter's own fields are now `obl_`-prefixed (`obl_position_key`/`obl_cycle`) and its table uses `prefix="obl_"`, so its GET params (filter, pagination, sort) never collide with the search section's; the two remain independent `<form>`s on the one page (django_tables2/`_partials/collapsible_filter.html`'s own design), so filtering one does not preserve the other's own filter state. This is a known, accepted trade-off for two independent filterable sections on one page, not a bug. The "My chapter dashboard" link on the Transitions list page was removed; "Search reports" (relabeled "Dashboard & search reports") is now the one link everyone gets, and it shows the dashboard section automatically whenever the viewer qualifies for it.
- **T100, back link.** A "Back to Transition Reports" link to `transitions:list` was added at the top of the merged dashboard/search page, doubling as the natural "back" affordance now that the page covers two sections instead of one.
- **T101, role guides now mention Transition Reports.** Added one step each (`"feature": "transition-reports"`) to the 7 required chapter-officer role guides (regent, vice regent, scribe, treasurer, corresponding secretary, pledge/new member educator, risk management chair, `cadence: "each_term"`, "write your own, read what came before" framing) plus regional director and national officer (`cadence: "ongoing"`, read-only framing: search plus the compliance dashboard for RD, search plus trends for national officer). Adviser was deliberately skipped: `services.get_readable_reports` gives an adviser no access at all unless they separately hold an officer, RD, or national role, so a step there would point at a page most advisers cannot actually use.

**Gotcha hit again despite the existing memory note:** forgot to register the new `TransitionTag` model with the anonymizer until the full test suite finally caught it (`core/tests/test_anonymizer.py::test_every_model_is_registered_with_the_anonymizer`), exactly the failure mode `/memories/repo/anonymizer.md` already documents from the original TRWI-1/2/3 build. Fixed by adding `TransitionTag` to `anonymizer/transitions.py`'s existing `register_skip` list. No change needed to that memory note, its advice was correct; the lapse was in following it during a long implementation block instead of checking it at model-creation time.

---

## Pre-Launch Checklist

- [ ] **Default Prompt Set review** — get a pass from someone who has actually held a chapter office before the prompt set is seeded to production; `prompt_key` values become immutable once shipped (F16). Discussion draft ready: `docs/specs/transition-reports-prompt-questions.md` (tailored ≤10-question sets for each of the 7 required chapter officer positions, plus generic Committee Chair and National Officer/Council sets) — walk this with actual officers, then update `seed_transition_prompt_set.py` with whatever survives.
- [x] Feature registry entry added for the Transitions page(s) and verified with `load_feature_registry --dry-run` (this is also what makes the row appear on Forms landing). Done 2026-09-05 (TRWI-5, key `transition-reports`); reworded 2026-09-06 to mention search/trends (TRWI-11, still the same `transition-reports` key — see R89).
- [ ] **`manage.py buildwatson` MUST run after deploy** — TRWI-11's search is now implemented via `watson` (`TransitionsConfig.ready()` registers a `status="submitted"`-filtered queryset). Without this one-time command the search index has zero entries until the next unrelated save touches each report. Verified locally only so far — still needs to actually run once against any real deploy.
- [ ] Schedule the new `send_transition_handoff_notices` daily command on PythonAnywhere (TRWI-7) — separate from the existing `send_transition_report_reminders` task (decision N53); both must run daily.
- [x] QA seed data (TRWI-12): `python manage.py seed_transition_reports_demo` (add `--force` outside DEBUG). See `docs/specs/transition-reports-qa.md` for the full account list and walkthrough.

---

## Remaining Open Questions

None from the original codebase review round, TRWI-3 (I20-I23, J24), TRWI-4 (K25-K34, confirmed), or TRWI-10 (Q76-Q79, verification only — nothing to review) — see Decisions Log A-K, Q. TRWI-5's design choices (L35-L45), TRWI-6's (M46-M52), TRWI-7's (N53-N61), TRWI-8's (O62-O67), TRWI-9's (P68-P75), TRWI-11's (R80-R89), and TRWI-12's (S90-S96) are implemented and tested but not yet reviewed by you; see the Decisions Log entries above. Every TRWI-1 through TRWI-12 work item is now implemented.
