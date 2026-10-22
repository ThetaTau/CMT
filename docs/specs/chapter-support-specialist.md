# Chapter Support Specialists (CSS)

**Status (2026-10-22):** All questions are answered (Q1 to Q27); see the
[Decisions log](#decisions-log). Every work item (CSSWI-1 to CSSWI-11) is built and tested,
including a browser check of the new pages. The build added smaller defaults S19 to S22 and
changed S14 (disabled rather than hidden buttons); please skim them, since they need no
answer unless you disagree. Deployment steps are in `docs/deploy.md` §8.3. See
[Progress](#progress) for the rest.

**How to use this document**

- Answer each question in [Questions for review](#questions-for-review) on its **Answer:**
  line. "Default" is a fine answer. Add anything else under the question. Each question says
  which work items it blocks, so answer those first if you are short on time.
- [Smaller defaults](#smaller-defaults-no-answer-needed-unless-you-disagree) need no answer
  unless you disagree.
- [Progress](#progress) is the tracker. Each work item updates its row and ticks its
  checklist when it lands.
- When a question is answered, the build session copies the answer into the
  [Decisions log](#decisions-log) and adjusts the work items it affects. Questions that come
  up during the build are added at the end of the questions section, dated, the same way.
- Work items are named CSSWI-n (CSS work item) and are written so a fresh session can pick
  one up cold. Read the [Shared preamble](#shared-preamble) and
  [Codebase facts](#codebase-facts-that-shape-the-design) first.

Proposed app: `thetatauCMT.support`. URL prefix: `/support/`. URL namespace: `support` (S10).

## Progress

| Item | Summary | Depends on | Waiting on | Status |
|---|---|---|---|---|
| Spec | This document | | | All answers in |
| CSSWI-1 | CSS role and status, `ChapterSupportAssignment` and `SupportDigestEntry` models, admin, anonymizer | | | Built, tested, models approved |
| CSSWI-2 | Access core: a CSS viewing an assigned chapter sees what its Regent sees, view only | 1 | | Built and tested |
| CSSWI-3 | Checks that read the viewer's own chapter or real roles | 2 | | Built and tested |
| CSSWI-4 | The CSS chapter switcher bar | 2 | | Built and tested |
| CSSWI-5 | Managing CSSs: accounts, assignments, directory | 1 | | Built and tested |
| CSSWI-6 | Regent emails to CSSs: CC on time-sensitive ones, daily and monthly digests | 1 | | Built and tested |
| CSSWI-7 | CSSs on the chapter page and profiles | 1 | | Built and tested |
| CSSWI-8 | CSS landing page: "My Chapters" table and dashboard | 4 | | Built and tested |
| CSSWI-9 | Feature catalog, role guide, seed command, docs, full test run | all | | Built and tested |
| CSSWI-10 | Officer contact sync for a CSS's chapters, and CSSs in region syncs | 1 | | Built and tested |
| CSSWI-11 | Two-factor sign-in for CSSs and every National Officer | | | Built and tested |

Build order: CSSWI-1, then pause for your review of the models (the usual working style).
Then CSSWI-2, then 3 to 7 and 10 in any order, then 8 and 9. CSSWI-11 does not depend on the
rest and can ship first.

## What was asked for

| # | Requirement (owner, 2026-10-22) | Where it lands |
|---|---|---|
| R1 | A new user type and role, the Chapter Support Specialist (CSS), who works with chapter leadership as a chapter advisor. | CSSWI-1 |
| R2 | A CSS has access to everything the chapter's Regent has access to, for the chapters they are assigned to, and only those. | CSSWI-2, CSSWI-3 (Q1 to Q5) |
| R3 | A CSS is assigned to several chapters. | CSSWI-1, CSSWI-5 |
| R4 | Like a National Officer, a CSS switches between chapters with the bar under the main menu, but only between their assigned chapters. | CSSWI-4 |
| R5 | A CSS has none of the other National Officer permissions. | CSSWI-2 (S6) |
| R6 | A CSS is not a chapter member, not a chapter officer, and not a member of the fraternity. | CSSWI-1 (Q7 to Q9), CSSWI-3 (Q5) |
| R7 | A CSS gets the same email notifications the Regent gets for each assigned chapter. | CSSWI-6 (Q13 to Q16) |
| R8 | Questions for the owner live in this document and are answered as the feature is built. | This document |
| R9 | (2026-10-22, Q1) A CSS only looks. "Chapters are still responsible for doing all the things." | CSSWI-2, CSSWI-3 |
| R10 | (Q12) A landing page with the chapters table on top and the full dashboard for their chapters below, in the first release. | CSSWI-8 |
| R11 | (Q14) Daily and monthly digests, "so they don't miss anything". | CSSWI-6 |
| R12 | (Q16) CSSs on the shingle sheet's "Notify" column, and able to sync their chapters' officers into their own contacts. | CSSWI-6, CSSWI-10 |
| R13 | (Q19) Two-factor sign-in for CSSs, and for every National Officer, as part of this work. | CSSWI-11 |
| R14 | (S3) A CSS can hide the switcher bar. | CSSWI-4 |

## The idea in one paragraph

National Officers can already pick a chapter and the Regent role in the region bar, and from
then on every page treats them as that chapter's Regent (one `UserAlter` row per user, read by
`User.current_chapter` and `User.chapter_officer()`). A CSS gets the same mechanism with four
differences: the chapter list holds only their current assignments, the role is always Regent,
none of the national powers come with it (a CSS is never in the `natoff` group), and it is
**view only** (Q1): a CSS sees everything the Regent sees but changes nothing, because the
chapter still does the work. Access is decided from the assignments every time a page loads,
so ending an assignment removes access at once. Emails do not depend on the chapter being
viewed: they follow the assignments, so a CSS is copied on every assigned chapter's Regent
emails all the time, and also gets digests (Q13, Q14).

## Permission matrix

What your answers produce (follow-up questions noted where one is still open). "Viewing"
means the chapter selected in the CSS's switcher.

| Capability | Regent (own chapter) | CSS, assigned chapter being viewed | CSS, any other chapter | National Officer |
|---|---|---|---|---|
| Officer pages: full roster, member contact details, chapter forms, tasks, GPAs, service hours, events, attendance, Bigs and Littles, chapter details, faculty advisors | See and change | See only (Q1) | No | See and change, through the switcher |
| The Regent's own Audit | File it | See it and whether it is done (Q20) | No | File it, through the switcher as Regent |
| Every officer's submitted transition reports | Read | Read (Q2) | No | Council and Admins read every report; RDs for their region |
| Close a vacant position's transition report | Yes | No (Q20) | No | RDs for their region |
| Owe a transition report | Yes | No | No | For their own positions |
| Cast the chapter's vote on a national ballot | Yes | No; sees the ballot and whether the chapter voted (Q3) | No | No |
| Disciplinary Form 2, and signing as one of the two named officers | When named | No (Q4, Q21) | No | Staff can reassign |
| Public pages: chapter directory, other chapters' pages, events calendar | Yes | Yes | Yes, like any signed-in user | Yes |
| Region pages and dashboards, National menu, national lists, user search, ballot administration, notes, event approvals | No | No | No | Yes |
| Chapter switcher | No | Assigned chapters only | | Every chapter |
| Landing page with a table and dashboard across chapters | No | All assigned chapters (Q12) | | Region and national dashboards |
| The chapter's Regent emails | Yes | CC on time-sensitive ones as sent; the rest in a daily digest; a monthly digest (Q13, Q14, Q25) | | No |
| Sync chapter officers into their own contacts | No | Their assigned chapters (Q16) | | Any region |
| Sign the RMP each semester | Yes | Yes (Q5) | | Yes |
| Two-factor sign-in | Not required | Required (Q19) | | Required (Q19, Q27) |

## Questions for review

Each question shows the default the build will use. Write a letter or your own wording on the
**Answer:** line.

### A. What a CSS can do

### Q1. Can a CSS make changes in an assigned chapter, or only look?

Blocks: CSSWI-2.

- **A (default):** Make changes, like the Regent. Submit chapter forms (initiation report,
  status changes, officer election report, graduation, collection referral, disciplinary
  Form 1), edit chapter details, add faculty advisors, manage events and attendance, enter
  GPAs and service hours, record Bigs and Littles, sign off chapter tasks, and email the
  roster. The CSS is recorded as the person who did it.
- **B:** Look only. Every page the Regent can open, but nothing can be saved. One central rule
  refuses every save, and the pages say why.
- **C:** Make changes, except for actions listed in a Config setting
  (`CSS_BLOCKED_ACTIONS`), so national can turn single actions off without a deploy.

**Answer:** B They should not be able to submit anything. Chapters are still responsible for doing 'all the things' we just want the CSS' to have visibility

### Q2. Powers tied to the real Regent

Blocks: CSSWI-3.

Three things check for the Regent in person, not just for an officer:

- **(a) The Regent's own Audit.** Each of the 5 executive officers files their own Audit, and
  filing it marks that officer's Audit task complete. A National Officer viewing the chapter
  as Regent through the region bar can already file it.
- **(b) Reading every officer's submitted transition reports** for the chapter. These are
  candid handoff notes. In 2026-09 national access to them was narrowed to Council and Admins
  (RDs keep their region), and a National Officer viewing the chapter as Regent does not get
  them.
- **(c) Closing a vacant position's transition report** as "vacant". Today only the chapter's
  Regent and its RD can.

Options:

- **A (default):** All three. This is the literal reading of "everything the Regent can see
  and do".
- **B:** (b) and (c) only. The Audit stays with the real Regent.
- **C:** None. The CSS sees these items and whether they are done, but cannot file, read or
  close them.

Answering per item is fine too, for example "a no, b yes, c yes".

**Answer:** A All three

### Q3. May a CSS cast the chapter's vote on a national ballot?

Blocks: CSSWI-3.

Today the chapter's single vote is cast by its Regent or Scribe. The ballot form quotes the
rule: four-fifths of the chapter's student members decide the vote, and the Regent votes on
the chapter's behalf only when the chapter is out of session.

- **A (default):** No. The CSS sees the chapter's open ballots and whether the chapter has
  voted, and gets the ballot emails, but cannot vote.
- **B:** Yes, like the Regent.
- **C:** No, and chapter ballots are hidden from CSSs.

**Answer:** A

### Q4. Workflow tasks addressed to a named officer

Blocks: CSSWI-3.

Disciplinary "Submit Form 2" is assigned to the Regent (the Vice Regent when the Regent is the
accused). Convention credentials, OSM and Resignation forms are signed by the two officers
named on the form. Central Office can already hand any task to anyone with the Reassign button.

- **A (default):** No change. These stay with the named officers. The CSS gets the emails, and
  Central Office can reassign a stuck task to the CSS.
- **B:** Disciplinary Form 2 is also offered to the chapter's CSSs. Signatures do not change.
- **C:** B, and a CSS can be named as one of the two signing officers on those forms.

**Answer:** A

### Q5. Member-only requirements

Blocks: CSSWI-3.

Today every account that is not alumni must sign the Risk Management Policies each semester
before using the site, and that includes faculty advisors.

- **A (default):** A CSS does not sign the RMP, because it binds members. A CSS has no ballots
  of their own. Their Edit My Info page is short (name, preferred name, pronouns, email,
  phone, photo), without member fields such as address, graduation year, major and emergency
  contact.
- **B:** Like faculty advisors today, a CSS signs the RMP each semester. The rest of A stays.

**Answer:** B

### B. Accounts and assignments

### Q6. Who creates CSS accounts and assigns their chapters?

Blocks: CSSWI-1, CSSWI-5.

Assigning a chapter gives Regent-level access to its member records, so the default keeps the
group small. The `natoff` group holds every National Officer, including every RD and director.

- **A (default):** Admins, plus anyone listed in a new Config setting, `CSS_MANAGERS`
  (usernames, emails or National Officer role names, comma separated; seeded with the
  Executive Director). They use a new "Chapter Support Specialists" page. Every National
  Officer can open that page to see who covers which chapter, without the buttons. Django
  admin works too.
- **B:** Admins only, in Django admin.
- **C:** A, plus each Regional Director for the chapters in their own region.
- **D:** A manager requests an assignment and the Executive Director approves it, as a
  Viewflow approval workflow like Volunteer Nominations. Larger build.

**Answer:** A

### Q7. What kind of account is a CSS?

Blocks: CSSWI-1.

Every account has a membership status (active, alumni, PNM, advisor, nonmember and so on),
which is what "user type" means in the CMT today.

- **A (default):** A new status, "Chapter Support Specialist" (`css`). Never counted as a
  member, never in advisor or officer lists, and chapter officers cannot set or change it.
- **B:** A new general status, "National Staff" (`staff`), with Chapter Support Specialist as
  the role on top, so a later staff position can reuse the status.
- **C:** The existing "Nonmember" status. It is shared with former PNMs, so reports could not
  tell the two apart.
- **D:** The existing "Advisor" status. It puts the CSS in their home chapter's faculty
  advisor list, where that chapter's officers can remove them.

**Answer:** A a new status

### Q8. What is a CSS's home chapter?

Blocks: CSSWI-1.

Every account must belong to one chapter (`User.chapter` is required). For a CSS it is only a
resting place: the header and every page follow the chapter being viewed, and fall back to it
only when nothing else applies.

- **A (default):** Their first assigned chapter, moved automatically to another current
  assignment when that one ends. The status from Q7 keeps them out of that chapter's roster,
  officer lists and member counts. The home chapter grants nothing by itself: access always
  comes from current assignments.
- **B:** A placeholder chapter such as "National Office". *(Corrected 2026-10-22: this
  originally said only about 15 of 80 chapter queries skip inactive chapters. That count
  missed the common `.exclude(active=False)` form. About 70 of the roughly 110 references do
  skip inactive chapters, including the three scheduled officer emails, so an inactive
  placeholder is low risk.)*
- **C:** No chapter at all for CSS accounts. The cleanest data, but the biggest change: about
  60 places in the app read a person's chapter directly, and the menus need a chapter to build
  their links.

**Answer:** A we have in prod a "Central Office" chapter that is inactive that we would use for this

### Q9. Can a CSS also be a member?

Blocks: CSSWI-1.

For example, an alumnus hired as staff.

- **A (default):** Yes. They keep their member account, status and chapter, and the CSS role
  and assignments are added. The switcher lists their own chapter, where they are a member as
  usual, as well as their assigned chapters.
- **B:** No. A CSS always has a separate non-member account, with a different email address
  from any member account.

**Answer:** A

### Q10. Do assignments have dates?

Blocks: CSSWI-1.

- **A (default):** Yes. Each assignment has a start date and an optional end date. Ending one
  removes access on the next page load. Past assignments stay on record and show on the
  management page.
- **B:** No. A simple on and off list of chapters.

**Answer:** A Yes

### Q11. The existing "Chapter Support Specialist" text on the chapter page

Blocks: CSSWI-7.

Since July, each chapter has a rich-text "Support Specialist" field, typed in Django admin and
shown on the chapter page as "Chapter Support Specialist:".

- **A (default):** Replace it with the chapter's current CSSs, taken from their assignments
  (name linking to the profile, and email). The text field is kept but hidden, and still
  shown for a chapter with no CSS assigned, so nothing typed there is lost during rollout. A
  later cleanup removes it.
- **B:** Show both: the assigned CSSs, then the text.
- **C:** Keep only the text. Assignments are not shown on the chapter page.

**Answer:** A

### C. Getting around

### Q12. A "My Chapters" overview page?

Blocks: CSSWI-8.

- **A (default):** Yes, a simple one. One row per assigned chapter: actives, PNMs, overdue
  tasks, balance and missing officers, each with a "Switch to this chapter" button. Linked
  from the switcher bar.
- **B:** Not in the first version. The switcher is enough.
- **C:** A full dashboard like the region dashboard, limited to their chapters. Larger; a later
  phase.

**Answer:** A and C For initial deployment I would like a simple landing page for them with the table proposed at top and the full dashboard below with relevant graphs and views for their assigned chapters.

### D. Emails

### Q13. Which emails does a CSS get?

Blocks: CSSWI-6.

- **A (default):** Every email the chapter's Regent gets: emails to the Regent personally, to
  the chapter's generic Regent address, and to the whole executive council. The full list is
  in [Email inventory](#email-inventory). The CSS goes on the same line as the Regent (To or
  CC).
- **B:** A, but the CSS is always on CC.
- **C:** Only emails addressed to the Regent specifically (the Regent alone, or the Regent and
  Scribe). Not the council-wide ones such as the monthly officer email, the dues roster and
  workflow updates.

**Answer:** B the CSS should be CC

### Q14. Email volume

Blocks: CSSWI-6.

A CSS with 10 chapters gets 10 copies of each chapter-wide email: 10 monthly officer emails, a
ballot reminder per chapter, and so on.

- **A (default):** Fine for the first version. The same emails each Regent gets, one per
  chapter.
- **B:** A daily digest instead: one email a day covering all their chapters. Larger, because
  it changes how about 15 places send email.

**Answer:** B A daily digest and digests on the months so they don't miss anything.

### Q15. Can a CSS's emails be switched off for one chapter?

Blocks: CSSWI-1, CSSWI-6.

- **A (default):** Yes, by managers only. Each assignment has "Receives chapter emails", on by
  default. For example, off while a new CSS shadows a chapter.
- **B:** No switch.
- **C:** Yes, and the CSS can switch it themselves.

**Answer:** B

### Q16. Chapter contact lists that are not emails

Blocks: CSSWI-6.

The same helper that builds the officers' email list also fills the "Notify" column of the
shingle order Google Sheet. Separately, National Officers can sync a region's officers into
their own Google or Microsoft contacts, or download them as a vCard.

- **A (default):** Leave CSSs out of the shingle sheet and out of the officer contact sync.
  No contact sync for CSSs in the first version.
- **B:** Add CSSs to the shingle sheet's "Notify" column.
- **C:** Let a CSS sync their assigned chapters' officers into their own contacts, the way
  National Officers sync a region. (B and C can both be chosen.)

**Answer:** B and C they should be on the shingle sheet and they can sync contacts

### Q17. Emails about assignments

Blocks: CSSWI-5.

- **A (default):** When a chapter is assigned, email the CSS, and send the chapter's
  executive council an introduction ("Name is your Chapter Support Specialist") with the
  region's address on CC. When an assignment ends, email the CSS only.
- **B:** Email the CSS only.
- **C:** No emails about assignments.

**Answer:** C we will handle official notification on assignments

### E. Visibility and security

### Q18. Who can see that someone is a chapter's CSS?

Blocks: CSSWI-7.

- **A (default):** Every signed-in member: on the chapter page (see Q11) and on the CSS's
  profile ("Chapter Support Specialist for: ..."). Never in the roster or officer lists.
- **B:** Only that chapter's officers, RDs, National Officers and Admins.

**Answer:** A

### Q19. Two-factor sign-in

Blocks: CSSWI-3.

- **A (default):** Not required, the same as Regents and National Officers. Only Admins must
  use it today.
- **B:** Required for CSSs, because they can see several chapters' member records.

**Answer:** B, in fact all national officers should have it going forward. Let's include that with this work.

### Follow-up questions (2026-10-22, from your answers)

Your answers mostly fit together. These eight settle the places where two answers pull
against each other, or where the build needs one more detail. Each shows the reading the
build will use if you answer "Default".

### Q20. "View only" (Q1) and "all three" (Q2)

Blocks: CSSWI-3.

Q1 says a CSS submits nothing. Of the three Regent powers in Q2, only (b), reading every
officer's transition reports, is looking; (a) filing the Regent's Audit and (c) closing a
vacant position's report are both submissions.

- **A (default):** Q1 wins. (a) The CSS sees the Regent's Audit and whether it is done, but
  cannot file it. (b) The CSS reads every officer's submitted transition reports. (c) The CSS
  sees which positions' reports are vacant, but cannot close them.
- **B:** Q1 with an exception for (c) only, since closing a vacant report is housekeeping
  rather than chapter work.
- **C:** Q1 with exceptions for (a) and (c).

**Answer:** A

### Q21. A task Central Office reassigns to a CSS (Q1 and Q4)

Blocks: CSSWI-3.

Q4 A kept "Central Office can reassign a stuck task to the CSS", but under Q1 a CSS could not
complete it.

- **A (default):** No exception. A CSS never completes workflow tasks, and the Reassign
  picker leaves CSS accounts out so a task cannot get stuck with one.
- **B:** One exception: a task Central Office reassigns to a CSS by name can be completed by
  that CSS.

**Answer:** A

### Q22. What a view-only CSS can still do for themselves

Blocks: CSSWI-2.

The proposed rule: a CSS can do anything that only touches their own account, and nothing
that changes chapter or member records.

- Allowed: switch chapters; sign the RMP (Q5); edit their own short profile; set up two-factor
  sign-in (Q19); change their password or email; set email preferences; dismiss What's New
  items; create a personal events calendar feed; sync officers into their own contacts (Q16);
  download the roster CSV and PDFs, since those only read.
- Blocked: everything else. That includes the roster's "Email ALL" button, which sends from
  an ordinary page load rather than a form submission, so it gets its own block; and event
  RSVPs and attendance, which change chapter records.

Options:

- **A (default):** That rule and those lists.
- **B:** Stricter: also no roster CSV or PDF downloads, on-screen only.

**Answer:** A

### Q23. The Central Office home chapter (Q8)

Blocks: CSSWI-1 deploy step, CSSWI-4.

Your Q8 answer, the existing inactive "Central Office" chapter, is really option B (a
placeholder), using a chapter that already exists. That is a sound choice. My option B text
overstated the risk: most chapter lists and all three scheduled officer emails already skip
inactive chapters, and because the chapter already exists, whatever lists it appears in today
do not change. Q8's option B text has been corrected. How the build will use it:

- Non-member CSS accounts belong to Central Office. A member who is also a CSS (Q9) keeps
  their own chapter.
- Central Office cannot be assigned (it is inactive), so it never gives access. After sign-in
  or Reset, a CSS lands on their first assigned chapter (or their own chapter, for a member).
- The chapter is named in a new Config setting, `CSS_HOME_CHAPTER` (its slug), not hard-coded.
  Tests and the seed command create their own inactive chapter.

Please confirm, and give the Central Office chapter's slug if you know it. The build has no
access to production data.

**Answer:** Confirm central officer slug is central-office

### Q24. The landing page (Q12)

Blocks: CSSWI-8.

You asked for the table and the full dashboard in the first release.

- **A (default):** For a CSS, signing in and the Home link open the landing page: the "My
  Chapters" table at the top, then the dashboard limited to their assigned chapters, then the
  What's New feed. The dashboard is the existing region dashboard with every KPI card and
  chart (student members, living census, PNMs, initiations, prealumni, resignations, PNM
  retention; members, initiations, depledges, events, submissions, tasks, trainings and scores
  by chapter; majors, top recruiting chapters, retention, current and graduation employers,
  member organizations), with a chapter filter. Each chapter's usual pages (Chapter Home,
  Tasks) stay one switch away.
- **B:** As A, but drop some charts. Name them.
- **C:** Keep the normal Home page; the landing page is a separate page linked from the bar.

**Answer:** A

### Q25. CC and digests together (Q13 and Q14)

Blocks: CSSWI-6.

Q13 B puts the CSS on CC of each Regent email. Q14 B adds a daily digest and digests "on the
months". These combine in more than one way.

- **A (default):** Both, nothing held back. The CSS is on CC of every Regent email as it is
  sent. Each morning, a daily digest lists the previous day's emails across all their
  chapters (chapter, subject, link), and is skipped on days with nothing. On the first of each
  month, a monthly digest covers each chapter: what was sent last month, and what is still
  open (overdue tasks, missing officers, open ballots, forms waiting).
- **B:** Digests replace the copies. No CC. The daily digest carries the full content of every
  Regent email from the previous day, and the monthly digest summarizes the month.
- **C:** CC only for time-sensitive emails (disciplinary, past-due reports, ballots, officer
  updates, workflow escalations). Everything else arrives only in the daily digest. Monthly
  digest as in A.

**Answer:** I like C so urgent things get notified quickly but a digest still comes to help reduce the amount of emails

### Q26. CSSs in National Officers' contact syncs (Q16)

Blocks: CSSWI-10.

Q16 lets a CSS sync their chapters' officers into their own contacts. The other direction is
open: when a National Officer syncs a region's officers, should the chapters' CSSs come along?

- **A (default):** No, officers only.
- **B:** Yes, labeled "Chapter Support Specialist".

**Answer:** B

### Q27. Rolling out two-factor sign-in to every National Officer (Q19)

Blocks: CSSWI-11 (rollout only).

"National Officers" here means everyone in the `natoff` group, including RDs and directors,
even while "Hide national officer functionality" is on. Today only Admins are required. The
current code forces setting up an authenticator app and then asks for its code at each
password sign-in.

- **A (default):** Announce first. From the deploy, a National Officer without two-factor sees
  a banner with a setup link. Enforcement starts on a date you set in a new Config setting,
  `NATOFF_2FA_REQUIRED_FROM` (suggested: two weeks after the deploy). CSSs must use it from
  their first sign-in. Each user gets backup codes at setup, and Admins can remove a lost
  device in Django admin.
- **B:** Enforce for everyone in the `natoff` group at the deploy, with no notice period.

**Answer:** A seems nicer with announcement. Good idea

### Smaller defaults (no answer needed unless you disagree)

- **S1.** Wording: "Chapter Support Specialist" in full; "CSS" only where space is tight (the
  switcher bar, table headers). No em dashes in anything a user reads.
- **S2.** A chapter can have more than one CSS at once (handoffs, shared coverage), and a CSS
  can have any number of chapters. Only active chapters, including candidate chapters, can be
  assigned.
- **S3.** The switcher bar sits under the main menu, styled like the National Officers' region
  bar: "Chapter Support Specialist", the chapter being viewed, a "View only" label, a dropdown
  of their current assignments only, Apply, and Reset (back to their first assigned chapter,
  Q23). No region links, no officer role picker, no "hide national officer functionality"
  toggle. The last chapter chosen is remembered between sign-ins. *(Your note, 2026-10-22:)* a
  CSS can hide the bar: the account menu gets the same "Hide region bar" / "Show region bar"
  item National Officers have, remembered by the browser. With the bar hidden, the header
  still names the chapter being viewed, and the landing page's "Switch to this chapter"
  buttons still work.
- **S4.** In an assigned chapter, the CSS stands in as the Regent for every check that decides
  what can be seen, so menus, the feature catalog and role guides look as they do for that
  chapter's Regent. A new "Chapter Support Specialist" role guide explains that the role is
  view only, and links the switcher, the landing page and the Regent guide.
- **S5.** Emails follow assignments, not the switcher (see the one-paragraph idea).
- **S6.** National-only pages stay closed: region pages and dashboards, the National menu,
  national officer and advisor lists, user search, ballot administration, notes, event
  approvals, region contact sync (a CSS syncs only their own chapters' officers, Q16), Member
  Email Communication, and the workflow task lists.
- **S7.** A National Officer who is also a CSS keeps the national bar, which already reaches
  every chapter. The CSS bar is not shown to them. The CSS emails still come.
- **S8.** A CSS with no current assignment can sign in, and sees their home chapter (Central
  Office, Q23) with no officer access. The bar says "No chapters assigned. Contact the Central
  Office."
- **S9.** Like anyone else, a CSS is recorded as the person who submitted or changed
  something. There is no extra "(CSS)" label on records; their profile says they are a CSS.
- **S10.** The code lives in a new app, `thetatauCMT.support`, plus small hooks in `core`,
  `users`, `chapters`, `transitions`, `forms` and `ballots`.
- **S11.** A CSS sees every contact field of members in their assigned chapters, whatever each
  member's visibility setting, as chapter officers do. The help text members read ("Your
  chapter's officers, National Officers, and Admins can always see them") gains "and Chapter
  Support Specialists".
- **S12.** The CSS role is dated, and only CSS managers (Q6) give or end it. A CSS cannot edit
  their own role dates. (Today a member may edit the dates of their own non-officer roles.)
- **S13.** The "submit your New Member Education program" banner that chapter officers see is
  shown to a CSS too, for the chapter being viewed, reworded as information without the
  submit link ("This chapter has not submitted its New Member Education program this
  semester.").
- **S14.** View only, on screen: buttons that would change something are hidden for a CSS on
  the main officer pages. Anything missed is refused centrally with "Chapter Support
  Specialists have view-only access. The chapter's officers make changes."
  *(Changed during the build, 2026-10-22:)* the buttons are shown disabled rather than hidden,
  on every page, with that message as their tooltip. The server marks each form a CSS cannot
  submit, so new pages are covered without extra code, and a CSS sees the same controls the
  Regent sees, which helps when advising. Say if you would rather have them hidden.
- **S15.** A CSS cannot be assigned to their own member chapter (Q9).
- **S16.** Which emails count as time-sensitive (Q25) is a Config setting,
  `CSS_REALTIME_EMAILS`, defaulting to the "CC as sent" rows of the
  [Email inventory](#email-inventory). National can move an email between real time and the
  digest without a deploy.
- **S17.** The daily digest ends with a one-line list of that day's time-sensitive emails that
  were already sent to the CSS, so one email shows the whole day.
- **S18.** A CSS's own contact sync (Q16) holds the officers of their chapters only, not other
  CSSs.
- **S19.** *(Added during the build.)* Ballots (Q3): a CSS sees each chapter ballot and
  whether, when and by which officer role the chapter voted, but never how it voted. Q3 says
  "whether it voted", and a chapter's vote is its own business.
- **S20.** *(Added during the build.)* What a CSS signs for themselves, such as the RMP, is
  filed under their own chapter (Central Office, or their member chapter), never the chapter
  they are viewing, so it cannot appear in that chapter's submissions or change its score.
- **S21.** *(Added during the build.)* Managers can remove a CSS from their page: the role and
  every assignment end at once (access stops on the next page load), upcoming assignments are
  cancelled, and a staff account is switched off so it cannot sign in. A member CSS keeps
  their member account. Adding the same email again later restores the staff account.
- **S22.** *(Added during the build.)* The feature catalog has no CSS-only audience, so the
  three CSS entries (My Chapters, the switcher, syncing your chapters' officers) use the
  officer audience and are tagged with the CSS role, as this spec suggested. Chapter officers
  therefore see them in the catalog too; following one sends a non-CSS back to Home with a
  short note. A CSS audience would hide them from officers; say if you want it.

## Shared preamble

Read this before starting any work item.

- **Local dev is docker.** Never use the host virtualenv.
  - Tests: `docker exec thetataucmt_local_django pytest <path> -v --tb=short`
  - Management: `docker exec thetataucmt_local_django python manage.py <cmd>`
- **Working style:** models and migrations first, then pause for review; then services, then
  views and templates, then tests per acceptance item. Gate every capability by role.
- **No Viewflow** (Q6). Assignments are managed directly, with plain class-based views and a
  `services.py` layer, like `biglittle` and `transitions`.
- **Never put a CSS in the `natoff` or `officer` group,** and never derive CSS access from
  group membership. Access comes from current assignments, checked on each request. See
  [Codebase facts](#codebase-facts-that-shape-the-design) 2 and 4.
- **Hide-aware flags:** to gate what a viewer sees, use `request.is_officer` (Python:
  `getattr(request, "is_officer", False)`), not the raw `request.user.is_officer`. The raw
  property drives group management and must stay raw.
- **Feature catalog:** every new page gets an entry in
  `thetatauCMT/guides/fixtures/feature_registry.json` in the same change. Verify with
  `load_feature_registry --dry-run` and `pytest thetatauCMT/guides`. A `url_name` must answer
  a GET (link the page hosting a POST-only control, with `url_fragment`). See
  [feature-registry.md](feature-registry.md).
- **Anonymizer:** register every new model in `anonymizer/support.py` in the same step as
  `makemigrations`, or `core/tests/test_anonymizer.py` fails.
- **Wording:** see S1. Every form submission shows a specific success message.
- **Front end:** no inline `<script>` blocks or inline event handlers in new templates; pass
  data with `json_script` and use a static JS file. Everything must work in the light, dark
  and system themes.
- **Housekeeping:** scoped `makemigrations support users` (so known third-party drift is not
  generated). Run black and flake8 on the files you touched only.
- **Test gotchas** (from the big-little build, still current):
  - The `auto_login_user` fixture creates the RMP signature the middleware demands. A CSS
    fixture needs one too (CSSs sign the RMP, Q5), plus a confirmed TOTP device, because
    CSSs must use two-factor sign-in (Q19, CSSWI-11).
  - `UserFactory` leaves `current_status` blank. Pass `status=`.
  - Two `ChapterFactory()` calls can return the same chapter. Pass `name=` with a real
    `GREEK_ABR` value such as `"alpha"`, `"beta"`, `"delta"` or `"epsilon"` (there is no
    `"gamma"`). A chapter whose name is not in `GREEK_ABR` also needs `greek=`.
  - CSS test helpers live in `thetatauCMT/support/tests/factories.py`: `central_office()`,
    `give_css_role(user)`, `make_css()` (a non-member CSS in Central Office),
    `ChapterSupportAssignmentFactory` and `SupportDigestEntryFactory`.
  - Superuser tests need `@override_settings(DEBUG=True)` to get past the 2FA middleware.
  - Known order-dependent flaky tests exist (see
    `.github/copilot-memory/thetatauCMT-status.md`); re-run the file alone before blaming a
    change.

## Codebase facts that shape the design

Checked against the code on 2026-10-22.

1. **National Officers already "become" a chapter's Regent.** The region bar in
   [base.html](../../thetatauCMT/templates/base.html) shows for `natoff` group members. Its
   form ([`UserAlterForm`](../../thetatauCMT/users/forms.py): every active chapter, plus an
   optional officer role) posts to `users:alterchapter`
   ([`UserAlterView`](../../thetatauCMT/users/views.py)), which keeps one
   [`UserAlter`](../../thetatauCMT/users/models.py) row per user. `User.current_chapter`
   returns that row's chapter and `User.chapter_officer()` adds its role, for `natoff` members
   only. Chapter pages read `current_chapter`, so the catalog, role guides and forms already
   follow the chosen chapter and office ([guides-qa.md](guides-qa.md)).
2. **The `natoff` group cannot be reused for CSSs.** It opens about 40 national-only views
   (`NatOfficerRequiredMixin`, `NationalOfficerRequiredMixin` in
   [core/views.py](../../core/views.py)) and 7 national-only function views
   (`group_required("natoff")`), plus the National menu, region pages, national user search,
   ballot administration, notes, event approvals, contact sync, sensitive profile fields and
   the "Hide national officer functionality" toggle.
3. **Officer access is checked four ways** (about 80 references in 34 files):
   - Mixins: `OfficerRequiredMixin` (groups `officer` or `natoff`) on 16 views (ballots 2,
     forms 11, tasks 1, users 2), plus 3 function views behind `group_required("officer")` or
     `group_required(["officer", "natoff"])`.
   - Middleware flags: [`check_officer` and `check_nat_officer`](../../core/utils.py) (run by
     `OfficerMiddleware` in [core/middleware.py](../../core/middleware.py)) set
     `request.is_officer`, `request.is_nat_officer` and `request.in_natoff_group`. Menus, the
     chapter page, roster buttons, events and forms templates read them.
   - Group properties on `User`: `is_officer_group` and `is_chapter_officer_group`. Used by the
     member picker (`UserAutocomplete` returns nothing without them, which would empty the
     member dropdown on every officer form), the profile page, attendance, awards, Bigs and
     Littles, transitions, and `UserRoleChange.can_be_edited_by`.
   - Role checks through `chapter_officer()`: task sign-off (`TaskCompleteView`), the Audit and
     NME program forms (both call `Task.mark_complete(current_roles=...)`, which completes the
     task owned by that role), and role guides (`guides.services.get_duty_roles`).
4. **Group membership follows real roles automatically.** `UserRoleChange.save()` puts anyone
   whose raw `User.is_officer` is true in `officer`, and anyone holding a role in `NAT_OFFICERS`
   in `natoff`; `clean_group_role()` removes them later. So the CSS role must stay out of
   `NAT_OFFICERS` and `COUNCIL`, and "standing in as Regent" must never feed the raw
   `User.is_officer`, or a CSS would land in a group and keep access everywhere.
5. **About 10 places read the viewer's own chapter (`user.chapter`) instead of
   `current_chapter`:** `User.contact_visible_to`, `TransitionsListView.dispatch` and
   `transitions.services.can_view_chapter_dashboard`, `AuditFormView.get_success_url`, the
   chapter vote in `BallotCompleteCreateView` (2), `biglittle.services.can_view_tree`, and the
   switcher's Reset (deliberately the home chapter). Some already show a National Officer
   their own chapter instead of the one they switched to; a CSS would hit them every day.
6. **Real roles still decide some Regent powers:** the chapter's ballot vote
   (`BALLOT_CHAPTER_ROLES = ["regent", "scribe"]`, read from `current_roles` and
   `user.chapter`), reading every officer's submitted transition reports
   (`transitions.services.get_readable_reports`, behind `can_read_report`) and closing a
   vacant one (`can_close_na_vacant`, `get_vacant_obligations_for_closer`), all through
   `"regent" in current_roles`; the transition-report obligations themselves (one per real
   position holder); and workflow tasks assigned to a named person: Disciplinary "Submit
   Form 2" (`DisciplinaryProcessFlow.chapter_regent`) and the "Officer1 Sign" and "Officer2
   Sign" tasks of the Convention, OSM and Resignation flows (all in
   [forms/flows.py](../../thetatauCMT/forms/flows.py)). Staff can reassign any of these to any
   user (`ReassignTaskView`). Because these read `current_roles`, a National Officer viewing a
   chapter as Regent does not get them either.
7. **Every account must have a chapter.** `User.chapter` is a required foreign key. About 70
   of the roughly 110 `Chapter.objects` references in app code skip inactive chapters
   (`exclude(active=False)` or `active=True`), including the scheduled officer emails
   (`monthly_chapter_officer_email`, `officer_update_reminder_email`, `chapter_pledges_check`).
   Production already has an inactive "Central Office" chapter, which Q8 uses as the home
   chapter for non-member CSS accounts.
8. **Faculty advisors are the nearest existing non-member account, and they are
   single-chapter.** Chapter officers add them on the chapter page
   (`ChapterDetailView.faculty_form_valid`) with status `advisor` and a badge number from 7000
   to 7999 (`Chapter.next_advisor_number`), and can remove them there. `advisors_in()` lists
   every status-`advisor` account as "Faculty Advisor" in the advisor lists.
9. **The RMP middleware asks almost everyone.** `User.requires_rmp` is true for every status
   except the alumni ones (alumni only while they hold a role), so faculty advisors sign each
   semester today, and a CSS would too unless exempted (Q5). `RMPSignMiddleware` also shows
   officers the NME program banner, using real roles only (S13).
10. **A free-text Support Specialist already exists.** `Chapter.support_specialist` (rich text,
    added 2026-07-28, edited in Django admin only) shows on the chapter page as "Chapter
    Support Specialist:" (Q11).
11. **The Regional Director is the closest "one person, many chapters" pattern.**
    `Region.directors` links users to regions (`User.director_regions`), and transitions uses
    it to let an RD read every chapter in their region (`can_view_chapter_dashboard`). A CSS
    needs the same idea one level down: users linked to chapters, with dates.
12. **Regent emails go through a few helpers on
    [`Chapter`](../../thetatauCMT/chapters/models.py):** `council_emails()` (the 5 executive
    officers' emails plus every generic chapter address), `get_email_specific(roles)` (the
    named roles' generic addresses plus the holders' personal and school emails),
    `get_generic_chapter_emails()` and `get_current_officers_council_specific()`. Four sends
    build their lists by hand. No opt-out filter applies to officer emails. Full list in
    [Email inventory](#email-inventory).
13. **`council_emails()` also feeds a list that is not an email:** the shingle order sheet's
    "Notify" column (`chapters/management/commands/update_shingle_contacts.py`), so adding
    CSSs inside `council_emails()` would change that sheet too (Q16).
14. **Settings live in Config.** `Config.get_value(key)`; `core.models.resolve_config_actor()`
    turns a username, email or National Officer role name into one user (Volunteer
    Nominations and Awards use it). `CSS_MANAGERS` needs a list version of it.
15. **Role names must be in `core.models.ALL_ROLES`** for role guides (`RoleGuide.role`) and
    registry `roles` targeting. Chapter-officer role forms offer `CHAPTER_ROLES_CHOICES`, not
    `ALL_ROLES`, so adding the CSS role to `ALL_ROLES` does not let chapter officers assign
    it. `ALL_ROLES_CHOICES` does feed `UserRoleChange.role` (Django admin, the `user_role`
    command) and `tasks.Task.owner`.
16. **The catalog audience comes from groups.** `guides.services.user_audience` returns
    `officer` when `is_officer_group` is true; role guides come from `chapter_officer()` plus
    `current_roles`. Once CSSWI-2 is in, a CSS standing in as Regent sees the officer catalog
    and the Regent guide with no guides change.
17. **Performance.** `base.html` evaluates `request.user.current_chapter` 11 times per page,
    and each call costs at least one query (more for National Officers). CSS checks add
    assignment lookups, so compute them once per request and cache them on the user object.
18. **Accounts are created by staff.** Self sign-up is off (`ACCOUNT_ALLOW_REGISTRATION` is
    false). Social sign-in, where configured, links to an existing account with the same
    email (`SocialAccountAdapter.pre_social_login`).

## Proposed design

Updated for your answers (2026-10-22). Open follow-up questions are noted where they matter.

### Data model (CSSWI-1)

```text
core.models
  CSS_ROLE = "chapter support specialist"
  SUPPORT_ROLES = {CSS_ROLE}     # added to ALL_ROLES only. Never in NAT_OFFICERS, COUNCIL,
                                 # CHAPTER_OFFICER, CHAPTER_ROLES, ADVISOR_ROLES or ALL_OFFICERS
  CSS_STANDS_IN_AS = "regent"

users.UserStatusChange.STATUS
  + css = ("css", "Chapter Support Specialist")                        # Q7

users.User.chapter     non-member CSS accounts: the chapter named by CSS_HOME_CHAPTER
                       (default "central-office", inactive, Q8 and Q23); member CSSs keep
                       their own (Q9)

support.ChapterSupportAssignment                                       # built (CSSWI-1)
  user            FK users.User, related_name="support_assignments"
  chapter         FK chapters.Chapter, related_name="support_assignments"
  start           date, default today
  end             date, blank = open-ended                               # Q10
  notes           text, blank, managers only
  created_by      who assigned it ("Assigned by"); ended_by: who set the end date
  created, modified
  constraints     one open assignment per (user, chapter); end not before start
  validation      no overlapping dates for the same person and chapter; not the CSS's own
                  member chapter (S15); when the assignment is made or moved, the chapter
                  must be active and the person must hold the CSS role on the start date
                  (so an assignment can still be ended after its chapter closes)
  queryset        .current(on), .upcoming(on), .ended(on); on defaults to today
  (no "receives emails" switch: Q15)

support.SupportDigestEntry                                             # built (CSSWI-1; Q14, Q25)
  user            FK users.User (the CSS), related_name="support_digest_entries"
  chapter         FK chapters.Chapter, related_name="support_digest_entries"
  kind            which email it was (S16): one code per Email inventory row, with E3
                  split into workflow_update and workflow_escalation
  subject         the email's subject
  body_html       the rendered email; kept only for digest-only emails
  link            optional link back into the CMT
  realtime        true when the CSS was already on CC (S17)
  created         when the email went out
  daily_sent_at, monthly_sent_at    when it went out in a digest (empty until then)

users.UserAlter        no change: stores the chapter a CSS is viewing (role stays empty)
configs.Config         CSS_MANAGERS (Q6), CSS_HOME_CHAPTER (Q23, default "central-office"),
                       CSS_REALTIME_EMAILS (S16), NATOFF_2FA_REQUIRED_FROM (Q27, CSSWI-11)
```

A person is a CSS while they hold the dated CSS role (a `UserRoleChange` row, which also puts
it on their profile and drives the role guide). Their current assignments say which chapters
they serve. Ending the role ends all access, whatever the assignments say.

*Build notes (2026-10-22):* assignments follow the `biglittle` convention (timestamps plus
`created_by` and `ended_by`) instead of `simple_history`. Assignments are ended rather than
deleted, so the rows themselves are the history, and admin edits also land in Django's admin
log. Both tables are dropped from anonymized database copies, the same as role changes
already are.

### Which chapter a CSS is viewing

Worked out once per request and cached on the user object (fact 17):

1. A National Officer: unchanged. The national branch always wins (S7).
2. A CSS: the chapter in their `UserAlter` row, if it is a current assignment (or their own
   member chapter, for a member, Q9). Otherwise their own member chapter, for a member.
   Otherwise their first current assignment by name. Otherwise the home chapter (Central
   Office), with no officer access (S8). Reset clears the `UserAlter` choice, which lands them
   on the same fallback.
3. "Standing in as Regent" means: a CSS whose viewed chapter is a current assignment (and not
   their own member chapter).

A posted chapter that is not a current assignment is refused by the switcher, and a stale
`UserAlter` row (for example after an assignment ends) is ignored by rule 2.

### How each kind of check learns about CSSs (CSSWI-2 and CSSWI-3)

Standing in as Regent decides what a CSS can **see**. A separate rule (below the table) stops
them changing anything.

| Kind of check | Today | Change |
|---|---|---|
| `User.current_chapter` | National Officers: the `UserAlter` chapter | CSS: the rules above |
| `User.chapter_officer()` (altered) | Real roles, plus the National Officer's `UserAlter` role | Adds `regent` while standing in |
| `User.chapter_officer(altered=False)`, `User.is_officer` | Real roles | No change (fact 4) |
| `User.is_officer_group`, `User.is_chapter_officer_group` | Group membership | Also true while standing in |
| `request.is_officer` | `officer` or `natoff` group | Also set while standing in. New raw flag `request.is_css` for the bar, and `request.css_view_only` |
| `OfficerRequiredMixin`, `group_required("officer")` | Group membership | Also pass while standing in |
| National checks: `natoff` group, `is_national_officer_group`, `user_is_national_officer`, `request.is_nat_officer` | National Officers and Admins | No change. Never true for a CSS |
| Viewer's own chapter (fact 5) | `user.chapter` | Fixed one by one in CSSWI-3 |
| Real-role powers (fact 6) | `current_roles` | Reading reports only (Q2, Q20); no vote (Q3); no named tasks (Q4, Q21) |

**View only (Q1).** A new `ViewOnlyCSSMiddleware` refuses POST, PUT, PATCH and DELETE from a
CSS who is standing in, except the personal allow-list in Q22 (by URL name), with the S14
message. The HTTP method alone is not enough: the roster's "Email ALL" sends emails from a
normal page load (`UserListView.get` with `?email=Email All`), so that view checks
`request.css_view_only` itself. The contact-sync OAuth callback also writes on a page load,
but only to the user's own account, which Q22 allows. A guard test lists every view that
writes on a GET, so a new one cannot slip past.

### Emails (CSSWI-6)

One helper, `Chapter.support_specialist_emails()`: the emails of CSSs with a current
assignment to the chapter. CSSs are never merged into `council_emails()` or
`get_email_specific()`, which most sends use for To. Instead each of the 14 sends below calls
one helper, `notify_support(notification, chapter, kind)`, which looks up whether `kind` is
time-sensitive (the Config setting `CSS_REALTIME_EMAILS`, S16):

- **Time-sensitive** (Q25 C; "CC as sent" below): the chapter's CSSs go on that email's CC,
  and a short `SupportDigestEntry` (subject and link) is recorded, so the daily digest can list
  it too (S17).
- **Everything else** ("Daily digest" below): no CC. The `SupportDigestEntry` keeps the
  email's subject and rendered body, so the daily digest carries its content.
- `council_emails(include_support=False)` gains a flag; only the shingle sheet's "Notify"
  column passes `include_support=True` (Q16), because a sheet has no CC.
- `send_css_digests --period daily` runs each morning: the previous day's entries for each
  CSS, grouped by chapter, skipped when there are none. `--period monthly` runs on the 1st:
  for each chapter, what was sent last month and what is still open (overdue tasks, missing
  officers, open ballots, forms waiting).

### Email inventory

Every email the chapter's Regent gets today, how a CSS gets it (Q25), and where the helper
is called.

| # | Email | Sent when | Regent today | CSS gets it | Where the helper goes |
|---|---|---|---|---|---|
| E1 | Monthly chapter officer email (`users.notifications.OfficerMonthly`) | `monthly_chapter_officer_email` (scheduled) | To, by `council_emails()` | Daily digest | `OfficerMonthly` |
| E2 | Dues roster and reminder (`chapters.notifications.DuesReminder`) | Dues reminders | To, by `council_emails()` | Daily digest | `DuesReminder` |
| E3 | Workflow updates with `email_officers=True` (`forms.notifications.EmailProcessUpdate`) in the forms flows, and the 14 and 30 day escalations of `remind_workflow_tasks` | Flow steps; scheduled reminders | CC, by `council_emails()` | Flow-step updates: daily digest. The 14 and 30 day escalations: CC as sent | `EmailProcessUpdate`, when `email_officers` is on |
| E4 | Award granted (`awards.notifications.grant_notification_recipients`) | An award is granted to a member or to the chapter | To, by `council_emails()` | Daily digest | The award-granted email in `awards/notifications.py` |
| E5 | NME program revision request | A reviewer asks for changes | To, by `council_emails()` | Daily digest | The send in `forms/views.py` |
| E6 | Bylaws update submitted | The chapter submits bylaws | To, by `council_emails()` | Daily digest | The send in `forms/views.py` |
| E7 | Ballot opened, and reminders (`ballots.notifications.chapter_reminder_emails`) | Ballot created; `ballot_reminders` (scheduled) | To: Regent and Scribe; from day 14 all 5 officers; from day 21 also every role holder and the RDs | CC as sent | The ballot email classes that use `chapter_reminder_emails` |
| E8 | Ballot vote receipt (`BallotVoteReceipt`) | The chapter's vote is cast | To: Regent and Scribe | CC as sent | `BallotVoteReceipt` |
| E9 | Ballot vote removed (`BallotVoteDeleted`) | The Grand Regent or Grand Scribe removes a vote | To: all 5 officers | CC as sent | `BallotVoteDeleted` |
| E10 | Expulsion notice (`forms.notifications.EmailScribeExpulsion`) | Disciplinary outcome | To: Scribe and Regent | CC as sent | `EmailScribeExpulsion` |
| E11 | Disciplinary Form 2 reminder, and the Executive Director's rejection (`DisciplinaryProcessFlow.email_regent_func`) | Trial date; Form 2 rejected | To: the Regent personally (Vice Regent if the Regent is the accused) | CC as sent | `email_regent_func` (its `extra_emails` are already CC) |
| E12 | Officer update reminder (`users.notifications.OfficerUpdateReminder`) | `officer_update_reminder_email` (daily) | To: every generic chapter address, including the Regent's, plus the officers whose terms are ending | CC as sent | `OfficerUpdateReminder` |
| E13 | PNM and initiation reminder | `chapter_pledges_check` (weekly) | To: the executive officers and every generic chapter address | Daily digest | The `GenericEmail` call in the command (it already has a CC list) |
| E14 | Transition report past due (`transitions.notifications.TransitionReportDueReminder`) | Transition reminders (scheduled), once a report is past due | To: the chapter's generic Regent address (`transitions.services._regent_emails`) | CC as sent | `TransitionReportDueReminder` |

Not sent to CSSs, because they are not addressed to the Regent as Regent: emails to whoever
filed or owns a particular item (a CSS gets these only for things they filed themselves), the
Convention credential replacement notice (to the named signers), the new-officer welcome, RD
digests and Central Office notices.

## Work items

### CSSWI-1: Role, status, models, admin, anonymizer

Waiting on: nothing.

Build:

- New app `thetatauCMT/support/` added to `LOCAL_APPS` in `config/settings/base.py`.
- `core/models.py`: `CSS_ROLE`, `SUPPORT_ROLES` and `CSS_STANDS_IN_AS` as in the
  [Data model](#data-model-csswi-1). Add `SUPPORT_ROLES` to `ALL_ROLES` only. That changes the
  role choices of `UserRoleChange`, `tasks.Task.owner` and `guides.RoleGuide`, so those apps
  get a choices-only migration too.
- `UserStatusChange.STATUS` gains `css` (Q7). Make sure no chapter-officer status form offers
  it (check the choice lists in `forms/forms.py` and `forms/filters.py`).
- `support.models.ChapterSupportAssignment` with its rules and `current()` queryset. No
  email switch (Q15).
- `support.models.SupportDigestEntry` (Q14, Q25). CSSWI-6 fills and sends it.
- `support.services.css_home_chapter()`: the chapter named by the `CSS_HOME_CHAPTER` Config
  setting (default `central-office`, Q23), with a clear error if it is missing or active.
- Admin: an assignment admin (filters: current or ended, chapter, region; search by name and
  email), an inline on the User admin, and a read-only digest entry admin.
- `anonymizer/support.py` registering both models.
- `docker exec thetataucmt_local_django python manage.py makemigrations support users tasks guides`.
- **Pause for review** before CSSWI-2.

Built 2026-10-22: `support` migration 0001 plus choices-only migrations `users` 0047,
`tasks` 0010 and `guides` 0007. The random-value test factories (`UserRoleChangeFactory`,
`UserStatusChangeFactory`) never pick the CSS role or status, so unrelated tests cannot
create a CSS by chance. The User admin inline is read-only and only appears for someone who
holds the role or has assignments.

Done when:

- [x] Migrations apply on a fresh database; `makemigrations --check --dry-run` is clean
- [x] Model rules tested: one open assignment per user and chapter, end not before start,
  no overlapping dates, active chapters only (when made or moved), not the CSS's own member
  chapter, CSS role required on the start date
- [x] Saving a CSS role `UserRoleChange` leaves the person out of `officer` and `natoff`
- [x] `anonymize_db --check_only` and `core/tests/test_anonymizer.py` pass
- [x] Your review of the models (the pause before CSSWI-2): approved 2026-10-22

### CSSWI-2: Access core and view only

Waiting on: nothing (models approved 2026-10-22).

Build:

- `support/services.py`: `is_css(user)`, `css_chapters(user, on=None)`,
  `supports(user, chapter)`, `css_viewing_chapter(user)` and `standing_in(user)`, cached on
  the user object for the request.
- `User.current_chapter` and `User.chapter_officer()`: the CSS branch from
  [Which chapter a CSS is viewing](#which-chapter-a-css-is-viewing). Keep `altered=False` and
  `User.is_officer` raw (fact 4).
- `User.is_officer_group` and `User.is_chapter_officer_group`: also true while standing in.
  Read every caller (fact 3) and note any that compare against the viewer's own chapter.
- `core/utils.py`: `check_officer` sets `request.is_officer` while standing in, and sets the
  new `request.is_css` and `request.css_view_only`. `check_nat_officer` does not change.
- `core/views.py`: `OfficerRequiredMixin.check_membership` and `group_required` pass while
  standing in.
- `ViewOnlyCSSMiddleware` (Q1) with the Q22 allow-list, the S14 message, and the separate
  check in `UserListView.get` for "Email ALL". See
  [How each kind of check learns about CSSs](#how-each-kind-of-check-learns-about-csss-csswi-2-and-csswi-3).
- Hide the change buttons for a CSS on the main officer pages (S14), using
  `request.css_view_only`.

Built 2026-10-22:

- `support/services.py` works out a CSS's state once per user object (`css_state`): whether
  they are a CSS, their current assignments, the chapter they are viewing, and whether they
  are standing in. Someone without the CSS role costs no query. The chapter viewed is the
  switcher's choice while it is a current assignment; otherwise a member CSS's own chapter;
  otherwise their first assignment by name; otherwise their home chapter.
- `User.chapter_officer()` gives `{"regent"}` only while standing in. `User.is_officer` still
  reads real roles only, so the `officer` and `natoff` groups never change for a CSS
  (fact 4).
- `check_officer` sets `request.is_css` for every CSS, and `request.is_officer` and
  `request.css_view_only` while standing in.
- `OfficerRequiredMixin` lets a CSS standing in through. So does `group_required("officer")`,
  exactly as for the Regent. The third such view, `user_verify`, uses
  `group_required(["officer", "natoff"])`, which matches no group today (the known quirk), so
  it stays closed to the Regent and the CSS alike. That quirk is not changed here.
- `ViewOnlyCSSMiddleware` refuses every POST, PUT, PATCH and DELETE from a CSS standing in
  unless the URL is a personal action (Q22) or a dashboard chart callback, which only reads.
  A script gets a JSON 403; a page gets the S14 message and goes back.
- Buttons (S14, changed during the build): rather than hiding buttons page by page, the same
  middleware marks every form on a CSS's page that posts somewhere they cannot, checking each
  form's target against the site's URL table. `base.html` then disables those forms' submit
  buttons, with the view-only message as their tooltip. This covers every page, including
  future ones, and a CSS still sees the controls the Regent sees. The roster's "Email ALL",
  which sends from a page load rather than a form, is hidden and also refused in
  `UserListView.get`.
- Two guard tests keep this true as the site grows. One walks every URL and checks that each
  officer view lets a CSS in and each National Officer view keeps them out. The other reads
  every `views.py` and fails if a new view writes on a plain page load.

Done when:

- [x] A guard test walks the URL resolver: every view whose class uses `OfficerRequiredMixin`
  lets a CSS standing in past its access check, and every view using
  `NatOfficerRequiredMixin` or `NationalOfficerRequiredMixin` redirects them. New views are
  covered automatically.
- [x] The `group_required("officer")` function views open for a CSS standing in, as they do
  for the Regent (`user_verify`'s list quirk keeps it closed to both)
- [x] Every officer form POST from a CSS standing in is refused with the S14 message and
  saves nothing; each Q22 personal action still works (tested through the switcher, Edit My
  Info and RMP signing; every allow-list name is checked to exist)
- [x] "Email ALL" on the roster sends nothing for a CSS
- [x] A hand-made `UserAlter` row pointing at an unassigned chapter grants nothing
- [x] Ending an assignment, or the CSS role, removes access on the next request
- [x] The member picker returns the viewed chapter's members for a CSS standing in
- [x] National Officer and plain officer behavior unchanged (full suite)
- [x] A CSS home page load uses no more queries than a National Officer's
- [x] Forms a CSS cannot submit are marked and their buttons disabled; the CSS's own forms
  (switcher, calendar feed) are not, and nothing is marked for the Regent

### CSSWI-3: Checks that read the viewer's own chapter or real roles

Waiting on: nothing.

Build:

- `User.contact_visible_to`: true for a CSS who supports the member's chapter (S11), and the
  member-facing help text update.
- Transitions: `TransitionsListView.dispatch` uses `current_chapter`;
  `can_view_chapter_dashboard` allows a CSS for their assigned chapters, and
  `get_readable_reports` gives a CSS standing in the Regent's reading scope for the chapter
  (Q2 b). Vacant reports are listed for them without the close control (Q20 A).
- Audit: the CSS sees the Regent's Audit and its status, and cannot file it (Q20 A).
  `AuditFormView.get_success_url` uses `current_chapter`.
- `biglittle.services.can_view_tree`: assigned chapters, not the home chapter by itself.
- Ballots (Q3): the vote page shows the viewed chapter's ballot status for a CSS standing in
  (`get_existing_vote` and `get_chapter_role` read `user.chapter` today, fact 5) and refuses
  the vote with a clear message.
- RMP (Q5 B): a CSS signs each semester, like faculty advisors, so `User.requires_rmp`
  needs no change. Check that the RMP form works for a non-member account, and that signing
  is on the Q22 allow-list. `RMPSignMiddleware` shows the reworded NME banner (S13).
- A short Edit My Info for CSS accounts (Q5).
- Workflows (Q4, Q21 A): no CSS completes a workflow task, and `ReassignTaskView`'s user
  picker leaves CSS accounts out.
- `UserRoleChange.can_be_edited_by`: the CSS role is edited by CSS managers only (S12).
- `ActiveMemberRequiredMixin` (pledge pins) stays closed to CSSs.

Built 2026-10-22:

- Contact details (S11): `User.contact_visible_to` lets a CSS see every contact field of
  members of all their assigned chapters, not only the one being viewed. The "No one"
  visibility choice and the three help texts now mention Chapter Support Specialists
  (`users` migration 0048, text only).
- Transitions: the list page follows the chapter being viewed; the chapter dashboard and the
  Regent's reading scope cover a CSS's assigned chapters; vacant reports are listed without
  the close control (Q20 A).
- Audit: after the Audit page a CSS returns to the chapter being viewed. Filing it is refused
  like any other form (Q20 A).
- Big/Little: a CSS sees the family trees of assigned chapters and never gets the manage
  controls.
- Ballots (Q3, S19): "My Ballots" lists the chapter's ballots with whether and when the
  chapter voted. The vote page says "Chapter Support Specialists cannot vote." and shows the
  same status, never the motion.
- RMP (Q5 B, S20): a CSS signs each semester, and signing is a personal action. The signed
  copy is filed under the CSS's own chapter (`support.services.own_records_chapter`), never
  the chapter being viewed, so it cannot show in that chapter's submissions or change its
  score. Without this, the archived copy and the task check-off would have followed the
  switcher.
- NME banner (S13): shown to a CSS for the chapter being viewed, as information without the
  submit link.
- Edit My Info (Q5): a CSS staff account (status `css`) gets a short page: name, pronouns,
  email and phone with their visibility, and email preferences. A member CSS keeps the full
  page.
- Workflows (Q21 A): the Reassign picker leaves CSS staff accounts out, and a posted one is
  refused, so no task can get stuck with someone who cannot complete it. A member CSS is
  still a member of their own chapter and can be given tasks there. A CSS standing in cannot
  complete any task (the middleware).
- Roles (S12): only CSS managers can edit a CSS role row: Admins, plus whoever the
  `CSS_MANAGERS` Config setting names (usernames, emails or National Officer role names, one
  per line or comma separated). It defaults to the Executive Director. A National Officer
  who has hidden their national functions is refused.
- `ActiveMemberRequiredMixin` is unchanged and stays closed to CSSs.

Done when:

- [x] Each change has a test for a CSS standing in, a CSS on an unassigned chapter, and the
  chapter's real Regent (Regent behavior is covered by the existing suites, which pass
  unchanged)
- [x] Every item in fact 5 is either fixed or noted as deliberate: contact details,
  transitions list and dashboard, the Audit return page, ballots and Big/Little are fixed;
  the national switcher's Reset still returns a National Officer to their own chapter, as
  before

### CSSWI-4: The CSS chapter switcher bar

Waiting on: nothing.

Build:

- `support/forms.py`: `CSSChapterForm`, choices from current assignments only, and
  `clean_chapter` refusing anything else.
- `support/views.py`: `CSSChapterSwitchView` (POST, `support:switch`) saving the choice in the
  user's `UserAlter` row, with a safe `next` redirect. Reset clears the choice (S3, Q23).
- A `css_switch_form` template tag, and the bar in `base.html`, shown when `request.is_css`
  and not `request.in_natoff_group`.
- The bar reads "Chapter Support Specialist: <chapter> (view only)", or the S8 message.
- The account menu's "Hide region bar" / "Show region bar" item, shown to CSSs too (S3). It
  reuses the existing browser-remembered toggle.

Built 2026-10-22: `support:switch` saves the choice in the CSS's `UserAlter` row (chapter
only, never a role), and Reset deletes the row, so the CSS falls back to their first
assignment. Leaving a chapter page lands on the new chapter's page; any other page reloads
in place. The bar has the class `tt-region-bar`, so the existing hide toggle hides it with
the National Officers' bar.

Done when:

- [x] Switching to an assigned chapter works and returns to the same page
- [x] A posted unassigned chapter is refused with a message, and nothing changes
- [x] The bar is hidden for members, officers and National Officers (a National Officer who
  is also a CSS sees the national bar)
- [x] A CSS can hide and show the bar, and it stays hidden across pages (browser check,
  2026-10-22)
- [x] The bar works in light, dark and system themes, and with the keyboard (browser check:
  Tab reaches the chapter picker, the arrow keys choose, Enter on Apply switches)

### CSSWI-5: Managing CSSs

Waiting on: nothing.

Build:

- `support.services.can_manage_css(user)`: Admins, plus `CSS_MANAGERS` entries (a list
  version of `resolve_config_actor`).
- Pages:
  - `support:list`, the directory: every CSS and their current chapters. National Officers
    read only; managers get the buttons. Linked from the National menu.
  - `support:create`: a new CSS account (name, email). Sets the status (Q7), the CSS role and
    the Central Office home chapter (Q23), and sends the password-set email. For an existing
    member (Q9), it adds the role and keeps their status and chapter.
  - `support:assign` and `support:end` for assignments, with a history of past ones.
- No emails about assignments (Q17: national sends the official notice).

Built 2026-10-22:

- `support:list` (`/support/`, the National menu's "Chapter Support Specialists"): every
  current CSS, staff or member, with their current chapters and a count of upcoming ones.
  National Officers read it; managers also get "Add a Chapter Support Specialist".
- `support:detail`: one CSS's current, upcoming and past chapters, with who assigned and who
  ended each. Managers see the notes and get "Assign a chapter", End (with an end date;
  yesterday ends it now), Cancel for one that has not started, and "Remove as Chapter Support
  Specialist" (S21).
- `support:create`: first name, last name and email. A new person gets a staff account
  (status `css`, the Central Office home chapter, the CSS role from today, and a verified
  email so the first sign-in needs no extra verification email) and a welcome email with a
  one-time set-password link (`EmailSupportWelcome`; it says nothing about chapters, Q17). If
  the email already belongs to someone, including a secondary email, they keep their account,
  status and chapter and gain the role, with no email (Q9). A switched-off member account is
  refused; a former CSS staff account is switched back on and emailed again.
- `support:assign`, `support:end` and `support:remove` are POST only and follow the model's
  rules (S2, S15, overlaps, role on the start date), showing them as messages.

Done when:

- [x] A manager can create a CSS, assign chapters and end assignments, with success messages
- [x] National Officers see the directory without buttons; everyone else is redirected
- [x] Assigning or ending sends no email
- [x] An existing member can be made a CSS without losing their membership (Q9)

### CSSWI-6: Regent emails to CSSs

Waiting on: nothing.

Build:

- `Chapter.support_specialist_emails()` and `notify_support(notification, chapter, kind)`,
  called at each of the 14 sends in the [Email inventory](#email-inventory). Time-sensitive
  kinds (Config `CSS_REALTIME_EMAILS`, S16) add the CSSs to CC; every kind records a
  `SupportDigestEntry` per CSS (Q25 C).
- `council_emails(include_support=False)`; `update_shingle_contacts` passes
  `include_support=True` (Q16 B).
- `send_css_digests --period daily|monthly`, plus two scheduled tasks (daily each morning,
  monthly on the 1st). Skips anyone with nothing to report, and marks entries as sent so a
  second run sends nothing.

Built 2026-10-22:

- `support/emails.py`: `notify_support()` and its never-failing wrapper `copy_to_support()`.
  The dedicated email classes use `SupportCopyMixin`, whose `send()` copies first:
  `OfficerMonthly`, `DuesReminder`, `EmailProcessUpdate`, `AwardGrantedNotification`,
  `BallotVoteRequest`, `BallotVoteReceipt`, `BallotVoteDeleted`, `EmailScribeExpulsion`,
  `OfficerUpdateReminder` and `TransitionReportDueReminder` (only once past due). The three
  `GenericEmail` sends (NME revision request, bylaws update, `chapter_pledges_check`) call
  `copy_to_support()` just before `send()`. `EmailProcessUpdate` takes a `support_kind`:
  `email_regent_func` passes the disciplinary kind (E11), and `remind_workflow_tasks` passes
  the escalation kind for its 14 and 30 day emails that copy the officers. A failure while
  copying is logged and never stops the officers' email.
- A digest-only entry keeps the email's own content (its `content` block), not the whole
  email layout, so the digest can show several emails in one message. Attachments are not
  repeated in the digest, which says so.
- `CSS_REALTIME_EMAILS` (Config, S16) lists kind codes such as `ballot_receipt`, one per line
  or comma separated; `none` sends everything through the digest; unset means the "CC as
  sent" rows. Config list values (this one and `CSS_MANAGERS`) are read one entry per
  paragraph, so typing one per line in the admin's editor works.
- `send_css_digests --period daily`: each CSS's unsent entries, grouped by chapter, with the
  digest-only emails in full and a closing "Already sent to you" list (S17). A day with only
  time-sensitive emails sends no digest, since the CSS has seen them all.
  `--period monthly` (sends on the 1st; `--override`, `--force`, `--dry-run`): for each
  chapter, what is still open today (officers missing on the CMT, overdue tasks, which are
  mostly forms, and open ballots the chapter has not voted on) and the month's emails in one
  line each. Workflow steps waiting on officers are not repeated, since each workflow emails
  on its own. A CSS who already got this month's digest is skipped (checked against the
  sent-email log).
- `Chapter.council_emails(include_support=False)` and `Chapter.support_specialist_emails()`;
  `update_shingle_contacts` passes `include_support=True` and now sorts the "Notify" list, so
  the sheet does not change order on every run.

Done when:

- [x] One test per row of the [Email inventory](#email-inventory): "CC as sent" rows put the
  CSS on CC; "Daily digest" rows do not, but record the body for the digest; nothing once the
  assignment has ended
- [x] Moving a kind in `CSS_REALTIME_EMAILS` changes its delivery with no code change
- [x] A CSS with two chapters gets both chapters' emails, whichever chapter they are viewing
- [x] The daily digest carries the digest-only emails in full, grouped by chapter, and lists
  the day's time-sensitive ones in one line each (S17); the monthly digest covers each chapter
- [x] Running either digest twice does not send twice
- [x] The shingle sheet's "Notify" value includes the chapter's CSSs

### CSSWI-7: CSSs on the chapter page and profiles

Waiting on: nothing.

Build:

- Chapter page: the "Chapter Support Specialist" block lists current CSSs from assignments
  (name linking to the profile, and email), replacing the text field (Q11). The text still
  shows for a chapter with no CSS assigned.
- Profile: "Chapter Support Specialist for: ..." on a CSS's profile, visible to every
  signed-in member (Q18). No badge or roll number for CSS accounts.
- CSS accounts stay out of the roster, officer lists, advisor lists and member counts.

Built 2026-10-22: `support.services.chapter_support_specialists(chapter)` (an active account
with a current assignment and the role on the day) feeds the chapter page's "Chapter Support
Specialists" line, with profile links and emails. The old text shows only when that list is
empty. The profile's header says "Chapter Support Specialist for:" with links to each current
chapter, and never shows a badge number for a staff account. Nothing was needed to keep CSSs
out of the chapter's lists: they are filtered by chapter and status, and a staff CSS belongs
to Central Office with status `css`, which no member, officer or advisor list includes. Tests
pin this down.

Done when:

- [x] Chapter page and profile tests for a member of the chapter, a member of another chapter,
  and the CSS
- [x] The roster (all filters cleared), officer list and advisor lists never show a CSS

### CSSWI-8: CSS landing page: "My Chapters" table and dashboard

Waiting on: nothing.

Build:

- `support:my_chapters`, the CSS landing page (Q12):
  - At the top, one row per current assignment with actives, PNMs, overdue tasks, balance and
    missing officers, each with a "Switch to this chapter" button (POST to `support:switch`).
    A fixed number of queries, however many chapters.
  - Below it, the region dashboard (`regions/dashboard.py`) limited to their assigned
    chapters. Today every dashboard callback trusts the scope the browser sends; the CSS
    scope must be worked out on the server from the signed-in user (an expanded callback that
    reads `request.user`), never a chapter list sent from the page.
  - Then the What's New feed, if Q24 is A.
- Signing in and the Home link open this page for a CSS (Q24 A).

Built 2026-10-22: `support:my_chapters` (`/support/my-chapters/`, also linked as "My
Chapters" in the CSS bar). The table (`support/overview.py`) mirrors `Chapter.actives()`,
`Chapter.pledges()` and the chapter's past-due incomplete tasks, plus the balance and which
of the five executive offices nobody holds, in four queries however many chapters. Each row
but the chapter being viewed has a "Switch to ..." button. The dashboard is the region
dashboard with a new `support` scope and a "Chapter" filter listing only their chapters;
`get_scope_chapters` holds a CSS who is not a National Officer to their assigned chapters
(and their own chapter if they are a member) whatever scope a request names, using the
signed-in user of the request on the server. What's New follows. Home and the after-sign-in
redirect go to this page for every CSS who is not a National Officer; a member CSS has a
"My member home page" button (`/?member=1`). The page explains when no chapter is assigned
(S8), without the dashboard.

Done when:

- [x] Only current assignments are listed, and the numbers match each chapter's own pages
- [x] The dashboard shows only assigned chapters, even when a request is edited to ask for
  others
- [x] The switch buttons work; non-CSS users are redirected
- [x] Light, dark and system themes (browser check, 2026-10-22, with the chapter filter)

### CSSWI-9: Feature catalog, role guide, seed command, docs, full test run

Build:

- Registry: entries for the switcher, the landing page, the CSS directory and CSS contact
  sync, and a `chapter support specialist` role guide that explains the role is view only
  (S4). The registry has no CSS-only audience: use the `officer` audience with
  `roles: ["chapter support specialist"]`, unless the review prefers adding a CSS audience to
  `guides.models.Audience`.
- `support/management/commands/seed_css_demo.py` (uses `core.seed_guard.ensure_seeding_allowed`):
  an inactive home chapter, one CSS with three current assignments and one ended one, safe to
  re-run.
- A deploy note in `docs/deploy.md`, and an entry in
  `.github/copilot-memory/thetatauCMT-status.md`.
- Full test run and the manual checks below.

Built 2026-10-22:

- Registry: `css-my-chapters`, `css-chapter-switcher` (My chapter area), `css-contact-sync`
  (Contacts & communication), `chapter-support-specialists` (the directory, natoff), and
  `two-factor-sign-in` (Getting started, since two-factor is now required of more people), plus
  the `chapter support specialist` role guide. A CSS standing in also keeps the Regent's
  guide, so the CSS guide points to it. See S22 for the audience question.
- `seed_css_demo`: the inactive Central Office chapter (created when missing), one CSS
  (`css.demo@css-seed.thetatau.local`, password `css-demo-password`) with three current
  assignments and one ended one. Safe to re-run, including after the demo CSS is removed.
- The four Config keys (`CSS_MANAGERS`, `CSS_HOME_CHAPTER`, `CSS_REALTIME_EMAILS`,
  `NATOFF_2FA_REQUIRED_FROM`) are in `default_configs.json` as blank, described rows, and in
  `docs/deploy.md` §5.2. §7 lists the two digest tasks and §8.3 is the upgrade runbook,
  including how to remove a lost two-factor device.
- The browser check found one problem, now fixed: the NME reminder (S13) was queued on every
  request, including the dashboard's chart callbacks, so a CSS saw it six times on the next
  page. It is now added only on page loads. Chapter officers' own NME reminder still repeats
  this way; that is older behavior and was left alone.

Done when:

- [x] Registry dry run is clean and the guides tests pass
- [x] The seed command works on a fresh database
- [x] The full suite is at baseline (2026-10-21: 3,557 passed, 16 skipped, 0 failed): after
  this work, every new and existing test passes; two older tests are flaky in parallel runs
  (`awards/tests/test_directory.py::test_filter_by_region`, a known one, and
  `transitions/tests/test_views.py::test_transitions_list_search_hides_an_unrelated_chapters_report`,
  whose random chapter name can be "eta", found in "Theta" on every page) and pass on re-run
- [x] Manual checks done (browser, 2026-10-22: the bar in three themes and by keyboard, hiding
  it, disabled buttons on the chapter page, My Chapters, and the dashboard's chapter filter)

### CSSWI-10: Officer contact sync for a CSS's chapters

Waiting on: nothing.

Build:

- A new contact-sync scope, "my assigned chapters", worked out on the server from the
  signed-in CSS (never a chapter list sent from the page). It covers the same 5 executive
  officers National Officers sync for a region (`SYNCED_OFFICER_ROLES`), and no other CSSs
  (S18).
- `contact_sync.views`: today every view is National-Officer only (`_is_natoff`). Let a CSS
  use the vCard download, Google and Microsoft sync, and weekly auto-sync for that scope only.
- A link on the landing page and in the account menu.
- Q26 B: a National Officer's region sync also includes the CSSs assigned to that region's
  chapters, once each, labeled "Chapter Support Specialist" with their chapters listed.

Built 2026-10-22: a `support` contact-sync scope ("My chapters") that always resolves from
the signed-in CSS, or, in `weekly_contact_sync`, from the token's owner, so an ended
assignment drops out of the next run. A CSS may connect Google or Microsoft, sync, turn on
the weekly sync and download the vCard (`contact_sync:support_vcard`) for that scope only;
any other scope is refused with a 403 even when the request is edited. The landing page has
an "Officer contacts" section with the existing sync dialog, and the account menu links to
it ("Sync my chapters' officers"). A region sync with every role selected ends with one
card per CSS assigned to any of the region's chapters: shown as "CSS First Last", title
"Chapter Support Specialist", and those chapters as the organization. Narrowing the sync to
particular officer roles leaves CSSs out.

Done when:

- [x] A CSS can download and sync their chapters' officers, and only those
- [x] A CSS cannot ask for a region or national scope, even by editing the request
- [x] Ending an assignment drops that chapter's officers from the next sync
- [x] A region sync lists each of the region's CSSs once, labeled, and drops a CSS whose last
  assignment in the region has ended

### CSSWI-11: Two-factor sign-in for CSSs and every National Officer

Waiting on: nothing. Independent of the other work items; can ship first.

Facts (checked 2026-10-22): the site uses `django-allauth-2fa` 0.10.0 with `django-allauth`
65.10. `core.middleware.RequireSuperuser2FAMiddleware` builds on its
`BaseRequire2FAMiddleware`, which only forces *setup* (redirects to "two-factor-setup" until a
device exists). The sign-in code is asked for by `OTPAdapter.login()` once a device exists. It
is skipped entirely when `DEBUG` is on. Google sign-in is enabled
(`allauth.socialaccount.providers.google`).

Build:

- Extend `RequireSuperuser2FAMiddleware`, renamed `Require2FAMiddleware` (update its entry in
  `MIDDLEWARE` in `config/settings/base.py`). `require_2fa` is true for superusers (as today),
  CSSs, and everyone in the `natoff` group (raw membership, so hiding national officer
  functionality does not skip it).
- Q27 A: before `NATOFF_2FA_REQUIRED_FROM`, National Officers without a device get a banner
  with a setup link instead of the redirect. With the setting empty, there is no National
  Officer requirement at all. CSSs are required from their first sign-in.
- **Test impact.** Today only superuser tests need `@override_settings(DEBUG=True)` to get past
  this middleware. Because the requirement stays off while `NATOFF_2FA_REQUIRED_FROM` is empty
  (as in tests), the existing National Officer tests keep passing. New CSS test fixtures get a
  confirmed TOTP device, and the 2FA tests set the date explicitly. (If Q27 is B, a settings
  flag that is off in the test settings does the same job.)
- **Check the Google sign-in path.** django-allauth-2fa 0.10 predates allauth 65's login
  flow. Prove that a National Officer with a device is asked for the code after signing in
  with Google. If not, closing that gap is part of this item. (allauth 65 has its own MFA,
  `allauth.mfa`; moving to it would be a separate project.)
- Admin: a short note in `docs/deploy.md` on removing a lost device in Django admin.

Built 2026-10-22: `core.middleware.Require2FAMiddleware` (renamed; its `MIDDLEWARE` entry
updated). It requires setup for superusers and every CSS (a National Officer who is also a
CSS included), and for anyone in the `natoff` group from the date in
`NATOFF_2FA_REQUIRED_FROM` (`YYYY-MM-DD`; empty or unreadable means no requirement). Before
that date a National Officer without a device sees a banner on every page with a "Set it up
now" link. Two findings while building: (1) Google sign-in already asks for the code, because
allauth 65 finishes a Google sign-in through the same adapter `login()` that
django-allauth-2fa hooks; a test proves it for a CSS, an Admin and a National Officer, so
nothing needed changing. (2) Someone who must both set up two-factor and sign the RMP would
have bounced between the two pages, so the setup page (`/setup/`) joined
`TERMS_EXCLUDE_URL_LIST`; two-factor comes first, then the RMP. CSS test fixtures get a
confirmed device (`support.tests.factories.add_totp_device`).

Done when:

- [x] A National Officer, a CSS and an Admin without a device are sent to setup (after the
  date, for National Officers); a regular member and a chapter officer are not
- [x] Each of them is asked for the code at the next password sign-in, and after Google
  sign-in
- [x] A National Officer with national functionality hidden is still required
- [x] The banner shows only before the enforcement date

## Verification

```bash
docker exec thetataucmt_local_django python manage.py makemigrations support users --check --dry-run
docker exec thetataucmt_local_django pytest thetatauCMT/support -v --tb=short
docker exec thetataucmt_local_django pytest core thetatauCMT/users thetatauCMT/chapters -q
docker exec thetataucmt_local_django pytest thetatauCMT/transitions thetatauCMT/ballots thetatauCMT/biglittle -q
docker exec thetataucmt_local_django pytest thetatauCMT/contact_sync thetatauCMT/regions -q
docker exec thetataucmt_local_django pytest core/tests/test_anonymizer.py thetatauCMT/guides -q
docker exec thetataucmt_local_django python manage.py load_feature_registry --dry-run
docker exec thetataucmt_local_django python manage.py anonymize_db --check_only
docker exec thetataucmt_local_django pytest --tb=no -q
```

Manual checks, after `docker exec thetataucmt_local_django python manage.py seed_css_demo`:

- Sign in as the CSS. You land on the "My Chapters" page; the table and the dashboard show only
  the assigned chapters.
- The bar lists only the assigned chapters and says "view only". Switch between them and check
  the header, the roster, a chapter form and the task list follow the switch. Hide the bar from
  the account menu and show it again.
- Open an officer form and try to submit it: refused with the view-only message, nothing saved.
  Try the roster's "Email ALL": nothing sent. Sign the RMP and edit your own profile: both work.
- Paste the URL of a national-only page (a region dashboard, user search): redirected.
- Edit the URL or the posted form to choose an unassigned chapter: refused.
- End one assignment as a manager; the CSS loses that chapter on the next page load.
- Run `monthly_chapter_officer_email` and `ballot_reminders` locally and check the CSS is on CC
  in the local Mailpit inbox. Then run `send_css_digests --period daily` and `--period monthly`.
- Sync the CSS's chapters' officers to a vCard download.
- Two-factor: sign in as a National Officer with `NATOFF_2FA_REQUIRED_FROM` in the future (banner)
  and in the past (setup required), then sign in again with password and with Google.
- The chapter page and the CSS profile, as a member of that chapter and as a member of
  another chapter.
- Light, dark and system themes for the bar and the new pages.

## Deployment notes

Production is PythonAnywhere (see `docs/deploy.md`, which has the full steps in §8.3). No new
Python packages.

1. `python manage.py migrate` (`support` 0001; `users` 0047 and 0048, `tasks` 0010 and
   `guides` 0007, which change choice lists and help text only)
2. No new static files this release, so `collectstatic` is not needed; Reload the web app
3. `python manage.py load_feature_registry`
4. Config rows in Django admin: `CSS_MANAGERS`, and `NATOFF_2FA_REQUIRED_FROM` (Q27).
   `CSS_HOME_CHAPTER` defaults to `central-office` (Q23) and `CSS_REALTIME_EMAILS` to the
   "CC as sent" rows (S16), so add those only to change them. Never run
   `loaddata default_configs` on production; it overrides values set in admin.
5. Two PythonAnywhere scheduled tasks for the digests: `send_css_digests --period daily` each
   morning, and `send_css_digests --period monthly` (it only sends on the 1st).
6. Announce the two-factor requirement to National Officers before the enforcement date.
7. Create the CSS accounts and assignments. Copy anything useful from each chapter's old
   "Support Specialist" text first (Q11).

## Out of scope for the first version

- Region pages or dashboards for CSSs, and anything else national (R5)
- National Officers previewing the site as a CSS (a "Chapter Support Specialist" choice in the
  region bar's role picker)
- Moving two-factor sign-in to allauth's built-in MFA (unless the Google check in CSSWI-11
  forces it)
- Two-factor for chapter officers and members
- Training portal (Open edX) access for CSSs
- Bulk assignment upload, and reports on CSS activity

## Decisions log

Answers move here from [Questions for review](#questions-for-review), with the date and any
follow-up they caused.

| # | Decision | Date | Follow-up |
|---|---|---|---|
| Q1 | **B. View only.** "They should not be able to submit anything. Chapters are still responsible for doing 'all the things'; we just want the CSSs to have visibility." | 2026-10-22 | `ViewOnlyCSSMiddleware` (CSSWI-2), button hiding (S14). Conflicts with Q2 and Q4 resolved in Q20 and Q21. Personal actions in Q22. |
| Q2 | **A. All three.** | 2026-10-22 | Under Q1 only (b), reading every officer's transition reports, is looking. Q20 asks how (a) and (c) fit. |
| Q3 | **A.** No vote; sees the chapter's ballots and whether it voted; gets the ballot emails. | 2026-10-22 | CSSWI-3. |
| Q4 | **A.** Named-officer workflow tasks do not change. | 2026-10-22 | The "Central Office can reassign it to the CSS" part conflicts with Q1: Q21. |
| Q5 | **B.** A CSS signs the RMP each semester, like faculty advisors. The rest of A stays: no ballots of their own, a short Edit My Info. | 2026-10-22 | `requires_rmp` unchanged. RMP signing and the short Edit My Info are on the Q22 allow-list. |
| Q6 | **A.** Admins plus `CSS_MANAGERS`; a CSS page; National Officers see it read only. | 2026-10-22 | CSSWI-5. |
| Q7 | **A.** New status "Chapter Support Specialist" (`css`). | 2026-10-22 | CSSWI-1. |
| Q8 | **The existing inactive "Central Office" chapter** (written as A, but it is the placeholder option B, using a chapter production already has). | 2026-10-22 | Q23 confirms details and the slug. Option B's risk text and fact 7 were corrected: the original count of inactive-chapter filters was wrong. |
| Q9 | **A.** A CSS can also be a member. | 2026-10-22 | Member CSSs keep their own chapter as home; S15 stops assigning a CSS to it. |
| Q10 | **A.** Assignments have start and optional end dates. | 2026-10-22 | CSSWI-1. |
| Q11 | **A.** The chapter page lists assigned CSSs; the old text shows only where none is assigned. | 2026-10-22 | CSSWI-7. |
| Q12 | **A and C.** A landing page for CSSs with the table at the top and the full dashboard below, for their assigned chapters, in the first release. | 2026-10-22 | CSSWI-8 now includes the dashboard, scoped on the server. Q24 confirms it is their Home page and which charts. |
| Q13 | **B.** The CSS is on CC. | 2026-10-22 | CSSs are added to each email's CC, not merged into `council_emails()` (most sends use that for To). |
| Q14 | **B, plus monthly.** "A daily digest and digests on the months so they don't miss anything." | 2026-10-22 | How digests combine with Q13's CC: Q25. `SupportDigestEntry` and `send_css_digests` in CSSWI-6. |
| Q15 | **B.** No per-chapter email switch. | 2026-10-22 | `receive_emails` removed from the model. |
| Q16 | **B and C.** CSSs go on the shingle sheet's "Notify" column, and can sync their chapters' officers into their own contacts. | 2026-10-22 | Shingle: `council_emails(include_support=True)`. Contact sync: new CSSWI-10. CSSs in National Officers' syncs: Q26. |
| Q17 | **C.** No emails about assignments; national sends the official notice. | 2026-10-22 | CSSWI-5 sends nothing. |
| Q18 | **A.** Every signed-in member sees who a chapter's CSS is. | 2026-10-22 | CSSWI-7. |
| Q19 | **B, extended.** Two-factor required for CSSs, "in fact all national officers should have it going forward". | 2026-10-22 | New CSSWI-11, independent of the rest. Rollout: Q27. |
| S3 | **Changed.** "They should have an option to HIDE the bar if they want." | 2026-10-22 | The account menu's "Hide region bar" item is shown to CSSs too (CSSWI-4). |
| Q20 | **A.** View only wins: the CSS sees the Regent's Audit, reads every officer's submitted transition reports, and sees vacant reports, but files and closes nothing. | 2026-10-22 | CSSWI-3. |
| Q21 | **A.** No exception: a CSS never completes workflow tasks, and the Reassign picker leaves CSS accounts out. | 2026-10-22 | CSSWI-3. |
| Q22 | **A.** A CSS may do anything that only touches their own account (the listed actions, including roster CSV and PDF downloads), and nothing else. | 2026-10-22 | The allow-list in `ViewOnlyCSSMiddleware` (CSSWI-2). |
| Q23 | **Confirmed.** Non-member CSS accounts live in the inactive Central Office chapter, slug `central-office`. | 2026-10-22 | `CSS_HOME_CHAPTER` defaults to `central-office`, so production needs no Config row unless the slug changes. |
| Q24 | **A.** Signing in and Home open the landing page for a CSS: the table, then the dashboard with every chart, then What's New. | 2026-10-22 | CSSWI-8. |
| Q25 | **C.** "Urgent things get notified quickly but a digest still comes to help reduce the amount of emails." Time-sensitive emails CC the CSS as sent; everything else arrives only in the daily digest; plus the monthly digest. | 2026-10-22 | Delivery column added to the [Email inventory](#email-inventory); the time-sensitive list is the Config setting `CSS_REALTIME_EMAILS` (S16); the daily digest also lists the day's time-sensitive emails (S17). `SupportDigestEntry` moved into CSSWI-1 so all the models are reviewed together. |
| Q26 | **B.** National Officers' region syncs include the region's CSSs, labeled "Chapter Support Specialist". | 2026-10-22 | CSSWI-10. |
| Q27 | **A.** Announce first: a banner until the date in `NATOFF_2FA_REQUIRED_FROM`, then enforcement. | 2026-10-22 | CSSWI-11. |

## Gotchas for the build

- **Recursion.** `current_chapter`, `chapter_officer()` and the group properties call each
  other. The CSS checks must read raw data (the role, the assignments, the `UserAlter` row),
  never the hide-aware properties, the same way `natoff_hidden` uses the raw
  `in_national_officer_group`.
- **`group_required(["officer", "natoff"])`** passes a list as its only argument, a known quirk
  (see `users/tests/test_views.py`). Keep it working when adding the CSS check.
- **The `UserAlter` row is shared** with the national switcher, and Reset clears
  `hide_natoff` and `hide_admin`. A CSS never sets those flags.
- **`Chapter.chapter_choices()`** lists every active chapter; the CSS form must never use it.
- **Emails follow assignments, not the switcher.** Do not read `current_chapter` anywhere in
  CSSWI-6.
- **View only is not just about POST.** The roster's "Email ALL" sends from a page load, and the
  contact-sync OAuth callback writes on one. Any new view that writes on a GET must be added
  to the CSSWI-2 guard test.
- **A CSS's own records follow their real chapter, not the switcher.** A personal action that
  files something under a chapter must use `support.services.own_records_chapter(user)`, not
  `current_chapter` (S20; the RMP view is the example).
- **Test Regents with `make_regent()`.** `UserFactory(make_officer=True)` first saves a
  random role, which can be a National Officer role and put the user in `natoff`; use
  `support.tests.factories.make_regent()` when a test compares a CSS with a Regent.
- **The dashboard trusts the browser's scope today.** The CSS scope must come from
  `request.user` on the server (CSSWI-8), and the contact-sync scope likewise (CSSWI-10).
