# Awards Feature — Copilot/Claude Work Breakdown

## Shared Preamble (paste once per session)

Project conventions for all Awards work items:

- **Stack:** Django + PostgreSQL in Docker containers. Reuse existing app patterns. Use Django Viewflow for any approval workflow — follow the SAME patterns used in the recently built Volunteer Nomination flow (config-driven task assignment, Process/Flow classes, node types, templates).
- **Roles:** Member, Chapter Officer, RD (Regional Director), National Officer, Admin. Map all permissions to these existing roles. Reference positions from `core.models.NAT_OFFICERS` where relevant.
- **Working style:** Prefer configuration over hard-coded rules. Establish migrations/models FIRST and pause for confirmation, then services/logic, then views/templates, then tests by acceptance criterion. Gate every capability by role/permission.

### Awards architecture (agreed)

- Single **AwardType** catalog (admin-managed) shared by all recipient kinds.
- Award **LEVELS:** member, chapter, region, alumni, active, PNM, national. (Level determines recipient kind + eligibility scope.)
- Single polymorphic **AwardGrant** linking to a recipient (Member OR Chapter OR Region) — use nullable FKs or a generic relation; propose and recommend which fits the codebase.
- Each AwardType configures its **GRANT METHOD:** `direct` or `nomination_workflow`.
- Each AwardType configures **WHO IS ELIGIBLE** (recipient eligibility rules) AND **WHO CAN NOMINATE** (nominator scope: member / officer / national), so the UI can populate the correct award list per role and the correct eligible-recipient list per award.
- Awards belong to **AWARD CYCLES** (period/year/event) with per-award cycle rules (recurring vs one-time; one winner vs multiple; multiple nominations allowed vs not).
- Awards can be **backdated** (needed for historical import) and **revoked/rescinded** (retain full audit history).
- All awards are **public**. Awards show on member profiles, chapter profiles, and a public awards dashboard. Badges/icons appear on profiles and inline next to member names site-wide (also usable for officer icons).
- Full **audit trail** on every grant/revoke. Notifications on nomination and grant; home-page announcements; monthly email digest. Certificates/letters auto-generated or uploaded.

---

## Target Data Model

> These are the target entities/fields for the feature. Propose exact Django field types + migrations per work item and pause for confirmation. Reuse existing base classes, timestamp mixins, and audit patterns where they exist.

### AwardType (AWI-1)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| name | CharField | |
| description | TextField | |
| category | CharField/FK | Award category (choices or lookup table) |
| level | CharField (choices) | member / chapter / region / alumni / active / pnm / national |
| badge_image | ImageField/FileField | Icon/badge shown on profiles + inline |
| points | Integer (nullable) | Optional weight for standings/rollups |
| grant_method | CharField (choices) | `direct` \| `nomination_workflow` |
| recurrence | CharField (choices) | `one_time` \| `recurring` |
| single_winner | Boolean | Enforce one winner per cycle when true |
| allow_multiple_winners | Boolean | Complement/mutually-exclusive with single_winner |
| allow_multiple_nominations | Boolean | Same recipient nominated multiple times per cycle |
| nominator_scope | CharField/M2M (choices) | member / officer / national (drives AWI-6 lists) |
| is_active | Boolean | Retired awards excluded from active lists |
| created_at / updated_at | DateTime | |

### AwardCycle (AWI-2)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| name | CharField | e.g., "2025", "Fall 2025", "2025 Convention" |
| period_type | CharField (choices) | year / term / event |
| start_date | Date (nullable) | |
| end_date | Date (nullable) | Nullable for open/ongoing |
| event | FK → Events (nullable) | Reuse existing Events app when event-based |
| created_at / updated_at | DateTime | |

*Note: per-award cycle rules (single/multiple winner, multi-nomination) live on AwardType; AwardCycle provides the period context they are enforced within.*

### AwardGrant (AWI-3) — polymorphic recipient

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| award_type | FK → AwardType | |
| cycle | FK → AwardCycle | |
| recipient_member | FK → Member (nullable) | One-of recipient (or use GenericFK — propose) |
| recipient_chapter | FK → Chapter (nullable) | |
| recipient_region | FK → Region (nullable) | |
| granted_by | FK → User | |
| granted_at | DateTime | Real system timestamp |
| effective_date | Date | Supports BACKDATING; used for display/reporting |
| reason | TextField | Justification |
| status | CharField (choices) | `active` \| `revoked` |
| source | CharField (choices) | `direct` \| `nomination` \| `import` |
| revoked_by | FK → User (nullable) | |
| revoked_at | DateTime (nullable) | |
| revoke_reason | TextField (nullable) | |

*Constraint: exactly one recipient_* populated (enforce in clean()/DB constraint). Never hard-delete; revoke sets status.*

### EligibilityRule (AWI-4)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| award_type | FK → AwardType | |
| rule_type | CharField (choices) | member_status / chapter_scope / region_scope / recipient_kind / custom_hook |
| member_status | CharField (nullable) | active / alumni / pnm (for member_status rules) |
| chapters | M2M → Chapter | Scope restriction (for chapter_scope) |
| regions | M2M → Region | Scope restriction (for region_scope) |
| hook_key | CharField (nullable) | Identifier for pluggable custom check (tenure, attendance, etc.) |
| params | JSONField (nullable) | Parameters for the hook |

*Service `get_eligible_recipients(award_type, cycle, actor)` combines all rules AND the actor's role scope. `is_eligible(award_type, recipient)` for single checks.*

### AwardNominationProcess (AWI-7) — Viewflow Process

| Field | Type | Notes |
|---|---|---|
| id | PK | Extends Viewflow Process |
| award_type | FK → AwardType | |
| cycle | FK → AwardCycle | |
| recipient_* | FK (nullable) | Same polymorphic recipient pattern as AwardGrant |
| nominator | FK → User | |
| justification | TextField | |
| supporting_docs | FileField (nullable) | Optional attachment |
| result | CharField (choices, nullable) | approved / rejected |
| reject_reason | TextField (nullable) | |
| resulting_grant | FK → AwardGrant (nullable) | Set on approval |

*Approver resolved via config (mirror the volunteer StepAssignment pattern).*

### GrantArtifact (AWI-8)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| grant | FK → AwardGrant | |
| artifact_type | CharField (choices) | `generated` \| `uploaded` |
| file | FileField | Certificate/letter |
| generated_at / uploaded_at | DateTime | |
| created_by | FK → User | |

### GrantAudit (AWI-3)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| grant | FK → AwardGrant | |
| action | CharField (choices) | created / revoked / imported / updated |
| actor | FK → User | |
| timestamp | DateTime | |
| detail | JSONField/Text | Snapshot/notes |

*Reuse an existing audit mechanism if one exists; otherwise implement this table.*

### AwardImportMatchQueueItem (AWI-13)

| Field | Type | Notes |
|---|---|---|
| id | PK | |
| raw_row | JSONField | Original import row |
| award_type | FK → AwardType (nullable) | Resolved award |
| candidate_matches | JSONField | Candidate recipients + confidence scores |
| resolved_recipient_* | FK (nullable) | Set on manual resolution |
| status | CharField (choices) | pending / resolved / skipped |

*Reuse the attendance national-upload matching approach + admin manual-match queue.*

---

## AWI-1 — Award catalog foundation

**Work item:** AwardType catalog (admin-managed). See **AwardType** table.

AwardType fields:
- name, description, category, level (member/chapter/region/alumni/active/PNM/national)
- badge_image/icon, points/weight (nullable), active/retired flag
- grant_method: `direct` | `nomination_workflow`
- recurrence: `one_time` | `recurring` (annual/term/event-based — tie actual periods to cycles in AWI-2)
- allow_multiple_nominations (bool), single_winner vs allow_multiple_winners (per cycle)
- nominator_scope: which roles may nominate (member / officer / national) — drives which awards appear in each role's nomination view (AWI-6)
- placeholders/config hooks for eligibility rules (implemented in AWI-4) and cycle rules (AWI-2)

Deliver migrations first (pause), then Django admin registration for managing the catalog.

**Tests:** create award types across all levels; grant_method + nominator_scope persist; retired awards excluded from active lists; badge/icon stored.

