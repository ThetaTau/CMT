# Feature Inventory — TWI-1 deliverable

> **Status:** reviewed and signed off. All Section A findings are **resolved** — see each finding for
> the ruling and what changed in code. Safe to author the TWI-8 fixture from this document.
>
> **Source of truth for the work this feeds:** [.github/copilot-memory/sessions/catalog-tours.md](../../.github/copilot-memory/sessions/catalog-tours.md)
> **Blocks:** TWI-8 (registry fixture).

## Method

Every named route was enumerated from [config/urls.py](../../config/urls.py) plus the 21 app-level
`urls.py` modules. Audience was determined by **reading the view class declaration** in each app's
`views.py`, not by inferring from the URL prefix or the app name — a distinction that mattered (see
A-1). Where gating lives in a `dispatch()` override or inside `get_queryset()` rather than a mixin, the
view body was read.

## Column definitions

| Column | Meaning |
|---|---|
| **Name** | Catalog display name — user-facing language, not the view class name |
| **URL name** | Reversible name, including namespace |
| **kwargs** | `—` = none; `@token` = dynamic, resolved per-viewer by `resolve_feature_url` |
| **Actual audience** | What the code enforces *today* |
| **Catalog audience** | What the registry entry should say. Differs from *actual* only where Section A explains why |
| **Duty roles** | `Feature.roles` — guidance targeting only, never access control. `—` = not role-specific |
| **Flag** | `Config` feature flag key, if any |
| **Verdict** | `INCLUDE`, or `EXCLUDE — reason` |

Audience values are the 4-value enum from the plan: `public | member | officer | natoff`.

## Summary

