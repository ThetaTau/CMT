# Open Issue Triage - CMT (Theta Tau Chapter Management Tool)

- **Date:** 2026-07-26
- **Author:** Automated agent (GitHub Copilot)
- **Repository:** [ThetaTau/CMT](https://github.com/ThetaTau/CMT/issues)
- **Scope:** All **108 open issues** (the 4 open pull requests are excluded). Closed issues were not analyzed.
- **How the data was pulled:** The `gh` CLI was **not authenticated** on this machine and `gh auth login` requires an interactive secret, so the equivalent **public GitHub REST API** was used (`GET /repos/ThetaTau/CMT/issues?state=open`). Raw data saved to [scratchpad/cmt_open_issues.json](../../scratchpad/cmt_open_issues.json).
- **Method:** Every issue body was read; each Rollbar crash traceback was parsed down to its **application-level frame** to group crashes by root cause. A few root causes were confirmed against the current code (e.g. [trainings/models.py](../../thetatauCMT/trainings/models.py)). Reuse opportunities were cross-referenced with prior engineering notes in [.github/copilot-memory/](../../.github/copilot-memory/) and repo memory.

> **To pull these yourself once `gh` is authenticated:**
> `gh issue list --repo ThetaTau/CMT --state open --limit 200 --json number,title,labels,body,createdAt,updatedAt,comments,url`

---

## 1. Executive summary

| Category | Count | Notes |
|----------|------:|-------|
| Functional bug (reported behavior) | 13 | Several are data-quality / dashboard-correctness issues that mislead National Officers. |
| Enhancement / feature | 42 | Large backlog; ~12 are near-empty stubs that need scoping. |
| Docs / onboarding | 6 | Includes 3 stale one-off "intern" tasks. |
| Infrastructure / platform | 1 | **#1098** - Python EOL with an external deadline. |
| **Total** | **108** | |


**Priority distribution (this triage's assessment):**

| Priority | Meaning | Count |
|----------|---------|------:|
| **P0** | Urgent / externally time-boxed | 1 |
| **P1** | High - active crash clusters, data corruption, or broken automation | 15 |
| **P2** | Medium - individual crashes & functional bugs (user-recoverable) | 40 |
| **P3** | Low - enhancements, docs, stubs, rare edge cases | 52 |

---


## 4. Functional bugs (reported behavior, no traceback)

| Issue | Summary | Priority | Needs repro info? |
|-------|---------|:-:|:-:|
| [#615](https://github.com/ThetaTau/CMT/issues/615) | Withdrawn member not reset to Active after invoice payment | P2 | Partial |
| [#1040](https://github.com/ThetaTau/CMT/issues/1040) | Many duplicate majors for a chapter | P2 | Yes (chapter) |
| [#1042](https://github.com/ThetaTau/CMT/issues/1042) | Verify Training report captures H&S education courses | P2 | No (verification task) |
| [#1043](https://github.com/ThetaTau/CMT/issues/1043) | Members "active-pending" when they should be active - bug or need a "why" indicator | P2 | Yes |
| [#53](https://github.com/ThetaTau/CMT/issues/53) | Deleted submission leaves an orphaned completed task | P3 | No |

---

## 5. Enhancements / features

> Grouped by theme. Most are **P3**; a few small, well-specified ones are **P2**. Items marked (needs info) are underspecified - see sections 7/8.

### Notifications & reminders (natural epic - consider grouping)
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#1049](https://github.com/ThetaTau/CMT/issues/1049) | In-app notifications w/ nav-bar counter | P3 |
| [#1050](https://github.com/ThetaTau/CMT/issues/1050) | Email subscription for selected notifications | P3 |
| [#1051](https://github.com/ThetaTau/CMT/issues/1051) | Task due-date email reminders | P3 |
| [#572](https://github.com/ThetaTau/CMT/issues/572) | Signature-request notifications tab + email | P3 |
| [#1072](https://github.com/ThetaTau/CMT/issues/1072) | Role-specific new-officer welcome email | P3 |

### Tasks & roles
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#996](https://github.com/ThetaTau/CMT/issues/996) | Chapter filter should override region filter | P2 |
| [#1053](https://github.com/ThetaTau/CMT/issues/1053) | Auto-filter Tasks by current role | P3 |
| [#998](https://github.com/ThetaTau/CMT/issues/998) | RD-defined region-only tasks | P3 |
| [#1001](https://github.com/ThetaTau/CMT/issues/1001) | Goals tied to role, not individual user | P3 |

### Members, pledges & lifecycle
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#231](https://github.com/ThetaTau/CMT/issues/231) | Handle alumni advisors from another chapter (has code stub) | P2 |
| [#239](https://github.com/ThetaTau/CMT/issues/239) | Auto-update username when email changes | P2 |
| [#411](https://github.com/ThetaTau/CMT/issues/411) | Enforce pledge deferral 1-year limit + warnings (bylaw 4.4.7) | P2 |
| [#1057](https://github.com/ThetaTau/CMT/issues/1057) | Better re-add of previously-depledged PNMs (pairs with #782) | P2 |
| [#240](https://github.com/ThetaTau/CMT/issues/240) | Warning when a faculty advisor is alumni | P3 |
| [#443](https://github.com/ThetaTau/CMT/issues/443) | Cancel an initiation process, revert members to PNM (rare) | P3 |
| [#1056](https://github.com/ThetaTau/CMT/issues/1056) | Email verification on PNM/pledge form (good first issue) | P3 |
| [#1070](https://github.com/ThetaTau/CMT/issues/1070) | Expose graduation-report data back to members | P3 |

### Dashboards, scoring & reporting
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#628](https://github.com/ThetaTau/CMT/issues/628) | Treasurer dashboard (historical balances, dues, debit-card risk flags) | P2 |
| [#655](https://github.com/ThetaTau/CMT/issues/655) | Financial performance metric on dashboard (recent interest 2026-07) | P3 |
| [#1003](https://github.com/ThetaTau/CMT/issues/1003) | "Current best" column in scoring | P3 |
| [#1034](https://github.com/ThetaTau/CMT/issues/1034) | Scoring UI colors for fulfilled columns (good first issue) | P3 |
| [#1060](https://github.com/ThetaTau/CMT/issues/1060) | In-chapter contribution leaderboard (needs info) | P3 |
| [#869](https://github.com/ThetaTau/CMT/issues/869) | 2021-2023 biennium graphs (needs info, dated) | P3 |

### Communication & content
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#991](https://github.com/ThetaTau/CMT/issues/991) | Region mailing lists / RD send email from CMT (needs info) | P3 |
| [#1062](https://github.com/ThetaTau/CMT/issues/1062) | In-system communication channel (e.g. cor-sec list) (needs info) | P3 |
| [#1000](https://github.com/ThetaTau/CMT/issues/1000) | RD "kudos" message to chapters (needs info) | P3 |
| [#1055](https://github.com/ThetaTau/CMT/issues/1055) | Section of labeled document links (PPM, constitution) (good first issue) | P3 |
| [#1063](https://github.com/ThetaTau/CMT/issues/1063) | Cleaner, more relevant front page (needs info; author asks for input) | P3 |
| [#265](https://github.com/ThetaTau/CMT/issues/265) | Ballot form tweaks (rename "Name"->"Ballot Name", date picker, natoff scope) (good first issue) | P3 |
| [#116](https://github.com/ThetaTau/CMT/issues/116) | Per-chapter document repo (constitution/bylaws) (needs info) | P3 |
| [#172](https://github.com/ThetaTau/CMT/issues/172) | Wiki in CMT (Confluence export/import) (needs info) | P3 |
| [#108](https://github.com/ThetaTau/CMT/issues/108) | Guest view of chapter (needs info) | P3 |
| [#105](https://github.com/ThetaTau/CMT/issues/105) | Anonymous RM/feedback form (needs info) | P3 |
| [#9](https://github.com/ThetaTau/CMT/issues/9) | Visitation App (needs info, stub) | P3 |

### Integrations & platform-ish
| Issue | Summary | Priority |
|-------|---------|:-:|
| [#447](https://github.com/ThetaTau/CMT/issues/447) | Investigate Salesforce integration (needs info, empty) | P3 |
| [#382](https://github.com/ThetaTau/CMT/issues/382) | Mask uploaded-file URLs (GCS CNAME endpoint) | P3 |
| [#269](https://github.com/ThetaTau/CMT/issues/269) | NatOff on/off-boarding checklist automation | P3 |
| [#757](https://github.com/ThetaTau/CMT/issues/757) | Disciplinary process w/ multiple users & open-ended outcomes (needs info) | P3 |
| [#702](https://github.com/ThetaTau/CMT/issues/702) | Force-complete old initiation invoices (needs info, empty) | P3 |
| [#1061](https://github.com/ThetaTau/CMT/issues/1061) | Database of members' previous work (needs info) | P3 |

---

## 6. Verify-and-close candidates (probably already fixed / stale)

Following the established cleanup pattern (confirm no recurrence on the current stack -> add a regression test -> close):

| Issue | Why it's likely stale | Action |
|-------|-----------------------|--------|
| [#869](https://github.com/ThetaTau/CMT/issues/869) | "2021-2023 biennium" graphs - the biennium is over. | Close or re-scope to current biennium. |

---

### Follow-up questions (per cluster / bug)

- **#1041 (co-op status):** What is the intended status for a member on co-op - **Away**? Confirm the full status mapping so the cleanup job can be corrected.
- **#1043 / #1045:** Do you want an actual behavior fix, an explanatory tooltip/column ("why is this member active-pending"), or both? A screen recording for #1045 would confirm bug vs. UI confusion.

---

## 8. Needs more information (blocked until answered)

**Labeled `Need More Info`:** [#1060](https://github.com/ThetaTau/CMT/issues/1060), [#1061](https://github.com/ThetaTau/CMT/issues/1061).

**Near-empty / stub bodies (need a written spec before estimating):** [#447](https://github.com/ThetaTau/CMT/issues/447), [#702](https://github.com/ThetaTau/CMT/issues/702), [#609](https://github.com/ThetaTau/CMT/issues/609), [#610](https://github.com/ThetaTau/CMT/issues/610), [#9](https://github.com/ThetaTau/CMT/issues/9).

**Underspecified feature requests (need concrete acceptance criteria):** [#105](https://github.com/ThetaTau/CMT/issues/105), [#108](https://github.com/ThetaTau/CMT/issues/108), [#116](https://github.com/ThetaTau/CMT/issues/116), [#172](https://github.com/ThetaTau/CMT/issues/172), [#757](https://github.com/ThetaTau/CMT/issues/757), [#869](https://github.com/ThetaTau/CMT/issues/869), [#991](https://github.com/ThetaTau/CMT/issues/991), [#1000](https://github.com/ThetaTau/CMT/issues/1000), [#1062](https://github.com/ThetaTau/CMT/issues/1062), [#1063](https://github.com/ThetaTau/CMT/issues/1063).

**Bugs blocked on reproduction data (which chapter / term / screen recording):** [#892](https://github.com/ThetaTau/CMT/issues/892), [#1040](https://github.com/ThetaTau/CMT/issues/1040), [#1043](https://github.com/ThetaTau/CMT/issues/1043), [#1045](https://github.com/ThetaTau/CMT/issues/1045), [#1046](https://github.com/ThetaTau/CMT/issues/1046), [#1048](https://github.com/ThetaTau/CMT/issues/1048), [#891](https://github.com/ThetaTau/CMT/issues/891).

**Crashes needing a triggering record to reproduce:** [#852](https://github.com/ThetaTau/CMT/issues/852), [#967](https://github.com/ThetaTau/CMT/issues/967), [#1030](https://github.com/ThetaTau/CMT/issues/1030), [#836](https://github.com/ThetaTau/CMT/issues/836), [#964](https://github.com/ThetaTau/CMT/issues/964).

---

## 9. Docs / onboarding

| Issue | Summary | Priority |
|-------|---------|:-:|
| [#578](https://github.com/ThetaTau/CMT/issues/578) | Admin help docs (find a profile, chapter balances, etc.) (good first issue) | P3 |
| [#1038](https://github.com/ThetaTau/CMT/issues/1038) | Raise member awareness that they have a login | P3 |
| [#1039](https://github.com/ThetaTau/CMT/issues/1039) | Onboarding tutorials / "crash course" for chapter use | P3 |
| [#608](https://github.com/ThetaTau/CMT/issues/608), [#609](https://github.com/ThetaTau/CMT/issues/609), [#610](https://github.com/ThetaTau/CMT/issues/610) | 2021 intern setup tasks (Docker, apps, VS Code debug) - **stale, close** | P3 |

---

## 10. Appendix - methodology & artifacts

- **Source data:** [scratchpad/cmt_open_issues.json](../../scratchpad/cmt_open_issues.json) (raw API), [scratchpad/cmt_issues_compact.txt](../../scratchpad/cmt_issues_compact.txt) (readable digest), [scratchpad/cmt_crash_frames.txt](../../scratchpad/cmt_crash_frames.txt) (parsed app-level traceback frames).
- **Priority key:** **P0** externally time-boxed; **P1** active crash cluster / data corruption / broken automation; **P2** individual crash or functional bug (user can retry); **P3** enhancement / docs / rare edge case.
- **Effort key:** S <= half-day; M ~ 1-3 days; L > 3 days (rough).
- **Caveat:** Priorities reflect code-signal (frequency, blast radius, recency) plus the maintainer context in repo memory; they should be re-ranked against Theta Tau's operational calendar (recruitment, initiation, dues cycles) by the product owner.