**Status (2026-07-16) — DONE:**
- New app `thetatauCMT/awards/` (registered in `config/settings/base.py` LOCAL_APPS
  after `nominations`; `anonymizer/awards.py` added — `register_skip(AwardType)`,
  catalog/non-PII; `anonymize_db --check_only` passes).
- `AwardType(TimeStampedModel)` in [awards/models.py](../../../thetatauCMT/awards/models.py)
  with every AWI-1 field. Design decisions:
  - `created`/`modified` via `core.models.TimeStampedModel` (the repo's timestamp
    mixin) in place of the generic `created_at`/`updated_at`.
  - `level`, `grant_method`, `recurrence`, `nominator_scope` as nested
    `models.TextChoices`. `nominator_scope` is a `MultiSelectField`
    (member/officer/national — an award may be nominated by several roles).
  - `category` = optional `CharField` (admin-managed free text) — simplest for the
    foundation; a lookup table can replace it later if needed.
  - `badge_image` = `ImageField(upload_to=awards/badges/…)` (Pillow is installed).
  - `points` nullable `IntegerField`; `single_winner` / `allow_multiple_winners` /
    `allow_multiple_nominations` / `is_active` booleans.
  - `single_winner` vs `allow_multiple_winners` kept as independent config flags —
    per-cycle winner ENFORCEMENT is deferred to AWI-2/AWI-5/AWI-7 (no `clean()`
    mutual-exclusivity added yet, to avoid pre-judging cycle semantics).
  - `objects = AwardTypeQuerySet.as_manager()` → `AwardType.objects.active()`
    (`is_active=True`) so retired awards are easily excluded from active lists.
- Migration `awards/0001_initial.py` generated, applied OK; `makemigrations --check`
  clean (EXITCODE 0).
- Admin: [awards/admin.py](../../../thetatauCMT/awards/admin.py) `AwardTypeAdmin`
  (list_display/list_filter/search_fields, `is_active` list-editable, fieldsets
  grouping grant config + cycle rules; `created`/`modified` read-only) — the
  admin-managed catalog UI.
- Tests: [awards/tests/test_models.py](../../../thetatauCMT/awards/tests/test_models.py)
  (7 tests) + `AwardTypeFactory` — covers all 4 acceptance criteria (all levels;
  grant_method + nominator_scope persist; retired excluded from active lists;
  badge/icon stored) plus `__str__` + defaults.
- **Full suite: 1915 passed, 17 skipped, 0 failed (~97s); flake8 + Django check clean.**
- **NEXT:** AWI-2 (Award cycles).

---

## AWI-2 — Award cycles

**Work item:** AwardCycle model and per-award cycle configuration. See **AwardCycle** table.

AwardCycle: name/label, period type (year / term / event), start/end (nullable for open), optional link to an event (reuse existing Events app if useful).

Relate AwardType <-> cycle behavior:
- recurring awards get a cycle per period; one-time awards may have a single/implicit cycle.
- enforce per-cycle rules configured on AwardType: single vs multiple winners; multiple nominations allowed vs not.

Deliver migrations first (pause), then admin + helper to resolve "current cycle" for an award.

**Tests:** cycle creation; single-winner enforcement per cycle; multiple-winner allowed when configured; current-cycle resolution.

**Status (2026-07-16) — DONE:**
- `AwardCycle(TimeStampedModel)` in [awards/models.py](../../../thetatauCMT/awards/models.py):
  `name`, `period_type` (`PeriodType` TextChoices year/term/event, default year),
  `start_date`/`end_date` (both nullable — blank end = open/ongoing), `event`
  (`FK events.Event`, `SET_NULL`, `related_name="award_cycles"`), + `created`/`modified`.
  `clean()` rejects end<start; `contains(date)` (open-ended bounds inclusive);
  `is_current` property. `AwardCycleQuerySet.active_on(date)` +
  `.current(on_date=None)` (active cycles, most-recent-start first). Migration
  `awards/0002_awardcycle.py` (depends on events + awards.0001) applied OK;
  `makemigrations --check` clean.
- Per-cycle RULES live on `AwardType` (methods only — NO schema change, AWI-1
  migration untouched): `winner_limit` (1 if single_winner else None),
  `can_add_winner(count)`, `can_add_nomination(count)`.
- Helpers in [awards/services.py](../../../thetatauCMT/awards/services.py):
  `resolve_current_cycle(on_date=None, period_type=None)` (current cycle, most
  recent start wins, optional period filter, None when none active);
  `check_winner_allowed(award_type, count)` +
  `check_nomination_allowed(award_type, count)` raise `ValidationError`
  (`SINGLE_WINNER_MSG` / `MULTIPLE_NOMINATION_MSG`) — the enforcement entry points
  AWI-5/AWI-7 will call with real `AwardGrant` counts (AWI-3).
- Admin: `AwardCycleAdmin` (list_display incl. boolean `is_current`, period_type
  filter, name search, `event` raw_id). `AwardCycleFactory` added.
  `anonymizer/awards.py` now `register_skip([AwardType, AwardCycle])`.
- Tests: [awards/tests/test_cycles.py](../../../thetatauCMT/awards/tests/test_cycles.py)
  (13) — cycle creation/open-ended/event-link/clean/contains; current-cycle
  resolution (active/open-ended/most-recent/period-filter/none); single-winner
  enforcement; multiple-winner allowed; multiple-nomination rule.
- **Full suite: 1928 passed, 17 skipped, 0 failed (~97s); flake8 + Django check +
  anonymize --check_only all clean.**
- Design note: no explicit AwardType→cycle FK (per spec — cycles are shared
  periods; `AwardGrant` will link award+cycle in AWI-3). "Current cycle for an
  award" = the active cycle by date (+ optional period_type). Winner enforcement
  is count-based now; grant-counting wires in at AWI-3.
- **NEXT:** AWI-3 (AwardGrant model + audit + backdating + revoke).

---

## AWI-3 — AwardGrant model + audit + backdating + revoke

**Work item:** AwardGrant polymorphic model with full history. See **AwardGrant** and **GrantAudit** tables.

Rules:
- Revoke/rescind sets status=revoked, retains the record and history (never hard-delete).
- Backdated grants use effective_date for display/reporting; granted_at remains the real timestamp.
- Exactly one recipient_* populated (enforce in clean() + DB constraint).
- If recipient is a group, create identical individual grants per member (per your note).
- Propose nullable-FKs vs generic relation and recommend.

Deliver migrations first (pause), then create/revoke services.

**Tests:** grant to member/chapter/region; backdated effective_date; revoke retains record + history; group grant creates one grant per member; audit entries written.

**Status (2026-07-16) — DONE:**
- **DECISION — recipient polymorphism: nullable FKs (NOT generic relation).**
  Recipient set is small/fixed (member/chapter/region); explicit FKs keep
  referential integrity, admin raw-id pickers, and simple joins/filtering.
- `AwardGrant(TimeStampedModel)` in [awards/models.py](../../../thetatauCMT/awards/models.py):
  `award_type`/`cycle` (`FK PROTECT`), `recipient_member`/`recipient_chapter`/
  `recipient_region` (nullable FKs, `PROTECT`, all `related_name="award_grants"`),
  `granted_by` (`PROTECT`), `granted_at` (real ts, default now), `effective_date`
  (`default=default_effective_date`=today, BACKDATE-able), `reason`, `status`
  (active/revoked), `source` (direct/nomination/import), `revoked_by`
  (`SET_NULL`)/`revoked_at`/`revoke_reason`, + created/modified.
  **DB `CheckConstraint awards_grant_exactly_one_recipient`** + `clean()` enforce
  exactly-one recipient. Helpers: `recipient`/`recipient_kind`/`recipient_display`,
  `is_active`/`is_revoked`. `AwardGrantQuerySet.active()/revoked()/for_cycle()`.
- `GrantAudit(models.Model)` append-only: `grant` (`CASCADE`,
  `related_name="audit_entries"`), `action` (created/revoked/imported/updated),
  `actor` (`SET_NULL`), `timestamp`, `detail` (`JSONField`). Chose a purpose-built
  audit table over simple_history (spec wants explicit action semantics).