| | Count |
|---|---|
| Named routes examined | ~205 |
| **INCLUDE** as catalog features | **118** |
| EXCLUDE — internal/technical (autocomplete, AJAX, OAuth, webhook, redirect) | ~52 |
| EXCLUDE — sub-step of an included feature (multi-page wizards, PDF renders, CSV endpoints) | ~24 |
| EXCLUDE — superuser-only internal tooling (resolved decision #6) | 8 |
| EXCLUDE — token-addressed, not linkable | 3 |
| Feature areas | 16 (0–15) |
| RoleGuides | 9 |

---

# Section A — Findings and rulings

These are the reasons this task could not be done mechanically. All six are now resolved.

### A-1. Four `users` views are public. An earlier automated pass called them `natoff`. ✅ corrected

[thetatauCMT/users/views.py](../../thetatauCMT/users/views.py) — `UserBadgeLookupView` (line 877),
`UserLookupSearchView` (932), `UserLookupSelectView` (982), and `UserLookupUpdateView` (1021) are all
plain `FormView` with **no mixin**. They are the "update member info without logging in" flow the owner
named in resolved decision #4, and they are the backbone of the `getting-in` area. Already corrected in
the plan; recorded here because it is the strongest argument for reviewing this document by hand.

### A-2. Award directory was public — **ruled member-only, now fixed** ✅

[core/views.py](../../core/views.py) line 156: `class PagedFilteredTableView(SingleTableView)` has no
`LoginRequiredMixin`. `AwardDirectoryView`, `AwardTypeWinnersView`, `AwardCycleWinnersView`,
`MemberAwardHistoryView`, and `ChapterAwardHistoryView` therefore inherited **no** login requirement,
and [thetatauCMT/templates/base.html](../../thetatauCMT/templates/base.html) linked **Award Winners** in
the anonymous navbar.

> **Ruling:** the public surface is login help only. Award data is for signed-in members.
>
> **Changed in code:** `AwardDirectoryView` and `_AwardHistoryView` now carry `LoginRequiredMixin`
> (their two subclasses each inherit it), the anonymous *Award Winners* nav link was removed, and the
> "public" docstrings were corrected. Tests updated in `awards/tests/test_directory.py` and
> `test_reports.py`. **`forms:pledgeform` stays public** — a prospective new member has no account yet,
> so that link must remain in the anonymous nav.

### A-3. `BillOfRightsDetailView` is public — **ruled intentional** ✅

[thetatauCMT/forms/views.py](../../thetatauCMT/forms/views.py) line 1418:
`class BillOfRightsDetailView(DetailView)` — no mixin, takes `<int:pk>` of a **Chapter**, renders that
chapter's region and the names of its regional directors. `BillOfRightsPDFView` inherits it.

> **Ruling:** public access is fine here. No code change. Catalogued as `member` because that is who
> needs to find it, but nothing enforces or needs to enforce a login.

### A-4. `users:update_review` has no access mixin — **ruled intentional** ✅

[thetatauCMT/users/views.py](../../thetatauCMT/users/views.py) line 1124:
`class UserUpdateDirectReview(UpdateView)` on `MemberUpdate` with `<int:pk>`. Reached from an emailed
link, so National Officers can action a member-update request without signing in first.

> **Ruling:** public access is fine here. No code change. `EXCLUDE` from the catalog regardless — it is
> a workflow landing page, not a discoverable feature.

### A-5. Two impersonation-aware views deliberately bypass the hide-natoff toggle

`UserAlterView` and `ToggleNatoffView` both override the check to use **raw** `in_national_officer_group`
rather than the toggle-aware property, and say so in comments — otherwise a National Officer who hid
national functionality could never unhide it.

**Implication for TWI-3:** these two are the *only* legitimate uses of `in_national_officer_group`. The
visibility service must not copy this pattern. Both are `EXCLUDE`d from the catalog (account-menu
controls, not features), but the Role Guide copy for national officers should mention the toggle exists.

### A-6. The `officer` audience is broader than "chapter officer"

`OfficerRequiredMixin.group_required = ["officer", "natoff"]`, and `core.views.group_required` also
returns `True` for **any superuser**. So `officer` in the catalog means "officer group, natoff group, or
superuser." Documented so nobody later writes a narrower test in `guides/services.py` and quietly
changes who can see what.

---

# Section B — Area-by-area inventory

## Area 0 — `getting-in` · audience `public`

The only area rendered to signed-out visitors. Everything here answers "I cannot get into my account."

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Sign in | `account_login` | — | public | public | — | — | INCLUDE |
| Find my username or badge number | `users:badge_lookup` | — | public | public | — | — | INCLUDE |
| Reset my password | `password_reset` | — | public | public | — | — | INCLUDE |
| Update my info without signing in | `update_lookup` | — | public | public | — | — | INCLUDE — canonical entry; redirects to `users:lookup_search` |
| Two-factor sign-in | *(`allauth_2fa`)* | — | public | public | — | — | EXCLUDE — sub-step of sign-in |

**Excluded sub-steps** (each is a stage of an included flow, not separately discoverable):
`users:lookup_search`, `users:lookup_select`, `users:update`, `password_reset_done`,
`password_reset_confirm`, `password_reset_complete`, `account_logout`, all `allauth_2fa` routes, and
`account_signup` (`ACCOUNT_ALLOW_REGISTRATION = False` — registration is off).

## Area 1 — `getting-started` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Home dashboard | `home` | — | member | member | — | — | INCLUDE |
| My profile | `users:profile` | `@username` | member | member | — | — | INCLUDE |
| Edit my info | `users:detail` | — | member | member | — | — | INCLUDE |
| My profile picture | `users:profile_picture` | — | member | member | — | — | INCLUDE |
| Email preferences / unsubscribe | `users:unsubscribe` | token | public | member | — | — | INCLUDE — describe the concept; token URL is not linkable (see note) |
| Terms of service (EULA) | `eula` | — | public | member | — | — | INCLUDE |
| Electronic business terms | `electronic_terms` | — | public | member | — | — | INCLUDE |
| Privacy notice | `privacy` | — | public | member | — | — | INCLUDE |
| About | `about` | — | public | member | — | — | INCLUDE |

> The unsubscribe entry must render as a **non-linked card** — its token is per-user and per-category and
> cannot be reversed generically. `resolve_feature_url` returns `None`; this is exactly the
> "unresolvable link" case the plan requires to degrade gracefully.

**Excluded:** `users:redirect`, `users:user_verify` (AJAX), `users:sync_email_provider`,
the `allauth_2fa` setup/backup-token/remove routes (sub-steps of security setup — consider one
"Two-factor authentication" concept card in a later pass), `help` (this *is* the help hub — TWI-10).

## Area 2 — `my-chapter` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter home | `chapters:detail` | `@chapter_slug` | member | member | — | — | INCLUDE |
| Chapter activity | `chapters:activity` | `@chapter_slug` | member | member | — | — | INCLUDE |
| Chapter audit view | `chapters:audit` | `@chapter_slug` | member | member | treasurer | — | INCLUDE |
| Chapter directory | `chapters:list` | — | member | member | — | — | INCLUDE |
| Chapter scores | `scores:list` | — | member | member | regent | — | INCLUDE |
| Score detail | `scores:detail` | slug | member | member | — | — | INCLUDE |
| Chapter notes | `notes:add` | `@chapter_slug` | natoff | natoff | — | — | INCLUDE |
| Note detail | `notes:detail` | pk | member | member | — | — | EXCLUDE — reached from chapter home, not independently |
| Member notes | `notes:add_user` | `@username` | natoff | natoff | — | — | INCLUDE |

**Excluded:** `chapters:redirect`, `chapters:activity_redirect`, `chapters:audit_redirect`,
`scores:redirect` — all `RedirectView` shims.

## Area 3 — `roster-members` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter roster | `users:list` | — | member | member | scribe | — | INCLUDE |
| Enter member GPAs | `users:gpas` | — | officer | officer | scribe | — | INCLUDE |
| Enter service hours | `users:service` | — | member | member | scribe | — | INCLUDE |
| External organizations | `users:orgs` | — | member | member | — | — | INCLUDE |
| Log external org participation | `users:orgs_add` | — | member | member | — | — | INCLUDE |
| Member search (all chapters) | `users:search` | — | natoff | natoff | — | — | INCLUDE |
| Member info (any member) | `users:info` | `@username` | member | member | — | — | EXCLUDE — duplicate of `users:profile` |
| Switch chapter / role | `users:alterchapter` | — | natoff | natoff | — | — | EXCLUDE — account-menu control (see A-5) |

**Excluded:** `users:orgs_delete` (row action), `users:org-autocomplete`, `users:autocomplete`,
`users:toggle_natoff` (A-5), `users:toggle_admin` (A-5), `users:update_review` (A-4).

## Area 4 — `events-attendance` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter events | `events:list` | — | member | member | vice regent | — | INCLUDE |
| Add an event | `events:add` | — | member | member | vice regent | — | INCLUDE |
| Copy an event | `events:copy` | pk | member | member | vice regent | — | EXCLUDE — row action on the events list |
| Event detail | `events:detail` | date+slug | member | member | — | — | EXCLUDE — reached from the list |
| Edit / delete an event | `events:update` / `events:delete` | date+slug | member | member | vice regent | — | EXCLUDE — row actions |
| Events calendar | `events:calendar` | — | member | member | — | `FEATURE_EVENTS_CALENDAR` | INCLUDE |
| Calendar subscriptions | `events:feeds` | — | member | member | — | `FEATURE_EVENTS_CALENDAR` | INCLUDE |
| Subscribe to a chapter's calendar | `events:feed_subscribe_chapter` | — | member | member | — | `FEATURE_EVENTS_CALENDAR` | INCLUDE |
| Add my tasks to my calendar | `events:feed_tasks` | — | member | member | — | `FEATURE_EVENTS_CALENDAR` | INCLUDE |
| All events (all chapters) | `events:list_all` | — | natoff | natoff | — | — | INCLUDE |
| Pending event reviews | `events:pending` | — | natoff | natoff | — | — | INCLUDE |
| Take attendance | `attendance:roster` | date+slug | member¹ | member | vice regent, scribe | — | INCLUDE |
| Add a guest to attendance | `attendance:guest_add` | date+slug | member¹ | member | vice regent | — | EXCLUDE — action within the roster |
| Attendance rollup | `attendance:rollup` | date+slug | member¹ | member | — | — | EXCLUDE — action within the roster |
| RSVP for an event | `attendance:rsvp` | date+slug | member | member | — | — | INCLUDE |
| Log my own attendance | `attendance:member_add` | `@username` | member | member | — | — | INCLUDE |
| Upload national attendance | `attendance:national_upload` | — | natoff | natoff | — | — | INCLUDE |
| National attendance match queue | `attendance:match_queue` | — | natoff | natoff | — | — | INCLUDE |

¹ `AttendancePermissionMixin(LoginRequiredMixin)` — login plus a per-event `can_record_attendance`
check. Correctly modelled as `member` audience with role guidance, not as `officer`.

**Excluded:** `events:approve` / `events:reject` (row actions on Pending), `events:redirect`,
`events:ical` / `events:ical_national` (feed endpoints — the *subscription* pages are the features),
`attendance:save` / `attendance:bulk_update` / `attendance:match_queue_resolve` (form POST targets),
and 5 autocompletes.

## Area 5 — `tasks-goals` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter tasks | `tasks:list` | — | member | member | all chapter officers | — | INCLUDE |
| Task detail | `tasks:detail` | pk | member | member | — | — | EXCLUDE — reached from the list |
| Mark a task complete | `tasks:complete` | pk | officer | officer | all chapter officers | — | EXCLUDE — row action |
| Chapter goals | `objectives:list` | — | member | member | regent | — | INCLUDE |
| Set a goal | `objectives:create` | — | member | member | regent | — | INCLUDE |
| Goal detail | `objectives:detail` | pk | member | member | — | — | EXCLUDE — reached from the list |
| Submissions | `submissions:list` | — | member | member | — | — | INCLUDE |
| Add a submission | `submissions:add` | — | member | member | — | — | INCLUDE |
| Submit for a specific score | `submissions:add-direct` | ScoreType slug | member | member | — | — | INCLUDE — **static** kwarg, one entry per score type |

**Excluded:** `submissions:redirect`, `submissions:update`, `submissions:detail`.

> `tasks:list` is the join point for **TWI-12**. `Task.owner` already uses `ALL_ROLES_CHOICES`, so every
> RoleGuide gets live rows from this area with no new data.

## Area 6 — `forms-workflows` · audience `member` · **largest area, needs sub-grouping (TWI-9b)**

Sub-groups below are the proposed TWI-9b grouping, not model fields.

### 6a. Membership changes

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Initiation report | `forms:init_selection` | — | member | member | scribe, regent | — | INCLUDE |
| Pledge / new member form | `forms:pledgeform` | — | public | member | — | — | INCLUDE (see A-2) |
| Pledge form (alternate) | `forms:pledgeform-alt` | — | public | member | — | — | EXCLUDE — variant of the above |
| Status change history | `forms:status_history` | reason | officer | officer | scribe | — | INCLUDE — one entry per reason |
| Submit a status change | `forms:status_new` | reason | officer | officer | scribe | — | INCLUDE — one entry per reason |
| Graduate members | `forms:status_graduate_select` | — | officer | officer | scribe | — | INCLUDE |
| Premature alumnus | `viewflow:forms:prematurealumnus:start` | — | member | member | scribe | — | INCLUDE |
| Return student | `viewflow:forms:returnstudent:start` | — | member | member | scribe | — | INCLUDE |
| Resignation | `viewflow:forms:resignation:start` | — | member | member | — | — | INCLUDE |
| Resignations list | `forms:resign_list` | — | officer | officer | — | — | INCLUDE |
| Alumni exclusion | `viewflow:forms:alumniexclusion:start` | — | member | member | — | — | INCLUDE |
| All alumni exclusions | `forms:alumniexclusion_list` | — | natoff | natoff | — | — | INCLUDE |
| Depledge survey | `surveys:depledge` | `@username` | public | member | — | — | INCLUDE — see Area 15 |

### 6b. Officer & chapter administration

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter officers | `forms:officer` | — | member | member | regent | — | INCLUDE |
| Submit chapter officers | `forms:officer_add` | — | officer | officer | regent | — | INCLUDE — **the Role Guide's highest-leverage entry point** |
| National officers directory | `forms:natoff` | — | member | member | — | — | INCLUDE |
| Chapter bylaws | `forms:bylaws` | — | member | member | regent, scribe | — | INCLUDE |
| All bylaws | `forms:bylaws_list` | — | natoff | natoff | — | — | INCLUDE |
| Roll book page | `forms:roll_book_page` | pk | officer | officer | scribe | — | INCLUDE |
| Ritual proficiency | `forms:ritual_proficiency` | — | natoff | natoff | — | — | INCLUDE |
| Convention form | `conventionform` | — | member | member | regent | — | INCLUDE |
| All convention forms | `forms:convention_list` | — | natoff | natoff | — | — | INCLUDE |
| Outstanding student member (OSM) | `osmform` | — | member | member | regent | — | INCLUDE |
| All OSM forms | `forms:osm_list` | — | natoff | natoff | — | — | INCLUDE |
| Forms landing | `forms:landing` | — | member | member | — | — | EXCLUDE — this *is* the area page (TWI-9b) |

### 6c. Risk & compliance

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Risk management policies (RMP) | `forms:rmp` | — | member | member | risk management chair, regent | — | INCLUDE — **required of every member; RMPSignMiddleware enforces it** |
| All RMP signatures | `forms:rmp_list` | — | natoff | natoff | — | — | INCLUDE |
| Health & safety education program | `viewflow:forms:hseducation:start` | — | member | member | risk management chair | — | INCLUDE |
| All H&S education reports | `forms:education_list` | — | natoff | natoff | — | — | INCLUDE |
| New member education program | `viewflow:forms:pledgeprogramprocess:start` | — | member | member | pledge/new member educator | — | INCLUDE |
| All NME programs | `forms:pledge_program_list` | — | natoff | natoff | — | — | INCLUDE |
| Disciplinary process | `viewflow:forms:disciplinaryprocess:start` | — | officer | officer | regent | — | INCLUDE |
| Bill of rights | `forms:bill_of_rights` | pk | public | member | — | — | INCLUDE — see **A-3** |

### 6d. Money

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter audit form | `forms:audit` | — | officer | officer | treasurer | — | INCLUDE |
| All audits | `forms:audit_list` | — | natoff | natoff | — | — | INCLUDE |
| Collection referral | `forms:collection` | — | officer | officer | treasurer | — | INCLUDE |
| Pledge pins (store) | `forms:pledge_pins` | — | active member | member | treasurer | — | INCLUDE — external Shopify link |

### 6e. Other

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Gear article submission | `gear` | — | member | member | — | — | INCLUDE |
| All gear articles | `submissions:gearlist` | — | natoff | natoff | — | — | INCLUDE |

**Excluded from area 6** (~22 routes): `forms:status` / `forms:status_selection` /
`forms:pledge_program` / `forms:discipline` / `forms:resignation` (RedirectView shims);
`forms:init_csv`, `forms:pledge_csv`, `forms:init_sync`, `forms:pledge_sync`, `forms:shingle_post`,
`forms:set_init_date`, `forms:roll_book_download_all`, `forms:discipline_download`,
`forms:discipline_pdftest`, `forms:bill_of_rights_pdf`, `forms:rmp_complete`,
`forms:pledge_program_detail`, `forms:alumniexclusion_detail`, `forms:pledge_program_request_revision`,
`forms:status_graduate`, `forms:role_edit`, `forms:ritual_proficiency_user_table`,
`forms:national_officer_contacts`, `forms:ajax_load_majors`, `forms:otherschool-autocomplete`,
`forms:employer-autocomplete` — all CSV/PDF/sync endpoints, detail pages reached from a list, or AJAX.

## Area 7 — `awards` · audience `member` · flag `FEATURE_AWARDS`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Nominate for an award | `viewflow:awards:awardnomination:start` | — | member | member | — | `FEATURE_AWARDS` | INCLUDE |
| Award winners directory | `awards:directory` | — | member | member | — | `FEATURE_AWARDS` | INCLUDE — see **A-2** |
| Winners by award type | `awards:type_winners` | pk | member | member | — | `FEATURE_AWARDS` | EXCLUDE — drill-down from the directory |
| Winners by cycle | `awards:cycle_winners` | pk | member | member | — | `FEATURE_AWARDS` | EXCLUDE — drill-down from the directory |
| A member's award history | `awards:member_history` | `@username` | member | member | — | `FEATURE_AWARDS` | INCLUDE |
| A chapter's award history | `awards:chapter_history` | `@chapter_slug` | member | member | — | `FEATURE_AWARDS` | INCLUDE |
| Grant an award | `awards:direct_grant` | — | member² | officer | regent | `FEATURE_AWARDS` | INCLUDE |
| Export award data | `awards:export` | — | member | member | — | `FEATURE_AWARDS` | INCLUDE |
| Award certificates | `awards:grant_artifacts` | pk | member | member | — | `FEATURE_AWARDS` | EXCLUDE — reached from a grant |

² `LoginRequiredMixin` + a `can_grant_awards(user)` check in `dispatch`. Catalogued as `officer` because
that is the effective audience; **TWI-3 must special-case it or the card will show to members who then
get bounced home with an error** — exactly the "advertising something you cannot reach" failure the plan
forbids.

**EXCLUDE — superuser-only internal tooling (resolved decision #6):** `awards:import_upload`,
`awards:import_queue`, `awards:import_resolve`.
**Excluded:** `awards:eligible_recipients`, `awards:recipient_member_autocomplete`,
`awards:artifact_download`.

## Area 8 — `volunteering` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Nominate someone for national office | `viewflow:nominations:nomination:start` | — | member | member | — | — | INCLUDE |
| All volunteer nominations | `nominations:list` | — | natoff | natoff | — | — | INCLUDE |

**Excluded:** `nominations:consent` (unguessable per-nominee token, external actor — the *concept*
belongs in the nomination card's copy, not as its own entry), `nominations:training`,
`nominations:appointment`, `nominations:denial` (all workflow task screens reached from a task inbox).

## Area 9 — `finances` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter invoices | `finances:list` | — | member | member | treasurer | — | INCLUDE |
| Chapter balances | `finances:chapters` | — | member³ | member | treasurer | — | INCLUDE |

³ **Fixed during this audit.** Was `LoginRequiredMixin` only, so any member could list *every* chapter's
balance. `ChapterBalancesListView.get_queryset` now scopes to `user.current_chapter` unless
`user_is_national_officer(user)`, so the same URL serves both audiences. Catalogued as `member`.

## Area 10 — `training-education` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Chapter training records | `trainings:list` | — | member | member | — | — | INCLUDE |
| Vector LMS | *(external)* | — | member | member | — | — | INCLUDE — `https://thetatau-tx.vectorlmsedu.com` |
| National training portal | *(external)* | — | natoff | natoff | — | — | INCLUDE — `https://apps.ed.thetatau.org/…` |

> The registry needs an **external-URL** representation. `url_name` cannot express these two, and both
> are live nav items. Suggest an `external_url` field on `Feature`, mutually exclusive with `url_name`.
> **This is a small TWI-2 model change not currently in the plan.**

## Area 11 — `jobs` · audience `member` · flag `FEATURE_JOBS`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Job board | `jobs:list` | — | member | member | — | `FEATURE_JOBS` | INCLUDE |
| Post a job | `jobs:add` | — | member | member | — | `FEATURE_JOBS` | INCLUDE |
| My saved job searches | `jobs:search` | — | member | member | — | `FEATURE_JOBS` | INCLUDE |
| Save a job search | `jobs:add_search` | — | member | member | — | `FEATURE_JOBS` | INCLUDE |
| Job detail | `jobs:detail` | pk+slug | member | member | — | `FEATURE_JOBS` | EXCLUDE — reached from the board |
| Approve a job posting | `jobs:approve` | pk | natoff | natoff | — | `FEATURE_JOBS` | INCLUDE |
| Ban a user from posting | `jobs:ban` | pk | natoff | natoff | — | `FEATURE_JOBS` | EXCLUDE — row action |

**Excluded:** `jobs:copy`, `jobs:update`, `jobs:delete`, `jobs:report`, `jobs:update_search`,
`jobs:search_filter`, `jobs:redirect`, and 3 autocompletes.

## Area 12 — `ballots-voting` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| My ballots | `ballots:votelist` | — | member | member | — | — | INCLUDE |
| Cast a vote | `ballots:vote` | slug | officer | officer | regent | — | INCLUDE |
| All ballots | `ballots:list` | — | natoff | natoff | — | — | INCLUDE |
| Create a ballot | `ballots:create` | — | natoff | natoff | — | — | INCLUDE |
| Ballot results | `ballots:detail` | slug | natoff | natoff | — | — | INCLUDE |

**Excluded:** `ballots:copy`, `ballots:update`, `ballots:redirect`.

> Note the split: **only officers vote** (`BallotCompleteCreateView` is `OfficerRequiredMixin`) but
> **every member sees the ballot list**. Get this wrong in the fixture and members are invited to vote
> and then blocked.

## Area 13 — `contacts-communication` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Sync contacts to my phone | `contact_sync:status` | — | member | member | corresponding secretary | — | INCLUDE |
| Download region contacts (vCard) | `contact_sync:region_vcard` | `@region_slug` | member | member | — | — | INCLUDE |
| Download national contacts (vCard) | `contact_sync:national_vcard` | — | member | member | — | — | INCLUDE |
| Member email communication | `email_tracking:member_communication` | — | natoff | natoff | — | — | INCLUDE |
| Message delivery history | `email_tracking:message_history` | message id | natoff | natoff | — | — | EXCLUDE — drill-down |

**Excluded:** all 10 `contact_sync` Google/Microsoft OAuth authorize/callback/sync/disconnect/auto-sync
endpoints, `email_tracking:member_communication_results`.

## Area 14 — `regions-national` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| My region | `regions:detail` | `@region_slug` | member | member | — | — | INCLUDE |
| Region list | `regions:list` | — | member | member | — | — | INCLUDE |
| Region dashboard | `regions:dashboard` | `@region_slug` | natoff | natoff | regional director | — | INCLUDE |
| Region officers | `regions:officers` | `@region_slug` | natoff | natoff | regional director | — | INCLUDE |
| Region advisors | `regions:advisors` | `@region_slug` | natoff | natoff | regional director | — | INCLUDE |
| Region tasks | `regions:tasks` | `@region_slug` | natoff | natoff | regional director | — | INCLUDE |
| National dashboard | `regions:dashboard` | `national` | natoff | natoff | — | — | INCLUDE — **static** kwarg |
| Events & attendance dashboard | `regions:event_attendance` | — | natoff | natoff | — | — | INCLUDE |
| All scores | `scores:chapterlist` | — | member⁴ | natoff | — | — | INCLUDE |
| Workflow task inbox | `viewflow:index` | — | member | member | all officers | — | INCLUDE — **verify the exact URL name in TWI-8** |

⁴ `LoginRequiredMixin` only — any member can list every chapter's scores. Same shape as the finances
issue fixed in Area 9, but scores are far less sensitive and were not in scope for this pass.
Catalogued as `natoff` so the catalog does not advertise it chapter-wide. **Left as-is deliberately.**

> `regions:officers 'national'` and `regions:advisors 'national'` appear in the Members dropdown as
> "All Officers" / "All Advisors" — same view, static kwarg. Two extra entries, both `natoff`.

**Excluded:** `regions:redirect`.

## Area 15 — `surveys` · audience `member`

| Name | URL name | kwargs | Actual | Catalog | Duty roles | Flag | Verdict |
|---|---|---|---|---|---|---|---|
| Depledge survey | `surveys:depledge` | `@username` | public | member | pledge/new member educator | — | INCLUDE — catalogue the concept |
| Survey response | `surveys:survey-detail` | slug | public | member | — | — | EXCLUDE — per-survey token/slug, not linkable generically |

**Excluded:** `surveys:survey-detail-step`, `surveys:survey-detail-member`,
`surveys:survey-detail-step-member`.

---

# Section C — Global exclusions

| Group | Count | Reason |
|---|---|---|
| Autocomplete endpoints (`*-autocomplete`, `*_autocomplete`) | 13 | AJAX widgets inside forms; never navigated to |
| `RedirectView` shims (`*:redirect`, legacy short URLs) | ~14 | Alias an included feature; would duplicate cards |
| OAuth / webhook / infrastructure (`o/`, `anymail/`, `ckeditor/`, `email-signals/`, `django_plotly_dash/`, `contact_sync` provider endpoints) | ~16 | Not user-facing |
| CSV / PDF / sync endpoints | ~12 | Produce a file from a page already catalogued |
| Report Builder (`report_builder`, `report_download_file`, `report_check_status`, `ajax_add_star`, `export_to_report`, `related_fields`, `fields`, `generate_report`) | 8 | `staff_member_required` — internal tooling, resolved decision #6 |
| Award import (`awards:import_*`) | 3 | Superuser-only, resolved decision #6 |
| Django admin (`admin:*`) | — | Internal, resolved decision #6 |
| Debug-only (`herald/`, `silk/`, `__debug__/`, `400/`–`500/`) | 8 | Not present in production |

---

# Section D — Viewflow flows (14)

Confirmed by reading `flows.py` in 4 apps. Start URLs follow `viewflow:<app>:<flow>:start`.

| Flow class | App | Process title | Start URL | Area | Start audience |
|---|---|---|---|---|---|
| `PrematureAlumnusFlow` | forms | Premature Alumnus Process | `viewflow:forms:prematurealumnus:start` | 6a | member |
| `InitiationProcessFlow` | forms | Initiation Process | *(StartFunction)* | 6a | via `forms:init_selection` |
| `ConventionFlow` | forms | Convention Process | `viewflow:forms:convention:start` | 6b | member |
| `PledgeProcessFlow` | forms | Pledge Process | *(StartFunction)* | 6a | via `forms:pledgeform` |
| `OSMFlow` | forms | OSM Process | `viewflow:forms:osm:start` | 6b | member |
| `AlumniExclusionFlow` | forms | Alumni Exclusion Process | `viewflow:forms:alumniexclusion:start` | 6a | member |
| `DisciplinaryProcessFlow` | forms | Disciplinary Process | `viewflow:forms:disciplinaryprocess:start` | 6c | officer |
| `ResignationFlow` | forms | Resignation Process | `viewflow:forms:resignation:start` | 6a | member |
| `ReturnStudentFlow` | forms | Return Student Process | `viewflow:forms:returnstudent:start` | 6a | member |
| `PledgeProgramProcessFlow` | forms | New Member Education Program Process | `viewflow:forms:pledgeprogramprocess:start` | 6c | member |
| `HSEducationFlow` | forms | H&S Education Program Review | `viewflow:forms:hseducation:start` | 6c | member |
| `AwardNominationFlow` | awards | Award Nomination | `viewflow:awards:awardnomination:start` | 7 | member |
| `NominationFlow` | nominations | Volunteer Nomination | `viewflow:nominations:nomination:start` | 8 | member |
| `MemberUpdateFlow` | users | Member Update Process | *(StartFunction)* | 0 | via `users:update` |

**Two things TWI-8 must handle:**

1. **Three flows start with `flow.StartFunction`, not `flow.Start`** — `InitiationProcessFlow`,
   `PledgeProcessFlow`, `MemberUpdateFlow`. They have **no reversible `:start` URL**. Their catalog
   entry must point at the ordinary view that kicks them off (listed above), or the card will render
   unlinked. The plan assumed every flow had a `:start`.
2. **Human task nodes are reviewer-facing functionality** but live at per-task URLs
   (`/workflow/<flow>/<process_pk>/<task_pk>/`) that cannot be reversed generically. Catalogue the
   **task inbox** (Area 14) once, and describe reviewing in each flow's `long_description`. Do not
   attempt one entry per task node.

---

# Section E — Notification commands (context only, not catalog entries)

~40 management commands exist. These are the ones that generate mail a user might ask about; capture
them in `long_description` copy so the catalog can answer "why did I get this email?"

`award_digest`, `job_search_notify`, `remind_workflow_tasks`, `monthly_chapter_officer_email`,
`officer_update_reminder_email`, `region_officer_reminder_digest`, `nomination_follow_up`,
`grad_anniversary_email`, `chapter_founding_day_email`.

> `officer_update_reminder_email` and `monthly_chapter_officer_email` are the two that should carry a
> **Role Guide link** once TWI-12 ships — they already reach exactly the audience that needs it.

---

# Section F — Acceptance checklist

- [x] Every named URL is marked INCLUDE or EXCLUDE-with-reason
- [x] Audience determined by reading each view class, not inferred
- [x] Feature-flagged routes identified (`FEATURE_AWARDS`, `FEATURE_JOBS`, `FEATURE_EVENTS_CALENDAR`)
- [x] Duty roles drawn from `core.models.ALL_ROLES` only
- [x] Dynamic kwargs marked with the `@token` vocabulary
- [x] All 14 Viewflow flows located and mapped to areas
- [x] Owner review of Section A
- [x] A-2 ruled: awards are member-only; views and nav updated
- [x] A-3 / A-4 ruled: public access is intentional, no change
- [x] `finances:chapters` scoped to the viewer's chapter
- [x] `external_url` field confirmed for `Feature`

## Model changes this audit implies

1. **`Feature.external_url`** — **approved.** Vector LMS and the national training portal are live nav
   items with no Django URL name (Area 10). Mutually exclusive with `url_name`.
2. **A permission-check escape hatch** — `awards:direct_grant` gates in `dispatch()` via
   `can_grant_awards`, not via a mixin. Hard-code its catalog audience as `officer`; it is the only
   such case found, so no generic `visibility_check` field is warranted.
3. **Nothing else.** The `FeatureArea` / `Feature` shape in the plan covers the other ~116 entries.