- Migration `awards/0003_awardgrant_grantaudit_and_more.py` (deps chapters/users/
  regions/awards.0002) applied OK; `makemigrations --check` clean.
- Services [awards/services.py](../../../thetatauCMT/awards/services.py) (all
  atomic, never hard-delete): `grant_award(award, cycle, recipient, granted_by,
  *, effective_date=None, reason="", source=None)` (dispatches recipient type via
  `_recipient_kwargs`; writes created/imported audit); `grant_award_to_members(...)`
  (one grant per member for GROUP awards); `revoke_grant(grant, revoked_by,
  reason="")` (status=revoked + who/when/why + revoked audit; idempotent);
  `write_grant_audit(...)`; `count_active_winners(award, cycle)` (bridges AWI-2
  `check_winner_allowed` to real grants).
- Admin: `AwardGrantAdmin` (recipient col/filters/raw-id FKs, date_hierarchy) +
  read-only `GrantAuditInline` + `GrantAuditAdmin` (add/change disabled).
  `AwardGrantFactory` (defaults to member recipient). anonymizer:
  `register_skip([AwardType, AwardCycle, AwardGrant, GrantAudit])` (FK-only PII,
  awards are public).
- Tests: [awards/tests/test_grants.py](../../../thetatauCMT/awards/tests/test_grants.py)
  (19) — member/chapter/region grant, backdating (+granted_at stays now), revoke
  retains record + history, revoke idempotent, group→N grants, created/imported/
  revoked audit trail, exactly-one-recipient (clean + DB constraint reject 0/2),
  active/revoked querysets, winner-count + single-winner enforcement + scoping.
- **Full suite: 1947 passed, 17 skipped, 0 failed (~125s); flake8 + Django check +
  anonymize --check_only all clean.**
- Design notes: recipient FKs use `PROTECT` (not SET_NULL) to preserve history
  and avoid conflict with the exactly-one-recipient constraint (SET_NULL on the
  last recipient would violate it). Winner-rule ENFORCEMENT at grant time is
  wired in AWI-5 (grant_award stays a low-level creator; count helper is ready).
- **NEXT:** AWI-4 (Configurable eligibility engine).

---

## AWI-4 — Configurable eligibility engine

**Work item:** Configurable eligibility rules for AwardType (who is eligible to RECEIVE). See **EligibilityRule** table.

Build a config-driven eligibility system supporting rules such as:
- level/recipient-kind match (member vs chapter vs region)
- member status filters: active / alumni / PNM
- scope restrictions: specific chapter(s), specific region(s)
- extensible rule hooks (e.g., tenure, attendance) as pluggable checks — leave extension points, implement the status/scope rules now.

Expose a service: `get_eligible_recipients(award_type, cycle, actor)` -> queryset/list, respecting rules AND the actor's role scope. Also `is_eligible(award_type, recipient)`.

Deliver migrations first for rule config (pause), then the eligibility service.

**Tests:** active-only rule excludes alumni; chapter/region scoping; PNM eligibility; pluggable hook invoked; get_eligible_recipients respects actor role scope.

**Status (2026-07-16) — DONE:**
- `EligibilityRule(TimeStampedModel)` in [awards/models.py](../../../thetatauCMT/awards/models.py):
  `award_type` (`FK CASCADE`, `related_name="eligibility_rules"`), `rule_type`
  (`RuleType` TextChoices: member_status/chapter_scope/region_scope/recipient_kind/
  custom_hook), `member_status` (`MemberStatus` active/alumni/pnm, blank),
  `chapters`/`regions` M2M (`related_name="award_eligibility_rules"`), `hook_key`
  (blank), `params` (`JSONField`, default dict). Migration `awards/0004_eligibilityrule.py`
  (deps chapters/regions/awards.0003) applied OK; `makemigrations --check` clean.
- `AwardType.recipient_kind` property (level→kind; member/alumni/active/pnm/national
  →member, chapter→chapter, region→region) — pure method, NO schema change.
- Engine [awards/eligibility.py](../../../thetatauCMT/awards/eligibility.py):
  `get_eligible_recipients(award_type, cycle=None, actor=None)` → distinct queryset;
  `is_eligible(award_type, recipient, cycle=None, actor=None)` (kind-mismatch → False).
  Rules combine additively: recipient_kind guard (params["kind"]); member_status via
  `MEMBER_STATUS_FILTERS` (active=`core.ACTIVE_STATUSES`, alumni=[alumni,alumniCC],
  pnm=[pnm]) on `User.current_status`; chapter/region scope (member→chapter/region,
  chapter→pk/region, region→pk). **Actor role scope** via
  `core.models.user_is_national_officer` (natoff/superuser→all; RD via
  `director_regions`→their regions; else→`current_chapter`; region award + non-RD →
  none). **Pluggable hooks:** `register_eligibility_hook(key)` decorator +
  `get_eligibility_hook`; custom_hook rules call `hook(qs, award_type=, cycle=,
  actor=, params=)`; unknown key ignored. Extension point (no built-in hooks).
- Admin: `EligibilityRuleInline` (StackedInline, filter_horizontal chapters/regions)
  on `AwardTypeAdmin` + standalone `EligibilityRuleAdmin`. `EligibilityRuleFactory`
  (M2M set via `.chapters.set()`/`.regions.set()` in tests). anonymizer skips all 5.
- Tests: [awards/tests/test_eligibility.py](../../../thetatauCMT/awards/tests/test_eligibility.py)
  (16) — recipient_kind, no-rules-all-eligible, active-excludes-alumni, PNM,
  chapter/region scope (member + chapter/region awards), custom hook invoked/filters
  + unknown-key ignored, actor scope (chapter officer / RD / natoff), is_eligible +
  kind mismatch, recipient_kind guard.
- **Full suite: 1963 passed, 17 skipped, 0 failed (~105s); flake8 + Django check +
  anonymize --check_only all clean.** (Dev container's runserver autoreloader had
  crashed mid-edit on a transient broken admin.py — restarted the stack; a clean
  `manage.py check` confirmed the fix. GOTCHA: multi-edit that consumes a
  decorator/class-header line in oldString without re-adding it mangles structure.)
- **NEXT:** AWI-5 (Direct-grant path).

---

## AWI-5 — Direct-grant path

**Work item:** Direct grant flow for AwardTypes with grant_method=`direct`.

- View/action for authorized roles to grant a direct award: pick award (filtered to those the actor may grant), pick eligible recipient(s) (from AWI-4 service), set effective_date (allow backdating), reason.
- Enforce eligibility + single/multiple-winner cycle rules (AWI-2) at grant time.
- Creates AwardGrant(source=`direct`); triggers notifications (AWI-9) and certificate hook (AWI-8).

Gate by role: Admin/National Officer broad; Chapter Officer limited to their chapter scope; per nominator/grant scope config.

**Tests:** direct grant creates active grant; eligibility enforced; single-winner blocked when already granted in cycle; backdating works; role scoping enforced.

**Status (2026-07-16) — DONE (no new model/migration — view/form/service over existing models):**
- Signal [awards/signals.py](../../../thetatauCMT/awards/signals.py) `award_granted`
  (sender=AwardGrant, kwargs grant+actor) — the AWI-8 certificate / AWI-9
  notification EXTENSION POINT (no receivers yet).
- Service [awards/services.py](../../../thetatauCMT/awards/services.py):
  `direct_grant(award_type, cycle, recipient, granted_by, *, effective_date=None,
  reason="")` (atomic): rejects non-direct awards (`grant_method != direct`);
  enforces AWI-4 `is_eligible(..., actor=granted_by)` (eligibility + actor scope);
  enforces AWI-2 `check_winner_allowed(count_active_winners(...))`; creates
  `AwardGrant(source=direct)` via `grant_award`; fires `award_granted`.
  `can_grant_awards(user)` = any officer (natoff/superuser via
  `user_is_national_officer`, chapter-officer group, or RD via `director_regions`).
- Form [awards/forms.py](../../../thetatauCMT/awards/forms.py) `DirectGrantForm`:
  award (active + direct only), cycle (defaults to `resolve_current_cycle()`),
  recipient_member (DAL `users:autocomplete`, `chapter="false"`) + recipient_chapter/
  recipient_region dropdowns, effective_date (backdate), reason. `clean()` requires
  exactly the recipient field matching `award.recipient_kind`.
- View [awards/views.py](../../../thetatauCMT/awards/views.py) `DirectGrantView`
  (LoginRequired + `can_grant_awards` gate in dispatch → redirect home);
  `form_valid` calls `direct_grant`, maps `ValidationError` → form errors.
  URL `awards:direct_grant` (`/awards/grant/`) — new [awards/urls.py](../../../thetatauCMT/awards/urls.py)
  registered in [config/urls.py](../../../config/urls.py). Template
  [templates/awards/direct_grant_form.html](../../../thetatauCMT/templates/awards/direct_grant_form.html)
  (crispy + `{{ form.media }}` for DAL). No nav link yet (deferred).
- Tests: [awards/tests/test_direct_grant.py](../../../thetatauCMT/awards/tests/test_direct_grant.py)
  (14) — creates active grant; rejects non-direct; eligibility enforced; single-winner
  blocked (+ allowed in a different cycle); backdating; role scope (cross-chapter
  blocked, own-chapter ok); signal fires; `can_grant_awards` matrix; view gating
  (anon/ non-officer/ officer) + POST create + POST-ineligible re-render.
- **Full suite: 1977 passed, 17 skipped, 0 failed (~96s); flake8 + Django check clean.**
- GOTCHAS (view tests): `RMPSignMiddleware` bounces ANY authenticated user without a
  current RMP → sign one dated `semester_encompass_start_end_date()[0]` (avoids the
  Jun/Jul term-boundary flake). `RequireSuperuser2FAMiddleware` bounces superusers
  without 2FA → use a **natoff-GROUP** user (not `is_superuser`) for unrestricted-scope
  view actors. (Service-level tests bypass middleware, so superuser actors are fine there.)
- Design notes: `direct_grant` does NOT gate on officer status (that's the view via
  `can_grant_awards`); actor scope in `is_eligible` is the recipient-side enforcement.
  Winner enforcement per cycle now live (count_active_winners + check_winner_allowed).
  Notifications/certificates intentionally deferred to AWI-8/9 (signal is the hook).
- **NEXT:** AWI-6 (Nomination views, role-scoped).

---

## AWI-6 — Nomination views (role-scoped)

**Work item:** Nomination entry views scoped by role.

Three role-aware experiences using ONE shared view/template:
- Member: sees awards where nominator_scope includes members.
- Officer: sees a larger set (officer scope).
- National Officer: sees the largest set (national scope).

Behavior:
- After selecting an award, dynamically populate the eligible-recipient picker via AWI-4 `get_eligible_recipients` (respecting the award's restrictions AND the actor's scope). Do NOT expose non-eligible recipients.
- Nomination form fields: award, recipient (from eligible list), justification, optional supporting docs.
- Respect allow_multiple_nominations per award/cycle.

This view feeds AWI-7 (workflow) for nomination_workflow awards.

**Tests:** each role sees correct award list; recipient picker populated from eligibility; multi-nomination rule enforced; ineligible recipients never selectable.

**Status (2026-07-16) — DONE (also delivered the AWI-7 Process model + flow skeleton):**
- **`AwardNominationProcess(viewflow Process)`** in [awards/models.py](../../../thetatauCMT/awards/models.py)
  (migration `0005_awardnominationprocess`, MTI child of viewflow Process): award_type/
  cycle (`FK PROTECT`), polymorphic recipient_member/chapter/region (nullable FKs,
  `related_name="award_nominations"`), nominator (`PROTECT`), justification,
  supporting_docs (`FileField`), + AWI-7 fields result (approved/rejected)/reject_reason/
  resulting_grant (`FK AwardGrant SET_NULL`). recipient/recipient_kind/recipient_display
  helpers (same pattern as AwardGrant). NO DB constraint / model.clean (form validates —
  avoids viewflow save-order issues).
- **`AwardNominationFlow`** in [awards/flows.py](../../../thetatauCMT/awards/flows.py)
  (`@register_factory(FilterableFlowViewSet)`): `start=flow.Start(AwardNominationCreateView)`
  → `awaiting_review` (parked `flow.Function` placeholder, `@method_decorator(flow.flow_func)`)
  → `flow.End`. AWI-7 replaces awaiting_review with review→approve(grant)/reject.
  **GOTCHA: viewflow start URL = `viewflow:awards:awardnomination:start` — namespace is the
  FLOW class name minus "Flow" (NOT the process model name).**
- Services [awards/services.py](../../../thetatauCMT/awards/services.py):
  `allowed_nominator_scopes(actor)` (hierarchical: member→{member}; officer/RD→{member,officer};
  natoff/superuser→{member,officer,national}); `nominatable_award_types(actor)` (active
  nomination_workflow awards whose `nominator_scope` overlaps — Python-filters the
  MultiSelectField); `count_nominations_for(award,cycle,recipient)` (non-rejected, drives
  multi-nomination rule).
- Form [awards/forms.py](../../../thetatauCMT/awards/forms.py) `AwardNominationForm`
  (ModelForm): award_type queryset = `nominatable_award_types`; recipient_member DAL +
  chapter/region; justification + supporting_docs. `clean()` enforces recipient-kind match,
  `is_eligible(..., actor)` (AWI-4 eligibility + scope → "ineligible never selectable"),
  and `can_add_nomination(count_nominations_for(...))` (AWI-2 multi-nomination rule).
- Views [awards/views.py](../../../thetatauCMT/awards/views.py): `AwardNominationCreateView`
  (viewflow `CreateProcessView` Start; sets nominator=request.user; redirect home) +
  `EligibleRecipientsView` (JSON `awards:eligible_recipients` — powers the dynamic recipient
  picker from AWI-4, scoped to the actor). Template
  [award_nomination_form.html](../../../thetatauCMT/templates/awards/award_nomination_form.html)
  (extends account/base, `{{ activation.management_form }}` for viewflow).
  `AwardNominationProcessFactory` (flow_class set); anonymizer skips it (viewflow Process).
- Tests: [awards/tests/test_nomination_entry.py](../../../thetatauCMT/awards/tests/test_nomination_entry.py)
  (11) — role-scoped award list (member/officer/natoff hierarchy; direct awards excluded;
  out-of-scope rejected); eligible-recipients JSON endpoint (active in / alumni out; login
  required); ineligible recipient rejected + kind mismatch; multi-nomination blocked / allowed /
  rejected-doesn't-block; viewflow Start creates a process.
- **Full suite: 1988 passed, 17 skipped, 0 failed (~105s); flake8 + Django check +
  anonymize --check_only all clean.**
- Design notes: created the AWI-7 Process model NOW (AWI-6 needs storage); AWI-7 adds the
  approval nodes to the existing flow (no new model expected — result/reject_reason/
  resulting_grant already present). Dynamic picker = the JSON endpoint + server-side
  eligibility enforcement (DAL member widget shows all, server rejects ineligible).
- **NEXT:** AWI-7 (Nomination + approval Viewflow — flesh out the flow: config-driven
  approver, approve→`grant_award(source=nomination)`, reject→close).

---

## AWI-7 — Nomination + approval Viewflow

**Work item:** Nomination + approval workflow for AwardTypes with grant_method=`nomination_workflow`. Reuse the Volunteer Nomination Viewflow patterns. See **AwardNominationProcess** table.

Flow: nomination submitted (from AWI-6) -> review/approval node(s) assigned via config (approver depends on the award/level) -> approve -> creates AwardGrant(source=`nomination`) + triggers notifications/certificate; reject -> close with optional reason (retain record).
- Config-driven approver per award/level (mirror the volunteer StepAssignment approach).
- Support multiple nominations per recipient/cycle when allowed; enforce single/multiple-winner rules at approval.

Deliver Process model + migrations first (pause), then Flow class + nodes + review views.

**Tests:** nomination starts process; approver resolved from config; approve creates grant + fires notifications; reject retains record with reason; winner-count rules enforced at approval.

**Status (2026-07-16) — DONE:**
- Process model existed from AWI-6; AWI-7 added review-tracking fields
  `reviewed_by` (`FK User SET_NULL`)/`reviewed_at`/`review_notes` to
  `AwardNominationProcess` (migration `0006`). No other model change.
- **Config-driven approver** [awards/services.py](../../../thetatauCMT/awards/services.py):
  `get_award_approver(award_type)` resolves `AwardApprover:<level>` then `AwardApprover`
  from `configs.Config` (value = username/email OR NAT_OFFICERS role → current holder),
  falling back to `settings.EXECUTIVE_DIRECTOR` (mirrors the volunteer
  `_resolve_config_actor`/`get_reviewer_for`). `grant_from_nomination(nomination, approver)`
  (atomic): `grant_award(source=nomination)` + fires `award_granted` (AWI-8/9 hook).
- **Flow** [awards/flows.py](../../../thetatauCMT/awards/flows.py) — REPLACED the AWI-6
  parked placeholder: `start → review (View, `.Assign(get_award_approver)` `.Permission(
  auto_create=True)`) → check_result (If `nomination_approved`) → approve (Handler:
  result=approved, grant via `grant_from_nomination(reviewed_by)`, set resulting_grant) /
  reject (Handler: result=rejected) → End(approved)/End(rejected)`.
- Review [form](../../../thetatauCMT/awards/forms.py) `AwardNominationReviewForm`
  (result required approved/rejected + reject_reason/review_notes; `clean()` enforces
  **winner rules at approval** via `can_add_winner(count_active_winners)` → `WINNER_LIMIT_MSG`).
  [view](../../../thetatauCMT/awards/views.py) `AwardNominationReviewView(UpdateProcessView)`
  sets `reviewed_by`/`reviewed_at` in `form_valid` BEFORE the activation advances.
- Tests: [awards/tests/test_nomination_approval.py](../../../thetatauCMT/awards/tests/test_nomination_approval.py)
  (11) + [_flow_helpers.py](../../../thetatauCMT/awards/tests/_flow_helpers.py)
  (`start_award_nomination`/`active_task`/`complete_review`, mirrors nominations helpers) —
  starts+parks at review; approver from config (base/level-specific/role); approve→grant
  (source=nomination) + signal + End(approved); reject retains record+reason (no grant);
  winner rules enforced at approval; review-form decision required; grant_from_nomination.
- **Full suite: 1999 passed, 17 skipped, 0 failed (~110s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.**
- Design notes: winner enforcement lives in the review FORM (HTTP gate); handler trusts it.
  `reviewed_by` = the approver → grant `granted_by`; test path sets it via `complete_review`
  (bypasses the view). `.Permission(auto_create=True)` perm created on migrate; tests drive
  via activation (no perm check). Notifications/certificates still deferred to AWI-8/9 (the
  `award_granted` signal now fires for BOTH direct and nomination grants).
- **NEXT:** AWI-8 (Certificates / letters).

---

## AWI-8 — Certificates / letters

**Work item:** Certificate/letter generation and upload per grant. See **GrantArtifact** table.

- Support two modes per AwardType: auto-generate (from a template with recipient/award/cycle/date merge fields) and/or manual upload.
- Store the artifact on the AwardGrant; record generated/uploaded + timestamp.
- Provide download; include artifact link in notifications (AWI-9).

Deliver migrations (artifact fields/model) first (pause), then generation service + upload view. Follow any existing document-generation/upload pattern (e.g., appointment letters from the volunteer feature).

**Tests:** auto-generate produces a certificate with correct merge data; manual upload stored; artifact linked to grant; download works.

**Status (2026-07-16) — DONE:**
- `GrantArtifact` model in [awards/models.py](../../../thetatauCMT/awards/models.py):
  `grant` (`FK CASCADE`, `related_name="artifacts"`), `artifact_type`
  (generated/uploaded), `file` (`FileField` → `awards/certificates/`),
  `generated_at`/`uploaded_at` (nullable), `created_by` (`FK User SET_NULL`),
  `created_at` prop (whichever timestamp applies). Plus `AwardType.auto_generate_certificate`
  bool. Migration `0007` (add field + create model) applied OK.
- Certificate service [awards/certificates.py](../../../thetatauCMT/awards/certificates.py):
  `certificate_context(grant)` (recipient/award/cycle/date merge dict);
  `generate_certificate(grant, created_by)` → `easy_pdf.render_to_pdf("awards/certificate.html")`
  PDF stored as a `generated` artifact; `store_uploaded_artifact(grant, file, created_by)`
  → `uploaded` artifact; `maybe_generate_certificate` (best-effort, logs + swallows —
  never breaks the grant path). Template
  [templates/awards/certificate.html](../../../thetatauCMT/templates/awards/certificate.html).
- **Auto-generate hook:** [awards/receivers.py](../../../thetatauCMT/awards/receivers.py)
  `on_award_granted` connected to the `award_granted` signal in
  [apps.py](../../../thetatauCMT/awards/apps.py) `ready()` (dispatch_uid) — fires for BOTH
  direct (AWI-5) and nomination (AWI-7) grants; generates only when
  `award_type.auto_generate_certificate`.
- Views [awards/views.py](../../../thetatauCMT/awards/views.py): `GrantArtifactView`
  (officer-gated `can_grant_awards`; POST action=generate|upload) at
  `awards:grant_artifacts` + `GrantArtifactDownloadView` (`FileResponse`, LoginRequired) at
  `awards:artifact_download`. Template
  [grant_artifacts.html](../../../thetatauCMT/templates/awards/grant_artifacts.html).
  Admin: `GrantArtifactInline` on `AwardGrantAdmin` + standalone `GrantArtifactAdmin`;
  `auto_generate_certificate` on `AwardTypeAdmin`. anonymizer skips `GrantArtifact`.
- Tests: [awards/tests/test_certificates.py](../../../thetatauCMT/awards/tests/test_certificates.py)
  (10) — template merge (recipient/award/cycle/date via `render_to_string`); generate
  creates `generated` artifact (mock `render_to_pdf` → %PDF); upload stored + linked;
  auto-generate on grant when enabled / not when disabled / failure doesn't break grant;
  download serves file (+ login required); upload view stores + non-officer blocked.
- **Full suite: 2009 passed, 17 skipped, 0 failed (~107s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.**
- Design notes: PDF via `easy_pdf.render_to_pdf` (codebase pattern; tests MOCK it like the
  forms tests — needs static files otherwise). Merge-data tested via `render_to_string`
  (no PDF). generated_at/uploaded_at per the spec table (one set per type). The
  `award_granted` signal now drives BOTH notifications (AWI-9, pending) and certificates.
- **NEXT:** AWI-9 (notifications + announcements + monthly digest — connect to `award_granted`).

---

## AWI-9 — Notifications + announcements + monthly digest

**Work item:** Notifications and announcements for awards.

- Notify on NOMINATION (to approver/relevant officers) and on GRANT (to recipient + chapter officers as appropriate).
- Create a home-page ANNOUNCEMENT when an award is granted (reuse existing announcement/home-page mechanism if present; else propose).
- Monthly EMAIL DIGEST: a management command (run monthly) collecting the period's granted awards into one email to a configured audience.

Deliver notification hooks wired into AWI-5/AWI-7, announcement creation, and the digest command.

**Tests:** nomination + grant notifications fire; announcement created on grant; monthly digest aggregates correct period; digest idempotent/safe to re-run.

**Status (2026-07-16) — DONE:**
- `AwardDigestRun` model (migration `0008`): `period_start`/`period_end`
  (`UniqueConstraint awards_digest_unique_period` → idempotency), `sent_at`,
  `grant_count`, `sent_by`. Only new model.
- Herald notifications [awards/notifications.py](../../../thetatauCMT/awards/notifications.py):
  `AwardGrantedNotification` (to recipient + officers via
  `grant_notification_recipients` — member→emails+chapter `council_emails()`,
  chapter→council, region→directors+mailbox); `AwardNominationSubmittedNotification`
  (to config approver); `AwardDigestNotification` (list of grants). Templates in
  [templates/herald/html/](../../../thetatauCMT/templates/herald/html/) (award_granted /
  award_nomination_submitted / award_digest, extend base_email).
- Wiring (all best-effort, never break the grant/flow):
  - GRANT: [receivers.py](../../../thetatauCMT/awards/receivers.py) `notify_on_award_granted`
    connected to `award_granted` in [apps.py](../../../thetatauCMT/awards/apps.py) `ready()`
    (2nd dispatch_uid) → sends grant notification + creates a home-page `Announcement`
    ([awards/announcements.py](../../../thetatauCMT/awards/announcements.py)
    `create_grant_announcement`). Fires for direct (AWI-5) + nomination (AWI-7) grants,
    NOT imports (which don't send the signal).
  - NOMINATION: [flows.py](../../../thetatauCMT/awards/flows.py) NEW `notify_submitted`
    Handler node (start → notify_submitted → review) → emails the config approver
    (best-effort; no-op when approver unresolved).
- Digest [awards/digest.py](../../../thetatauCMT/awards/digest.py): `previous_month_period`/
  `month_period`, `grants_in_period` (active grants by `effective_date`),
  `digest_recipients` (Config `AwardDigestRecipients` → central office fallback),
  `send_award_digest(...)` (idempotent: skip if `AwardDigestRun` for the period exists
  unless `force`; `update_or_create` avoids duplicate run rows). Command
  [award_digest.py](../../../thetatauCMT/awards/management/commands/award_digest.py)
  (`--year/--month/--force/--dry-run/--day/--override`; day-of-month gate for daily
  scheduling → previous month).
- Admin `AwardDigestRunAdmin`; anonymizer skips `AwardDigestRun`.
- Tests: [awards/tests/test_notifications.py](../../../thetatauCMT/awards/tests/test_notifications.py)
  (13) — recipient helper (member/chapter/region); grant notification + announcement on
  direct grant; nomination notification to approver (+ none when unresolved); digest
  aggregates correct period; central-office fallback; idempotent (2nd run None, 1 email,
  1 run) + force re-sends; command sends / dry-run; previous_month_period. Uses `mailoutbox`.
- **Full suite: 2022 passed, 17 skipped, 0 failed (~104s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.**
- Design notes: `award_granted` receiver now does certificate (AWI-8) + notification +
  announcement, each best-effort. Announcement created per real-time grant (imports
  excluded — no signal). Digest keys off `effective_date` (backdated imports don't flood
  current digests). The notify_submitted Handler fires in BOTH HTTP + flow-helper paths.
- **NEXT:** AWI-10 (profile display + badges/icons).

---

## AWI-10 — Profile display + badges/icons

**Work item:** Display awards + badges on profiles and inline next to names.

- Member profile: list of that member's active awards (with badge/icon, cycle, date); show revoked separately or hidden per config.
- Chapter profile: chapter's awards similarly. Region awards on the region view.
- Inline name icons: render award/officer badge icons next to a member's name site-wide via a reusable template tag/component. Design it to ALSO support officer icons (from NAT_OFFICERS), since you want that too.
- All awards public.

Deliver reusable badge component/template tag + profile sections.

**Tests:** member/chapter/region awards render; badges shown; revoked handled per config; inline icon tag renders award + officer icons; performant (no N+1).

**Status (2026-07-16) — DONE:**
- **DECISION — inline name-icon supports BOTH awards + officer icons via a new
  configurable `OfficerBadge` model** (role `NAT_OFFICERS_CHOICES` unique,
  badge_image / icon_class / short_label / is_active; migration `0009`). Admin-managed
  so officer icons are configurable per national-officer role.
- Reusable template tags [awards/templatetags/award_tags.py](../../../thetatauCMT/awards/templatetags/award_tags.py):
  helpers `award_grants_for(recipient, revoked=False)` (member/chapter/region via
  isinstance → active/revoked queryset, select_related, **1 query**),
  `award_badge_types_for` (distinct award types with a badge_image),
  `officer_badges_for(user)` (active OfficerBadges matching `current_roles`, **1 query**;
  [] for non-members / no roles). Inclusion tags `{% inline_badges recipient %}`
  ([_inline_badges.html](../../../thetatauCMT/templates/awards/_inline_badges.html) —
  award badges + officer icons/imgs) and `{% awards_section recipient show_revoked= %}`
  ([_awards_section.html](../../../thetatauCMT/templates/awards/_awards_section.html) —
  Awards card, revoked section gated).
- `AWARDS_SHOW_REVOKED` setting (default False) → awards_section hides revoked unless
  configured or `show_revoked=True` passed.
- Integrated (all awards public): member profile
  [user_profile.html](../../../thetatauCMT/templates/users/user_profile.html)
  (`{% inline_badges object %}` by the name + Awards card), chapter
  [chapter_detail.html](../../../thetatauCMT/templates/chapters/chapter_detail.html) +
  region [region_detail.html](../../../thetatauCMT/templates/regions/region_detail.html)
  (Awards row). Admin `OfficerBadgeAdmin`; anonymizer skips `OfficerBadge`.
- Tests: [awards/tests/test_badges.py](../../../thetatauCMT/awards/tests/test_badges.py)
  (11) — member/chapter/region render; inline tag shows award badge img + officer icon;
  badge-types only-with-image; revoked hidden by default / shown when configured;
  officer badges active+matching-role only / excludes inactive / [] for non-member;
  no-N+1 (`django_assert_num_queries(1)` for grants + officer badges). Profile/chapter/
  region VIEW tests still pass (templates render).
- **Full suite: 2033 passed, 17 skipped, 0 failed (~103s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.**
- Design notes: officer icons via `OfficerBadge` (image OR icon_class OR label fallback).
  Inline tag = 2 queries/member (awards + officer badges); for big tables prefetch (single
  profile is fine). Revoked config = setting (per-call override via `show_revoked=`).
- **NEXT:** AWI-11 (public awards dashboard/directory).

---

## AWI-11 — Public awards dashboard

**Work item:** Public awards dashboard/directory.

- Browse/searchable directory of awards and winners: by award type, level, cycle/year, chapter, region.
- "All winners of X" and "winners in cycle Y" views.
- Public visibility (all awards public); respect revoked status.

Deliver dashboard views + filters.

**Tests:** filters by type/level/cycle/chapter/region; all-winners view correct; revoked excluded/labeled; public access.

### Status (2026-07-16) — DONE

- **Model/migration:** NONE. AWI-11 is a read-only public directory over the
  existing `AwardGrant` / `AwardType` / `AwardCycle`; `makemigrations --check`
  confirms no schema change. (Model-first analysis result: no persistent state.)
- **Filters** — `awards/filters.py` `AwardGrantFilter(DynamicScopeFilterSetMixin,
  FilterSet)`: `recipient` (free-text over member/chapter/region name),
  `award_type`, `level` (`award_type__level`), `cycle`, `chapter`, `region`.
  Chapter matches grants to that chapter AND to members of it; region matches the
  region, chapters in it, and members whose chapter is in it ("national" =
  no-narrow, "candidate_chapter" supported), mirroring the events directory.
- **Table** — `awards/tables.py` `AwardGrantTable`: award (→ type_winners),
  recipient (→ profile/chapter/region), kind, context chapter, context region,
  cycle (→ cycle_winners), effective_date, and a `status` column the view
  `exclude`s unless revoked are shown. Helpers `_context_chapter/_context_region/
  _recipient_url`.
- **Views** — `awards/views.py` (all PUBLIC, no `LoginRequiredMixin`, built on
  `core.views.PagedFilteredTableView`): `AwardDirectoryView` (base qs
  `AwardGrant.objects.active()` with select_related; `?show_revoked=1` widens to
  all + shows the status column), `AwardTypeWinnersView` ("all winners of X",
  `/directory/type/<pk>/`), `AwardCycleWinnersView` ("winners in cycle Y",
  `/directory/cycle/<pk>/`). Crispy `AwardDirectoryFilterHelper` in forms.py.
- **URLs** `awards:directory` `/directory/`, `awards:type_winners`,
  `awards:cycle_winners`. Template `templates/awards/award_directory.html`
  (`collapsible_filter` + `render_table` + show/hide-revoked toggle). Public nav
  link "Award Winners" added to `base.html` (visible to everyone).
- **Tests** — `awards/tests/test_directory.py` (14): public access; filter by
  type/level/cycle/chapter (both branches)/region (member/chapter/region
  recipients); type_winners + 404; cycle_winners; revoked excluded by default;
  revoked shown+labeled with `?show_revoked=1`; recipient search. Assert against
  `response.context["filter"].qs` (award/cycle/chapter names also appear in the
  filter `<select>` options, so raw-HTML matching gives false positives).
- **Full suite: 2047 passed, 17 skipped, 0 failed (~114s); flake8 + Django check
  + anonymize --check_only + makemigrations --check all clean.**
- **NEXT:** AWI-12 (reporting / exports CSV/Excel + member/chapter award history).

---

## AWI-12 — Reporting / exports + award history

**Work item:** Reports, exports, and award history.

- Reports/exports (CSV/Excel): awards by cycle, by chapter, by region; all winners of an award; per-member and per-chapter award history.
- Member award history view (chronological, includes backdated via effective_date; shows revoked).
- Respect role permissions for any non-public/administrative report if applicable (all award data is public, but exports may be officer-gated — propose).

Deliver report queries + export endpoints + history views.

**Tests:** each export returns correct rows; history ordered by effective_date; backdated + revoked handled; permission gating on exports.

### Status (2026-07-16) — DONE

- **Model/migration:** NONE. AWI-12 is read-only reporting/exports/history over the
  existing `AwardGrant`; `makemigrations --check` confirms no schema change.
- **Report queries** — `awards/reports.py`: `all_grants`, `awards_by_cycle`,
  `awards_by_award_type`, `awards_by_chapter` (chapter + its members),
  `awards_by_region` (region + its chapters + members in it), `member_award_history`
  / `chapter_award_history` (ordered by `effective_date` asc so backdated grants
  sort into place; include revoked by default). `include_revoked` flag; exports
  default active-only. select_related on all display relations.
- **Exports** — `awards/exports.py`: one `grant_row` (16 cols incl. status, source,
  granted_by, effective/granted/revoked dates, reason) feeds both
  `grants_csv_response` (stdlib csv) and `grants_xlsx_response` (openpyxl 3.0.10);
  `grants_export_response(fmt=)`. Timestamped filenames.
- **Export view** — `AwardExportView(LoginRequiredMixin, View)` at `awards:export`,
  officer-gated via `can_grant_awards` dispatch check (same gate as direct-grant /
  certificates — award data is public but bulk export needs an officer). One GET
  param selects the report: `cycle` / `chapter` / `region` / `award_type` /
  `member` (none = all); `?format=xlsx`; `?include_revoked=1`.
- **History views (PUBLIC)** — `MemberAwardHistoryView` (`/history/member/<username>/`),
  `ChapterAwardHistoryView` (`/history/chapter/<slug>/`) on `SingleTableView`,
  reuse `AwardGrantTable` with `order_by="effective_date"` and the status column
  shown (revoked labeled). `can_export` + `export_url` in context → officer-only
  CSV/Excel buttons. Template `award_history.html`. Officer export buttons also
  added to the AwardType/Cycle winner pages (`export_url` + `can_export`).
- **Integration** — `awards_section` tag now supplies `history_url` (member/chapter)
  and `_awards_section.html` shows a "View full award history →" link.
- **Tests** — `awards/tests/test_reports.py` (17): report queries (cycle/type/chapter/
  region, active-vs-revoked); member+chapter history ordering (backdated first,
  revoked included); CSV rows correct; XLSX workbook loads with rows; revoked
  excluded-by-default / included-on-request; export by chapter+member; gating
  (anonymous 302, non-officer 302, officer 200 CSV); public history views; history
  includes revoked; officer-only export buttons.
- **Full suite: 2064 passed, 17 skipped, 0 failed (~131s); flake8 + Django check
  + anonymize --check_only + makemigrations --check all clean.**
- **NEXT:** AWI-13 (legacy/historical bulk import + `AwardImportMatchQueueItem`).

---

## AWI-13 — Legacy / historical awards bulk import

**Work item:** Bulk import of historical award winners. See **AwardImportMatchQueueItem** table.

- CSV import mapping to award type, recipient (member/chapter/region), cycle/year, effective_date (backdated), source=`import`.
- Recipient matching: match members by ID/email/name (reuse the attendance national-upload matching approach, incl. an admin manual-match queue for low-confidence matches). Match chapters/regions by name/code.
- Idempotent (no duplicate grants on re-import); create missing cycles as needed or map to existing.
- Restricted to Admin.

Deliver import parser + matching + admin resolution UI (reuse existing match-queue pattern).

**Tests:** valid rows create backdated grants; low-confidence -> match queue; chapter/region matching; idempotent re-import; admin-only.

### Status (2026-07-16) — DONE

- **Model/migration:** `AwardImportMatchQueueItem` (migration `0010`) — mirrors the
  attendance `MatchQueueItem`: `upload_id`, `fingerprint` (idempotency), `recipient_kind`,
  raw fields (`raw_row` JSON + `raw_award`/`raw_recipient`/`raw_cycle`/`raw_effective_date`),
  resolved `award_type`/`cycle`/`effective_date`, `candidate_matches` JSON + `best_score`,
  `import_error`, `status` (pending/resolved/skipped), `resolved_recipient_member/chapter/region`,
  `resolved_grant`, `resolved_by`/`resolved_at`, `uploaded_by`. Methods `resolve_to` (creates the
  backdated import grant) / `skip` / `is_pending` / `display_label`.
- **Matching** — `awards/import_matching.py`: members reuse
  `attendance.matching.match_row` (id / email / fuzzy name); chapters & regions matched
  by name / slug (exact -> auto-accept, else ranked fuzzy candidates). Uniform
  `RecipientMatch(recipient, kind, score, auto_accept, candidates)`.
- **Importer** — `awards/importer.py` `ingest_award_csv`: reuses the attendance column
  aliases + adds award/cycle/region/recipient/effective_date; resolves the award (catalog
  must exist -> else error), creates missing cycles (4-digit = calendar-year), parses the
  backdated `effective_date`. Confident matches -> `import_grant` (idempotent on
  award/cycle/recipient, `source=import`, bypasses eligibility/winner rules); low-confidence
  -> queue (idempotent via `fingerprint`; already-resolved fingerprints skipped). `ImportResult`
  counts imported/duplicates/queued/skipped/errors.
- **Admin UI** — `AwardImportUploadView` (`/import/`), `AwardImportQueueListView`
  (`/import/queue/`), `AwardImportQueueResolveView` (`/import/queue/resolve/`) gated by a new
  `AdminRequiredMixin` (`is_staff`; authed non-staff -> home, anon -> login). Templates
  `import_upload.html` + `import_queue.html` (candidate confirm / skip). Staff nav link
  "Import Awards". `AwardImportMatchQueueItemAdmin`. Management command `import_awards <csv>
  --user`.
- **Anonymizer** — `AwardImportMatchQueueItem` `register_clean` (raw PII, transient) like the
  attendance queue.
- **Tests** — `awards/tests/test_import.py` (15): valid member row -> backdated import grant;
  email match; missing cycle created; award-not-found error; chapter + region exact match;
  low-confidence member -> queue with candidates; resolve creates grant; skip; idempotent
  re-import (duplicate, single grant); re-import after resolution skipped; admin-only (upload +
  queue: anon 302 / non-staff 302 / staff 200); staff upload ingests; resolve view creates grant.
- **Full suite: 2079 passed, 17 skipped, 0 failed (~114s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.**
- **NEXT:** AWI-14 (simulated/seed data command `seed_awards_demo`).

---

## AWI-14 — Simulated/seed data for QA

**Work item:** Create a repeatable way to populate the database with realistic simulated Awards data so the entire feature can be QA'd end-to-end.

Deliver a Django management command (e.g., `seed_awards_demo`) that generates coherent, cross-referenced sample data covering every path in AWI-1…AWI-13. Follow existing seed/factory patterns in the codebase (reuse factories/fixtures if they already exist; otherwise use factory_boy or plain ORM creation consistent with the repo).

**Command requirements:**
- Idempotent and safe to re-run: support `--flush-awards` to clear only Awards-domain data before seeding (do NOT touch unrelated tables).
- Deterministic option: accept `--seed <int>` so runs are reproducible for QA.
- Scalable: accept `--scale <small|medium|large>` (or count flags) to control volume.
- Reuse EXISTING members, chapters, and regions where present; only create the minimum supporting records needed if the environment is empty (clearly flagged/tagged as demo data, e.g., a name prefix like `[DEMO]`).
- Do not run automatically in production; guard with a settings/DEBUG check or explicit `--force`.

**Data coverage (must exercise all features):**
- **AwardTypes** across every level (member, chapter, region, alumni, active, PNM, national), with a mix of `grant_method` (`direct` and `nomination_workflow`), `recurrence` (`one_time` and `recurring`), single- vs multiple-winner, and multi-nomination allowed vs not. Include at least one retired/inactive award.
- **AwardCycles** of each period type (year, term, event) including a past cycle, a current cycle, and an event-linked cycle.
- **EligibilityRules** exercising member_status (active/alumni/PNM), chapter_scope, region_scope, and at least one custom_hook stub.
- **AwardGrants** with a mix of recipients (member, chapter, region), including: active grants, at least one backdated grant (past effective_date), at least one revoked grant, and each `source` value (`direct`, `nomination`, `import`). Include a group-grant example that produced multiple individual member grants.
- **AwardNominationProcess** instances in varied states: pending/in-review, approved (with resulting AwardGrant), and rejected (with reason) — enough to see the Viewflow inbox/tasks populated for the configured approvers.
- **GrantArtifacts:** at least one auto-generated certificate and one uploaded certificate.
- **Config-driven approver assignments** set so nomination workflows route to real seeded/existing users, enabling QA of the reviewer queue.
- Enough data to make the **public awards dashboard**, **profile badges/inline name icons**, **reporting/exports**, and the **monthly digest** visibly meaningful (multiple winners across chapters/regions/cycles).

**Deliverables:** the management command + any supporting factories/fixtures, plus a short `docs/specs/awards-qa-seed.md` note listing what gets created, the flags, and a suggested QA walkthrough per feature area.

**Tests:**
- Command runs cleanly on an empty DB and on a DB with existing members/chapters/regions.
- `--seed` produces reproducible output; re-running with `--flush-awards` yields a clean, consistent dataset (no duplicates, no orphans).
- Seeded data satisfies model constraints (exactly one recipient per grant, valid eligibility, winner-count rules) and every AWI feature area has at least one representative record.
- Command refuses to run in production without `--force`.

### Status (2026-07-16) — DONE

- **No model/migration** — a management command only.
- **Command** `awards/management/commands/seed_awards_demo.py`: flags `--flush-awards`
  (deletes ONLY `[DEMO] ` awards rows — never members/chapters/regions or non-demo
  awards), `--seed` (random + Faker), `--scale small|medium|large`, `--force`
  (required when `settings.DEBUG` is off). Wrapped in one `transaction.atomic`.
- **Coverage** — 8 AwardTypes (every level; direct + nomination; one_time + recurring;
  single/multi winner; multi-nomination; one retired). 5 cycles (year/term/event; past +
  current). 6 EligibilityRules (member_status active/alumni/PNM, chapter_scope,
  region_scope, custom_hook stub). Grants of every source (`direct` via grant_award +
  a real `direct_grant` call, `nomination` from the driven flow, `import` via
  `import_grant`), every recipient kind, backdated + revoked + a group grant.
  Nominations pending/approved(→grant)/rejected via the viewflow flow (Config
  `AwardApprover` set to a demo approver so the reviewer queue populates). 1 generated +
  1 uploaded GrantArtifact. 2 OfficerBadges + the approver given a national-officer role.
- **Idempotency** — catalog `get_or_create`; grants existence-checked; artifacts gated
  on demo-artifact existence; nominations created only up to the target count. Re-run
  (no flush) and `--flush-awards` reseed both yield identical structure.
- **Reuse** — reuses existing members/chapters/regions; creates minimal `[DEMO]`
  supporting records (region + chapters + members + approver) only when empty.
- **Deliverables** — command + `docs/specs/awards-qa-seed.md` (flags, what's created,
  per-feature QA walkthrough).
- **Tests** — `awards/tests/test_seed_demo.py` (6): full coverage + constraints
  (exactly-one-recipient, single-winner) on an empty DB; reuses existing members;
  idempotent re-run; `--flush-awards` consistent reseed (no dupes/orphans, stable member
  set); flush preserves supporting + non-demo data; refuses without `--force`.
- **Full suite: 2085 passed, 17 skipped, 0 failed (~114s); flake8 + Django check +
  anonymize --check_only + makemigrations --check all clean.** Manually smoke-tested the
  command against the dev DB (seed → idempotent re-run → flush reseed).
- **DONE — the Awards feature (AWI-1 … AWI-14) is complete.**

---

## Build Order & Dependencies

- **AWI-1 → AWI-2 → AWI-3 → AWI-4** are the foundation (catalog, cycles, grants, eligibility). Build these first, in order.
- **AWI-5** (direct) and **AWI-6 → AWI-7** (nomination/workflow) are the two grant paths; both depend on 1–4.
- **AWI-8 / AWI-9** (certificates, notifications) plug into both grant paths.
- **AWI-10 / AWI-11 / AWI-12** are display/reporting; build after grants exist.
- **AWI-13** (import) depends on the full grant + eligibility + cycle model and reuses the attendance match-queue pattern.
- **AWI-14** simulated data to help start QA review and testing.

### Open decisions to confirm before starting

1. **Recipient polymorphism (AWI-3):** nullable FKs (Member/Chapter/Region) vs. a generic relation. Copilot will propose and recommend based on the codebase — override here if you have a preference.
2. **Inline name-icon scope (AWI-10):** currently baked in as a reusable component supporting both awards and `NAT_OFFICERS` officer icons. Split into a separate feature if preferred.

---

## Final Review (2026-07-17)

Full audit of AWI-1 … AWI-14 for completeness, testing, sample data, and code reuse.

**Functionality & tests** — every work item has a dedicated test module (`test_models`,
`test_cycles`, `test_grants`, `test_eligibility`, `test_direct_grant`, `test_nomination_entry`,
`test_nomination_approval`, `test_certificates`, `test_notifications`, `test_badges`,
`test_directory`, `test_reports`, `test_import`, `test_seed_demo`). **Full suite: 2085 passed,
17 skipped, 0 failed.** flake8, Django `check`, `anonymize_db --check_only`, and
`makemigrations --check` (awards) all clean.

**Sample data** — `seed_awards_demo` verified end-to-end; the dev DB holds a coherent demo
dataset (8 award types, 16 grants across all sources/recipient kinds, 3 nominations, 2 certificates).

**De-duplication fixes (this review):**
- `_resolve_config_actor` was **verbatim-duplicated** in `awards/services.py` and
  `nominations/models.py` → extracted to a single **`core.models.resolve_config_actor`**; both
  approver resolvers (`get_award_approver`, `get_reviewer_for`) now reuse it.
- The awards CSV importer re-implemented `parse_rows` / `_canonical_header` → the attendance
  uploader's versions were **parametrized** (`aliases=`, backward-compatible) and the awards
  importer now **reuses** them.
- The `_sign_rmp` test helper (duplicated in 5 award test modules) → shared
  `awards/tests/_helpers.py::sign_rmp`.

**Reuse verified (already correct):** `services._recipient_kwargs` (→ importer, model
`resolve_to`), `tables._context_chapter/_context_region` (→ exports), `attendance.matching.match_row`
+ `COLUMN_ALIASES` (→ importer), `chapter.council_emails()` (→ notifications),
`PagedFilteredTableView` + `DynamicScopeFilterSetMixin` (→ directory), `easy_pdf.render_to_pdf`
(→ certificates), django-herald, viewflow flow patterns, and `semester_encompass_start_end_date`.

**Noted, left as-is (pre-existing codebase convention, not awards-introduced):**
`CENTRAL_OFFICE_EMAIL` is defined identically in the `jobs`, `nominations`, and `awards`
notification modules; awards follows the sibling pattern. Consolidating it is a codebase-wide
change outside the awards scope.

**Note:** an unrelated attendance test (`test_cross_chapter_guest_attendance_recorded`) can flake
under non-deterministic `xdist` worker distribution (a `chapter_factory` Greek-name collision);
it passes in isolation and on suite re-run, and is independent of the awards work.
