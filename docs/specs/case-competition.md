# National Engineering Case Competition (NECC)

**Status (2026-11-23):** Every question is answered (Q1 to Q27, in the
[Decisions log](#decisions-log)) and **every work item is built and tested**, Releases 1 to 3
together: NECCWI-1 to 14. The app has 182 tests of its own; the full suite passes. Nothing
reaches members until an Admin ticks "Published" on this year's competition. **Next: deploy by
Wednesday, December 2** with [deploy.md §8.4](../deploy.md#84-upgrading-into-the-case-competition-release);
the proposal window opens on **Friday, December 4**. Build-time decisions you may want to check
are S33 to S38 in [Smaller defaults](#smaller-defaults-no-answer-needed-unless-you-disagree).

**Your changes after the build (2026-11-20 to 23)** are done: Feedback 1 to 8 in the
[Decisions log](#decisions-log). To see judging, build the demo at the judging stage
(`seed_case_competition_demo --stage judging --judge <your email>`) and sign in as a demo judge
(NECCWI-8). A judge with scorecards to submit sees a counted scales icon at the top of every
page (S24).

**How to use this document**

- Answer each question in [Questions for review](#questions-for-review) on its **Answer:**
  line. "Default" is a fine answer. Add anything else under the question. Each question says
  which work items it blocks, so answer those first if you are short on time.
- [Smaller defaults](#smaller-defaults-no-answer-needed-unless-you-disagree) need no answer
  unless you disagree.
- [This year's setup](#this-years-setup-the-one-time-fixture) is what the one-time fixture
  loads. Check it for typos and anything missing; after loading, every value can be changed in
  Django admin.
- [Progress](#progress) is the tracker. Each work item updates its row and ticks its
  checklist when it lands.
- When a question is answered, the build session copies the answer into the
  [Decisions log](#decisions-log) and adjusts the work items it affects. Questions that come
  up during the build are added at the end of the questions section, dated, the same way.
- Work items are named NECCWI-n and are written so a fresh session can pick one up cold. Read
  the [Shared preamble](#shared-preamble) and
  [Codebase facts](#codebase-facts-that-shape-the-design) first.

Proposed app: `thetatauCMT.competitions`. URL prefix: `/competitions/`. URL namespace:
`competitions` (S1).

## Progress

| Item | Summary | Release | Depends on | Waiting on | Status |
|---|---|---|---|---|---|
| Spec | This document | | | | Every question answered |
| NECCWI-1 | App, models, migration, Django admin, anonymizer | 1 | | | Built, tested, reviewed |
| NECCWI-2 | Rules and permissions (`services.py`), windows and time zones | 1 | 1 | | Built and tested |
| NECCWI-3 | This year's setup: the one-time fixture `necc_2026_2027` | 1 | 1 | | Built, tested, reviewed |
| NECCWI-4 | Competition page, list, menu link, home page card | 1 | 2 | | Built and tested |
| NECCWI-5 | Taking part: intent form, contacts, participants status page | 1 | 2 | | Built and tested |
| NECCWI-6 | Submitting: entry form, files, receipts, extensions, upload on behalf | 1 | 2 | | Built and tested |
| NECCWI-7 | The one daily command (`case_competition_daily`) and chapter emails | 1 | 5, 6 | | Built and tested |
| NECCWI-8 | Release 1 wrap-up: catalog, docs, QA seed command, full test run, browser check | 1 | 1 to 7 | | Done |
| NECCWI-9 | Judges and assignments, judge emails | 2 | 6 | | Built and tested |
| NECCWI-10 | Judging pages: My Judging and the scorecard | 2 | 9 | | Built and tested |
| NECCWI-11 | Scores and selection page, CSV exports | 2 | 10 | | Built and tested |
| NECCWI-12 | Publishing results: chapter results, Regional Qualifiers page, results emails | 2 | 11 | | Built and tested |
| NECCWI-13 | Final round: qualifiers only, places, the Convention announcement | 3 | 12 | | Built and tested |
| NECCWI-14 | Release 2 and 3 wrap-up: catalog, role guide, docs, full test run | 2, 3 | all | | Done |

Build order: NECCWI-1 and 3, the model review, then 2, 4 to 8, and 9 to 14, all on 2026-11-20.
The three releases can ship as one deploy ([deploy.md §8.4](../deploy.md#84-upgrading-into-the-case-competition-release)):
judging and results pages stay empty until a round closes.

## What was asked for

| # | Requirement (owner, 2026-11-20) | Where it lands |
|---|---|---|
| R1 | Support the National Engineering Case Competition, which runs across the academic year. | All |
| R2 | Forms for each step: intent to participate, design (proposal) submission, final submission. | NECCWI-5, 6, 13 |
| R3 | The window for each step is configurable, and easy to update (Q2). | NECCWI-1, 3 (Q3, S32) |
| R4 | The case topic is configurable for each year. | NECCWI-1, 3 |
| R5 | The judges are set for each round. | NECCWI-9 (Q16, Q17) |
| R6 | Judges fill out scores and feedback per the rubric. | NECCWI-10 (Q18, Q19) |
| R7 | The rubric can change; this year's is in the announcement. | NECCWI-1, 3 |
| R8 | A few projects are selected to advance, and only they make a final submission in the spring. | NECCWI-11, 13 (Q20) |
| R9 | The selected first-round submissions become visible to other chapters, but not until judging is complete. | NECCWI-12 (Q21, Q22) |
| R10 | The final winners are announced at Convention. | NECCWI-13 (Q23) |
| R11 | Reminders of the submission windows to chapters that opted in and have not submitted; for the final round, only to the selected chapters. | NECCWI-7, 13 (Q13 to Q15) |
| R12 | A way to add this year's chapters by hand, from your own list of those who intend to submit: in Django admin, nothing fancy (Q9). | NECCWI-1 (built) |
| R13 | A plan with questions to answer before full development starts. | This document |
| R14 | (Q3) Set up in Django admin; this year's setup is a one-time fixture of what was taken from the announcement. The rubric is stored in a model and can change from year to year. | NECCWI-1, 3 (built) |
| R15 | (Q6) Anyone in the chapter can declare intent, and update it later to add the main contacts in charge of the submission. | NECCWI-2, 5 |
| R16 | (Q14) Everything scheduled runs in one daily management command, like the other daily commands. | NECCWI-7 |

## The idea in one paragraph

Each year national sets up one competition in Django admin: the case, the intent window, and two
judged rounds (the proposal and the final submission), each with its own window, rubric and
list of files to collect. This year's setup is loaded once from a fixture. Any member of a
chapter can declare its intent and name the main contacts, or an Admin adds the chapter in
Django admin. During the proposal window, any member of the chapter uploads the proposal; the
files are stored under addresses nobody can guess. One daily command emails participating
chapters that have not submitted, before the window opens, when it opens and as it closes.
When the window closes, the round's judges score each proposal against the rubric on a
scorecard. Managers see the scores ranked within each region, confirm the Regional Qualifiers
(up to two per region and 20 in total this year) and publish: each chapter learns its result
and reads its feedback, and the qualifiers' proposals become visible to every member. The
final round repeats this for the qualifiers only, with reminders only to them, and the winners
stay hidden until a manager announces them at Convention.

## This year's timeline and the release plan

From the announcement, with what the CMT does at each point. Today is Friday, November 20,
2026, and the week of November 23 is Thanksgiving.

| Date | Competition | In the CMT |
|---|---|---|
| Sept 11 | Launch, announcement released | (past) The competition page carries the content |
| Sept 14 | Recorded overview | A key date with the recording link |
| Sept 22 | PD Chair call, live Q&A | A key date |
| Sept 28 | Intent-to-compete form due | (past) Your list is added in Django admin (Q9) |
| Dec 4 | Submission window opens | Round 1 opens; the "window is open" email |
| Dec 11, 11:59 pm Eastern | Submissions close | Round 1 closes; judging starts |
| Jan 8, 2027, 11:59 pm Eastern | Judging deadline (Q2) | Judge reminders count down to it |
| January 2027 | Regional Qualifiers announced | Managers publish the Round 1 results |
| Spring 2027 | Funded build | |
| May 21 to May 28, 2027, 11:59 pm Eastern | Final submission window (Q2, Q25) | Round 2 window, qualifiers only |
| June 25, 2027, 11:59 pm Eastern | Final judging deadline (Q2, Q25) | Judge reminders count down to it |
| Saturday, July 17, 2027 | Convention: national winners (Q2, Q23) | A manager presses "Announce winners" |

Release plan (Q1):

| Release | What it contains | When it must be live | Work items |
|---|---|---|---|
| 1. Take proposals | Setup and this year's fixture, competition page, intent and contacts, chapters added in Django admin, proposal submission, reminders | Deployed Wednesday, December 2, so this year's chapters are added and the "window is open" email goes out on December 4 | NECCWI-1 to 8 |
| 2. Judge and publish | Judges, scorecards, scores and selection, publishing results, the Regional Qualifiers page | Before judging starts, about December 14 | NECCWI-9 to 12, 14 |
| 3. Final round | Qualifiers-only window and reminders, final judging, the winners at Convention | Before the spring window opens | NECCWI-13, 14 |

## Permission matrix

What your answers produce. "Members of the chapter" are its current members and PNMs (Q6 B,
S29). "National Officers" includes Regional Directors, who are in the National Officer group.
"Managers" are Admins plus the people named in `CASE_COMPETITION_MANAGERS` (Q4). Files are
stored under addresses nobody can guess, and the CMT only shows a file's link to the people
this table allows; anyone who is given the link can still open it (Q11 B).

| Capability | Members of the chapter | Members of other chapters | Judges of the round | National Officers | Managers |
|---|---|---|---|---|---|
| Competition page: case, rubric, dates, resources | Yes | Yes | Yes | Yes | Yes, also before it is published |
| Register the chapter (declare intent) | While the intent window is open | No | No | No | Admins, in Django admin, at any time (Q9) |
| Update contacts, team size and note; withdraw or rejoin | Once registered, until the last round closes (S31) | No | No | No | Admins, in Django admin |
| Submit and replace files | While the window is open, or until the chapter's extension ends (Q26) | No | No | No | On a chapter's behalf, at any time |
| Their chapter's entry, before results | View and change while the window is open | No | After the window closes | No | Yes |
| Who is taking part, and who has submitted | Own chapter | No | No | Every chapter, read only (S19) | Every chapter |
| Scores and comments, before results | No | No | Their own scorecards only | No | All |
| Their chapter's result and feedback, after results | Qualified or not, and unsigned feedback (Q21) | No | No | Result only | All |
| The qualifiers' proposals, after results | Yes (Q22) | Yes | Yes | Yes | Yes |
| Proposals that did not qualify, after results | Own chapter | No | Their round's | No | Yes |
| Final places, before the announcement | No | No | No | No | Yes |
| The winners, after the announcement | Yes | Yes | Yes | Yes | Yes |

A Chapter Support Specialist viewing an assigned chapter sees what that chapter's Regent sees,
and can submit nothing (S21). A National Officer viewing a chapter through the region bar does
not become a member of it (S29); the competition page shows them that chapter's progress, view
only.

## Questions for review

Each question shows the default the build will use. Write a letter or your own wording on the
**Answer:** line.

### A. Timing and setup (Release 1)

### Q1. Should the CMT take this year's proposals?

Blocks: the release plan, and so everything.

- **A (default):** Yes. Build in three releases (see the
  [release plan](#this-years-timeline-and-the-release-plan)): Release 1 is live on December 2,
  so chapters submit in the CMT from December 4, and judging is ready by the time the window
  closes.
- **B:** No. This year's proposals arrive by email or another form, managers upload them on
  the chapters' behalf (S7), and the CMT is used from judging on. Release 1 can then wait until
  mid-December.
- **C:** Start with next year's competition (2027-2028) and run this year outside the CMT.

**Answer:** A, yes we will need to deploy this soon.

### Q2. This year's dates

Blocks: NECCWI-3. Fill in what you know; blanks are fine for now. Every time is Eastern (S4).

| Date | Default the build uses | Your date |
|---|---|---|
| Proposal window opens | Friday, December 4, 2026, 12:00 am | |
| Proposal window closes | Friday, December 11, 2026, 11:59 pm (from the announcement) | |
| Judging deadline, for the judge reminders | Friday, January 8, 2027, 11:59 pm | |
| Regional Qualifiers published | No date needed: a manager presses Publish | |
| Final submission window | Needed before spring | Due Friday, May 28, 2026, 12:00 am |
| Final judging deadline | Needed before spring |  Friday, June 25, 2026, 12:00 am |
| Convention 2027, when the winners are announced | Only needed for Q23 B Saturday, July 17, 2026, 12:00 am | |

**Answer:** Added but remember that these need to be configurable in a way that can be updated easily

### Q3. Where is each year's competition set up?

Blocks: NECCWI-1, NECCWI-3.

The yearly setup is the case, the intent window, each round's window, rubric and list of files,
the key dates, and what chapters see when results come out.

- **A (default):** In Django admin, on one competition page with the rounds, rubric and files
  inline, plus a "Copy to a new year" action. This year's setup is loaded from the
  announcement by the build (NECCWI-3), so nobody types it in. Everything during the year
  (chapters taking part, judges, extensions, selection, publishing) is on CMT pages for
  managers. Django admin needs staff status: tell us who should have it.
- **B:** Everything on CMT pages, no Django admin. About a week more of build, so it cannot be
  ready for December 4; this year would still be loaded from the announcement.

**Answer:** A, but not loaded from the announcement but setup in the admin is fine. The rubric should be configured and stored in a model. This may change from year to year, which is fine.

### Q4. Who manages the competition?

Blocks: NECCWI-2.

Managing means setting up the year, adding chapters, giving extensions and uploading on a
chapter's behalf, choosing judges, seeing every score, choosing the qualifiers, publishing
results and announcing the winners.

- **A (default):** Admins, plus the people in a Config setting, `CASE_COMPETITION_MANAGERS`
  (usernames, emails or National Officer role names, separated by commas or new lines). Blank
  means the Professional Development Director. Other National Officers get a read-only status
  page (S19).
- **B:** Any National Officer.

**Answer:** A

### Q5. Viewflow for judging?

Blocks: NECCWI-1.

The project's guideline is to use Viewflow for approval workflows. This competition has no
approval step: many judges score many proposals at the same time, and choosing the qualifiers
compares every proposal in a region, which one workflow per proposal does not model well. Also,
the workflow task list is open to National Officers only (Codebase facts 12), so alumni or
volunteer judges would have no inbox.

- **A (default):** No Viewflow. Plain pages and a `services.py` layer, like Bigs and Littles
  and Transition Reports. Each judge gets a "My Judging" page instead of a workflow inbox.
- **B:** One Viewflow process per proposal: submitted, then a scoring task for each judge in
  parallel, then a manager decision. Judges would need access to the workflow pages, and
  choosing the qualifiers would still need a page that compares proposals.

**Answer:** A

### B. Chapters taking part (Release 1)

### Q6. Who in a chapter can declare intent and submit?

Blocks: NECCWI-2, NECCWI-5, NECCWI-6.

- **A (default):** The chapter officers, the PD Chair, and the contacts named on the chapter's
  intent. The extra roles live in a Config setting, `CASE_COMPETITION_CHAPTER_ROLES` (blank
  means `pd chair`), so they can change without a deploy. Every member of the chapter can view
  the entry (S20).
- **B:** Any member of the chapter.
- **C:** Chapter officers only.

**Answer:** B anyone can declare intent, and this can be updated to add main contacts in charge of the submission

### Q7. Can a chapter that did not declare intent still submit?

Blocks: NECCWI-2, NECCWI-6, NECCWI-7.

The announcement calls the intent "non-binding and used only for participation tracking and
judging-load planning".

- **A (default):** Yes. Any active chapter can submit while the window is open, and submitting
  registers it. Reminders still go only to chapters registered before then (R11).
- **B:** No. Only registered chapters can submit. A manager can register a chapter at any
  time, including during the window.

**Answer:** A

### Q8. What does the intent form ask?

Blocks: NECCWI-1, NECCWI-5.

- **A (default):** One or two contacts picked from the chapter roster (the team leads, who get
  the emails), an estimated team size, and an optional note to national. Nothing more, since it
  is non-binding.
- **B:** Also the planned scope (for example "our campus library") or the majors on the team.
  Say which.

**Answer:** A, this in mainly for us to know how many chapters are interested

### Q9. Your list of this year's chapters

Blocks: NECCWI-5.

- **A (default):** An "Add participating chapters" page where you type to search, pick several
  chapters at once, and save. Contacts can be named afterwards, by you or by the chapter.
- **B:** Your list also has contact names or emails: upload a CSV (`chapter`, `contact_email`),
  with a review step for any row that does not match a chapter or a member.
- **C:** Send the list to the build session, and it is loaded once by a command.

Also: should the chapters you add get the welcome email (registered, key dates, where to
submit; E1)? Default: yes, with a box on the page to untick.

**Answer:** Ideally if I could just manually add these in admin nothing fancy needed.

### C. Submissions (Release 1)

### Q10. What does a proposal submission include?

Blocks: NECCWI-1, NECCWI-6.

- **A (default):** A project title, a short summary (up to 1,000 characters), the proposal file
  (PowerPoint or PDF, S8), and an optional team list: members picked from the chapter roster,
  each with their role on the team. Judges see each team member's major and class year from the
  CMT, which helps with the "Team & Chapter Engagement" criterion.
- **B:** The title, summary and file; no team list.
- **C:** The file only.

**Answer:** A

### Q11. How private are the files?

Blocks: NECCWI-1, NECCWI-6.

Every file uploaded to the CMT today can be opened by anyone who has its link, with no sign-in
(Codebase facts 3). The proposals must stay hidden until results are published (R9).

- **A (default):** Private. Competition files are stored privately. Every download first checks
  who is asking, then hands out a link that stops working after 15 minutes. Emails link to CMT
  pages, never to files.
- **B:** Stored like other CMT uploads, but under names nobody can guess. Anyone who is given a
  link can still open it, forever.

**Answer:** B

### Q12. What does the final (spring) submission collect?

Blocks: NECCWI-13 only; this can wait until spring.

The announcement says "Additional information will be provided to qualifying chapters." Each
round has its own list of items, so this is setup, not build.

- **A (default):** A final report (PDF, required), a final presentation (PowerPoint or PDF,
  required), a grant spending summary with receipts (PDF or spreadsheet, required), and an
  optional video link.
- **B:** Something else (write it in).

**Answer:** A

### D. Emails (Release 1)

### Q13. Who gets a chapter's competition emails?

Blocks: NECCWI-7.

That is, the reminders, the receipts and the results.

- **A (default):** The contacts named on the intent, plus whoever holds the Regent role and the
  roles in `CASE_COMPETITION_CHAPTER_ROLES` (the PD Chair, Q6), plus the chapter's generic
  Regent address. Replies go to the competition contact (the Professional Development
  Director). The chapter's Chapter Support Specialists get them in their daily digest (S21).
- **B:** The named contacts only; the Regent and the PD Chair only when no contact is named.
- **C:** All five chapter officers, the PD Chair and the contacts.

**Answer:** A and C

### Q14. The reminder schedule for chapters that have not submitted

Blocks: NECCWI-7.

Only registered chapters that have not withdrawn and whose entry is not complete. For the final
round, only the qualifiers (R11).

- **A (default):** 7 days before the window opens, when it opens, 3 days and 1 day before it
  closes, and on the closing day ("closes tonight at 11:59 pm Eastern"). The steps are
  settings on each round (`7` before opening; `3,1,0` before closing). A step missed because
  the chapter joined late, or a daily run did not happen, is skipped, never sent late.
- **B:** Only when it opens and on the closing day.
- **C:** Another schedule (write it in).

This year's window is one week long, so a "7 days before closing" step would land on the
opening day; the default does not have one.

**Answer:** A and this should all be contained in one command that can be run daily like the other managment commands. Only one command

### Q15. The other emails

Blocks: NECCWI-7, NECCWI-9, NECCWI-12.

The [Email inventory](#email-inventory) also has: a welcome when a chapter registers, a receipt
after each submission, a summary to managers when a window closes, "judging is open" and
reminders for judges, the results, and the winners.

- **A (default):** All of them, as listed.
- **B:** All except the ones you strike (list their E numbers).

**Answer:** A

### E. Judging (Release 2, needed by about December 11)

### Q16. Who can be a judge?

Blocks: NECCWI-9.

- **A (default):** Anyone with a CMT account: alumni, volunteers, National Officers, staff. A
  manager picks the judges by name for each round.
- **B:** Also people with no CMT account, such as industry partners. A manager enters a name
  and email, which creates a judging-only account in Central Office (the way non-member Chapter
  Support Specialist accounts are made), and the judge sets a password from an email. More
  build, which has to start at once to be ready by December 12.
- **C:** Like B, but each outside judge gets a private link and never signs in.

**Answer:** A

### Q17. Which proposals does each judge score?

Blocks: NECCWI-9.

- **A (default):** Every judge in the round scores every proposal, except their own chapter's
  (S11). Fair and simple with a small panel: with about 30 proposals, about 30 scorecards each.
- **B:** Managers assign proposals to judges, with an "assign N judges to each proposal" button
  that spreads the load evenly. Better for a large field, but totals from different mixes of
  judges compare less fairly.
- **C:** By region: each judge takes one or more regions.

**Answer:** A

### Q18. How is each criterion scored?

Blocks: NECCWI-3, NECCWI-10.

- **A (default):** A whole number from 1 to 5 for each criterion (1 Poor, 2 Fair, 3 Good,
  4 Very good, 5 Excellent), every criterion counting the same. A judge's total is the sum:
  out of 35 for the proposal (7 criteria) and out of 25 for the final (5 criteria). A
  proposal's score is the average of its judges' totals.
- **B:** 0 to 10 for each criterion, every criterion counting the same.
- **C:** A different maximum for each criterion, so some count more, for example Technical
  Rigor & Analysis out of 20 and Team & Chapter Engagement out of 5. Write the points.

The maximum is a setting on each criterion, so it can change in any year without a deploy.

**Answer:** A

### Q19. What does a judge write?

Blocks: NECCWI-10.

- **A (default):** An optional comment under each criterion, overall feedback for the chapter
  (required), and an optional private note that only managers see. When results are published,
  the chapter sees the comments and feedback unsigned, as "Judge 1", "Judge 2" (as Q21 allows).
- **B:** The overall feedback and the private note only; no comment per criterion.
- **C:** Like A, but the judges' names are shown with their feedback.

**Answer:** A

### F. Selection and results (Releases 2 and 3)

### Q20. How are the Regional Qualifiers chosen?

Blocks: NECCWI-11.

- **A (default):** The CMT ranks the proposals by average score within each region and
  pre-selects the top two in each region. Managers review, change anything, and confirm. Ties,
  missing scorecards, and going over the overall limit (20) are flagged. Both limits are
  settings on the round.
- **B:** Managers pick by hand with the ranking shown; nothing is pre-selected.
- **C:** Automatic: the top two in each region, with no manager step.

**Answer:** A

### Q21. What does each chapter see when results are published?

Blocks: NECCWI-12.

- **A (default):** Whether it qualified, and the judges' written feedback, unsigned. No
  numbers.
- **B:** A, plus its average score for each criterion.
- **C:** B, plus its rank in its region.
- **D:** Only whether it qualified.

These are settings on each round, so the final round can differ.

**Answer:** A

### Q22. Who sees the qualifiers' proposals after results are published?

Blocks: NECCWI-12.

- **A (default):** Every signed-in member of every chapter, on a "Regional Qualifiers" page:
  chapter, region, title, summary, team and the proposal file. Proposals that did not qualify
  stay private to their chapter (R9).
- **B:** Chapter officers and PD Chairs only.
- **C:** A, plus a public page with no sign-in, for example to link from the national website.

**Answer:** A

### Q23. The final round and Convention

Blocks: NECCWI-13.

- **A (default):** After final judging, managers record first and second place, and nobody
  else can see them. At Convention a manager presses "Announce winners". From then on the
  competition page shows the winners to everyone, every finalist's final submission is visible
  to all members, each finalist sees its own feedback, and every finalist chapter gets an email.
- **B:** Like A, but the announcement happens by itself at a date and time set in advance (the
  Convention session).
- **C:** The winners are not recorded in the CMT.

**Answer:** A

### Q24. Record the results as chapter awards?

Blocks: NECCWI-12, NECCWI-13.

- **A (default):** Yes, while awards are switched on. The build adds three chapter award types:
  "NECC Regional Qualifier", "NECC First Place" and "NECC Second Place". Publishing the Round 1
  results grants the first to each qualifier, and announcing the winners grants the other two.
  They then show on chapter pages and on Award Winners like any other award.
- **B:** First and second place only.
- **C:** No awards; the results live on the competition pages only.

**Answer:** A

### Follow-up questions (2026-11-20, from your answers)

Three short ones. None of them changes the models; each says what it blocks.

### Q25. The final round's dates (from Q2)

Blocks: nothing now. The fixture uses the defaults below, and every date can be changed in
Django admin at any time.

Your dates said 2026, but the weekdays you wrote match 2027 (Friday, May 28, 2027; May 28,
2026 was a Thursday), so the fixture uses 2027. You also wrote "12:00 am", which is the very
start of a day: taken literally, the final would be due at the start of Friday, so in effect on
Thursday night.

- **Close and deadlines (default):** final submissions due Friday, May 28, 2027, at 11:59 pm
  Eastern, like the proposal; final judging deadline Friday, June 25, 2027, at 11:59 pm Eastern;
  Convention on Saturday, July 17, 2027, shown as a key date (a manager presses "Announce
  winners", Q23 A). Correct anything that is wrong.
- **When the final window opens:**
  - **A (default):** One week before it closes: Friday, May 21, 2027, at 12:00 am Eastern, like
    the proposal window. Reminders go to the qualifiers on May 14, May 21, May 25, May 27 and
    May 28.
  - **B:** As soon as the qualifiers are announced in January, so they can upload drafts all
    spring. Reminders go when they are announced, then on May 25, May 27 and May 28.

**Answer:** A

### Q26. Who can change a chapter's entry once contacts are named? (from Q6)

Blocks: NECCWI-2, NECCWI-6.

You chose B: any member of the chapter declares intent and submits, and the intent can be
updated to add the main contacts in charge of the submission.

- **A (default):** Any member of the chapter, as you answered, all the way to the close. Every
  save records who made it, replaced files are kept (managers can bring one back), and the
  contacts get the receipt (E5) after every save, so an unwanted change is noticed.
- **B:** Once a contact is named, only the contacts can change the entry (managers too, on the
  chapter's behalf). Before any contact is named, any member can.

**Answer:** A

### Q27. Who edits the setup in Django admin? (from Q3 and Q9)

Blocks: a deployment step only (NECCWI-8).

Dates, the rubric and the chapters taking part are all edited in Django admin. Today only staff
accounts can open Django admin.

- **A (default):** Admins only. The Professional Development Director and other managers use the
  CMT pages (status, extensions, uploads on a chapter's behalf, judges, scores, publishing) and
  ask an Admin to change a date or add a chapter.
- **B:** The managers too. The build adds a "Case Competition" permission group that can edit
  only the competition's tables, and the deploy gives each manager staff status and that group.
  Say who, if not the Professional Development Director.

**Answer:** A

### Smaller defaults (no answer needed unless you disagree)

- **S1.** Wording: "Case Competition" in menus; "National Engineering Case Competition" in page
  titles and emails; "NECC" where space is tight. "Proposal" for Round 1, "final submission"
  for Round 2, and "Regional Qualifier" for a chapter that advances. No em dashes in anything a
  user reads. The code lives in a new app, `thetatauCMT.competitions`, named generally so
  another national competition could reuse it.
- **S2.** One competition per academic year, each with its own case, windows, rubric, judges
  and results. Past years stay listed, with their case, qualifiers and winners.
- **S3.** Members see nothing until a manager marks the competition published; managers can
  preview it before then. No feature flag is needed.
- **S4.** Every time is entered and shown in the competition's time zone, Eastern by default,
  and labelled ("11:59 pm Eastern"), even though the site itself runs on Arizona time.
- **S5.** One entry per chapter per round. A chapter can change its details and replace files
  as often as it likes until the window closes. Judges see only the latest files; managers can
  still open the replaced ones.
- **S6.** No separate Submit button: an entry counts as submitted once the title, the summary
  and every required file are in. A receipt goes out each time a complete entry is saved (E5).
  The chapter's page shows a checklist of whatever is still missing.
- **S7.** Uploads that arrive after the close are refused, except within a 10-minute grace
  period for uploads already under way (a round setting; 0 turns it off). The deadline shown is
  still 11:59 pm. Managers can give one chapter an extension, or upload on its behalf at any
  time; both are recorded and shown to managers.
- **S8.** Proposal files are PDF or PowerPoint (.pptx or .ppt), up to 50 MB each (a setting on
  each item). The help text recommends PDF, and a link for any video rather than embedding it.
- **S9.** The slide count (10 to 20) is not checked by the CMT. Judges score the format under
  Communication & Professionalism, and a manager can mark an entry ineligible with a reason the
  chapter sees. Counting slides automatically would add two packages (`pypdf`, `python-pptx`).
- **S10.** *(Changed for Q11 B.)* Files keep the name they were uploaded with, cleaned of
  characters that do not belong in a file name, inside a folder with a random name, and open in
  a new tab. No document viewer is built into the page.
- **S11.** A judge never scores their own chapter's entry. A judge can step aside from any other
  entry (a conflict of interest), with a reason that managers see.
- **S12.** Judges score on their own: they never see other judges' scores or comments.
  Managers see everything.
- **S13.** Judges can save a scorecard as a draft, and change a submitted scorecard until the
  results are published. Drafts do not count toward the score.
- **S14.** Judging starts when the window closes, so every judge sees the final files. An entry
  with an extension reaches the judges when its extension ends.
- **S15.** The rubric locks when the first scorecard is saved, so every judge scores against the
  same criteria. A manager can unlock it in Django admin, after a warning.
- **S16.** A proposal's score is the average of its submitted scorecards' totals. Managers also
  see each criterion's average, and the spread between the highest and lowest total, to spot
  judges who disagree. No adjustment for harsh or generous judges (with Q17 A, every judge
  scores everything).
- **S17.** The per-region limit (2) and the overall limit (20) are settings on the round. An
  optional minimum average to qualify is left blank (none) this year.
- **S18.** Before publishing, a manager can hide one judge comment from the chapter, such as an
  unkind remark. It stays on record for managers.
- **S19.** Before results, National Officers (Regional Directors included) get a read-only
  status page: which chapters are taking part and which have submitted, for every chapter. No
  files and no scores.
- **S20.** *(Changed for Q6 B.)* Every member of a chapter (S29) can open their chapter's entry,
  change it while its window is open (Q26), and read it afterwards; after results, also its
  result and feedback (Q21).
- **S21.** A Chapter Support Specialist viewing an assigned chapter sees its competition pages
  as its Regent does, and cannot submit (the existing view-only rule refuses it, with no
  competition code). The chapter's competition emails reach CSSs through their daily digest, as
  a new digest kind.
- **S22.** Candidate chapters can take part. Inactive chapters cannot.
- **S23.** Any member of the chapter, or an Admin in Django admin, can withdraw the chapter,
  which stops its reminders. It can rejoin while the window is open. To let more chapters
  register themselves after the intent deadline, an Admin moves the intent close date in Django
  admin.
- **S24.** *(Your change, 2026-11-20: the Activity menu rather than the Chapter menu; judges'
  part changed 2026-11-21, Feedback 5.)* Getting there: "Case Competition" in the Activity menu
  while a published competition exists. A card on the home page for members while the intent
  window or their round's window is open and their chapter has not acted yet. For judges, as
  for ballots: while they have scorecards to submit (drafts included), a scales icon with the
  count at the top of every page and a reminder at the top of the home page, both leading to
  My Judging. "My Judging", with the same count, is in the Activity menu and the account menu
  for anyone judging a round of a published competition whose results are not out yet. The
  competition page tells a judge where each of their rounds stands, and an entry's page links
  its judge to their scorecard for it.
- **S25.** The manager pages are linked from the National menu ("Case Competition"), for
  managers, and for National Officers as the read-only status page.
- **S26.** Managers download CSV files of the chapters taking part, the entries, and every
  score (by judge and criterion). No "download every file as one ZIP" in this version.
- **S27.** *(Changed for Q3.)* This year's setup is the one-time fixture `necc_2026_2027`,
  loaded once in production with `loaddata` right after the migration. After that, and in later
  years, the setup is edited in Django admin, and "Copy to a new year" starts the next one.
  Loading the fixture a second time would put this year's setup back to the fixture's values,
  undoing changes made in Django admin.
- **S28.** Feature catalog: a new "Case Competition" area. The judge and manager pages are in it
  too, with a note in their descriptions; anyone else following those links lands on the
  competition page with a short message.
- **S29.** *(Added for Q6 B.)* "Members of the chapter" means its current members (the active
  statuses) and its PNMs, by their own chapter. Alumni and other statuses cannot submit; a
  manager can upload for them (S7). A National Officer viewing a chapter through the region bar
  does not become a member of it, so before results they see only whether it has submitted
  (S19). The competition page's chapter panel follows the region bar, as every other page does
  (Feedback 8): the chapter's registration and each round's status, view only, opening an entry
  only where the permission matrix allows.
- **S30.** *(Added for Q9.)* Chapters an Admin adds in Django admin get no email at that moment.
  The next daily run sends them the reminder due that day: before December 4, "the window opens
  on Friday" (E2); from December 4, "the window is open" (E3). Those emails say the chapter is
  registered and link to the page where any member names the contacts.
- **S31.** *(Added for Q6.)* After the intent window closes, a registered chapter can still
  update its contacts, team size and note, and withdraw or rejoin, until the last round closes.
  New registrations after the intent window come from a first submission (Q7) or an Admin.
- **S32.** *(Added for Q2.)* Every date lives on the competition and its rounds in Django admin,
  entered and shown in Eastern time. Pages follow a change at once, and emails at the next daily
  run. When a window's opening or closing moves, its reminders start over from the step due on
  the new date: no step is sent twice for the same date, and steps already past are never sent
  late.
- **S33.** *(Build, 2026-11-20.)* Awards (Q24): publishing records "NECC Regional Qualifier" for
  each qualifier quietly, without the usual award email and home-page announcement, because the
  results email (E9) already tells them and up to 20 announcements at once would crowd the home
  page. "NECC First Place" and "NECC Second Place" are announced like every other award. The
  award types are made by migration `competitions` 0002 where award types already exist (as in
  production), or by name at the first publish on a brand-new database, where
  `loaddata award_types` (fixed pks 1 to 30) would otherwise overwrite them. The grant is
  recorded as made by whoever publishes.
- **S34.** *(Build.)* Uploaded files are checked by their own structure rather than with libmagic:
  the first bytes of a PDF, image or old Office file, and the parts inside a .pptx, .docx or
  .xlsx (Gotchas 3). The same file is judged the same way on PythonAnywhere as locally, whatever
  libmagic version each has.
- **S35.** *(Build.)* An item with uploads, or a criterion with scores, still cannot be deleted
  on its own, but deleting a whole round or competition (with its entries) now works, for the
  deploy smoke test's throwaway copy (`RESTRICT` rather than `PROTECT`, migration 0003).
- **S36.** *(Build.)* Small additions to the plan: a manager's "Upload on behalf" and
  "Extension" pages per chapter and round; `scores_current` and `results_current` redirects for
  the catalog; a judge can undo stepping aside until results are published; the home card shows
  a round's window only to chapters taking part (or qualifiers), so the 100 or so other chapters
  are not nagged during the window.
- **S37.** *(Build, for Feedback 2.)* An entry's status turns at the chapter's own deadline: the
  close, or its extension. Before it, "Not started" or "In progress"; after it, or once results
  are published, "Incomplete" for an entry that was started and "Not submitted" for one that was
  not. The grace minutes (S7) do not delay the change: they only accept an upload already under
  way at the close. An extension turns an incomplete entry back to "In progress" until it ends.
- **S38.** *(Your request, 2026-11-23, Feedback 7.)* The competition contact, who gets every
  reply and is named on the competition page and in the emails' footer, is the first of: the
  `CASE_COMPETITION_CONTACT` setting (a username or email of a CMT account, a National Officer
  role or any email address; a vacant role is skipped); the competition's contact email, shown
  with the contact role holder's name; the holder of the competition's contact role; Central
  Office (central.office@thetatau.org). Managers' emails go to the people in
  `CASE_COMPETITION_MANAGERS`, else to the contact. The competition's admin page shows the
  contact now and where it comes from.

## This year's setup (the one-time fixture)

What the fixture `thetatauCMT/competitions/fixtures/necc_2026_2027.json` (NECCWI-3) loads, as
you asked (Q3): this year's setup, taken from the announcement, loaded once; later years are set
up in Django admin. After loading, every value can be changed in Django admin. The fixture loads
the competition unpublished, so it can be checked before members see it. The announcement PDF is
not in the fixture; it can be attached in Django admin as an optional download for members.

**Competition:** National Engineering Case Competition 2026-2027 (slug `necc-2026-2027`). Time
zone: Eastern. Contact: the Professional Development Director (the role, so the page follows
whoever holds it).

**Case: Reduce energy usage in your community.** "As a team you will define the community, the
baseline, and scope (campus building, a neighborhood, a process, a system, etc.)." A
competitive response will consider:

- **Scope:** Define a specific problem with a quantified baseline you can measure against.
- **Analysis:** Show engineering work such as calculations, modeling, data, or trade studies.
- **Development:** Address cost, schedule, and other constraints to utilize the $400 grant to
  prototype or demonstrate.
- **Metrics:** Tie specific, measurable success metrics back to the case objective.

**About** (purpose, timeline and awards, as rich text):

- Purpose: Engineering In Action; Skills Members Can Show; A Portfolio For Your Chapter;
  Recognition For Technical Work; Connection Across Theta Tau (the announcement's wording).
- Timeline: Case Released (September 2026); Chapter Proposal (fall semester); Regional
  Qualifiers (January 2027, up to two qualifying proposals per region advance to the
  development phase); Funded Build (spring semester, $400 to each qualifying chapter); National
  Winners (Convention 2027).
- Awards: a $400 Development Grant to each regional qualifying chapter, up to 20 chapters; a
  dues reduction for the following academic year for the national first-place chapter, and a
  smaller one for second place.

**Key dates** (shown on the page; they drive nothing):

| Date | Label | Note |
|---|---|---|
| Sept 11, 2026 | Competition launch | Announcement released. |
| Sept 14, 2026 | Recorded overview | Prerecorded walkthrough of the case, structure, dates, judging, awards, and how to participate. Link: to be added. |
| Sept 22, 2026 | PD Chair call, live Q&A | Opportunity to ask questions. |
| Sept 28, 2026 | Intent-to-compete form due | Non-binding and used only for participation tracking and judging-load planning. |
| Dec 4, 2026 | Submission window opens | Portal opens. Final office hours. |
| Dec 11, 2026 | Submissions close | Final proposals due at 11:59 pm Eastern. Portal closes. |
| May 28, 2027 | Final submissions due | Regional Qualifiers submit their final report, presentation and grant spending by 11:59 pm Eastern. |
| July 17, 2027 | National winners announced | Finalists are showcased at Convention 2027, where first and second place are announced. |

**Intent window:** September 11, 2026, 12:00 am to September 28, 2026, 11:59 pm Eastern
(closed; this year's chapters are added in Django admin, Q9).

**Round 1, Proposal.** Window: December 4, 2026, 12:00 am to December 11, 2026, 11:59 pm
Eastern. Judging deadline: January 8, 2027, 11:59 pm Eastern. Who: registered chapters (Q7).
Instructions: "Format: PowerPoint or PDF. Length: 10 to 20 slides." Items: "Proposal" (PDF or
PowerPoint, required, 50 MB). Selection: up to 2 per region and 20 in total. Reminders: 7 days
before opening; 3 and 1 days before closing and the closing day; judges 7, 3 and 1 days before
their deadline. Rubric, each criterion 1 to 5 (Q18):

| # | Criterion | Description |
|---|---|---|
| 1 | Problem Definition & Research | Problem is precisely scoped with a quantified baseline. Research draws on credible technical sources and, where relevant, stakeholder or user input. Assumptions are explicit and justified. |
| 2 | Technical Rigor & Analysis | Sound engineering fundamentals applied throughout. Calculations, modeling, or data analysis are correct, appropriately detailed, and clearly documented. Trade studies compare alternatives against quantified criteria. |
| 3 | Solution Design & Feasibility | Design is complete and practical. Constraints (cost, schedule, safety, regulatory) are identified and addressed. A realistic implementation path and budget show the idea could be executed with the $400 grant or a clearly justified plan beyond it. |
| 4 | Impact & Measurability | Projected impact is quantified against the baseline with well-considered estimates. Success metrics are specific, measurable, and tied to the case objective. |
| 5 | Innovation & Creativity | Approach is original or applies existing technology in a novel, well-justified way that clearly improves on standard solutions. |
| 6 | Communication & Professionalism | Proposal is well organized, concise, and polished. Figures, tables, and citations are professional and support the argument. Accessible to a technical reviewer from any discipline. |
| 7 | Team & Chapter Engagement | Documented participation drawing from multiple disciplines and class years, with clearly defined roles. |

**Round 2, Final submission.** Window: May 21, 2027, 12:00 am to May 28, 2027, 11:59 pm
Eastern (Q25). Judging deadline: June 25, 2027, 11:59 pm Eastern. Who: the Regional Qualifiers
only. Instructions: "Additional information will be provided to qualifying chapters." Items
(Q12): "Final report" (PDF, required), "Final presentation" (PDF or PowerPoint, required),
"Grant spending summary" (PDF or spreadsheet, required), "Video" (a link, optional); files up to
50 MB. Places: first and second. Reminders as in Round 1. Rubric, each criterion 1 to 5 (Q18):

| # | Criterion | Description |
|---|---|---|
| 1 | Execution of Development Plan | The chapter substantially executed its proposed plan within the grant period, adapting thoughtfully where reality diverged from the proposal. Grant spending is fully documented and well justified. |
| 2 | Demonstrated Results | Results are measured against the metrics proposed in Phase 1 and honestly reported, including shortfalls. Evidence (data, prototype performance, pilot outcomes) is credible and verifiable. |
| 3 | Technical Learning & Iteration | Final report shows rigorous engineering judgment: failures analyzed, design iterated, and conclusions supported by evidence gathered during development. |
| 4 | Sustainability & Path Forward | Clear, realistic plan for continuing, scaling, or handing off the project beyond the competition, including resources required. |
| 5 | Final Presentation & Report Quality | Final report and presentation are polished, well organized, and communicate the work compellingly to a multidisciplinary audience. |

## Shared preamble

Read this before starting any work item.

- **Local dev is docker.** Never use the host virtualenv.
  - Tests: `docker exec thetataucmt_local_django pytest <path> -v --tb=short`
  - Management: `docker exec thetataucmt_local_django python manage.py <cmd>`
- **Working style:** models and migrations first, then pause for review; then services, then
  views and templates, then tests per acceptance item. Gate every capability by role.
- **No Viewflow** (Q5 A): plain class-based views plus a `services.py` layer, like `biglittle`
  and `transitions`.
- **One daily command** (Q14): everything scheduled (every reminder, the window-closed summary,
  the judge emails and adding late judging assignments) runs in `case_competition_daily`. Never
  add a second scheduled task.
- **Setup lives in Django admin** (Q3): no CMT page edits the competition, its dates or its
  rubric. This year's values come from the one-time fixture (NECCWI-3).
- **Every permission check goes through `services.py`** (NECCWI-2), never through templates
  alone. Use the hide-aware checks: `core.models.user_is_national_officer(user)`,
  `user.is_admin`, and `request.is_officer` in templates. A National Officer in "view as member"
  mode is not a manager.
- **Times:** always `timezone.now()`, never `datetime.now()`. Parse and show times in the
  competition's time zone (S4; see [Gotchas](#gotchas-for-the-build) 1).
- **Emails:** django-herald `EmailNotification` classes in `competitions/notifications.py`,
  templates in `thetatauCMT/templates/herald/html/` extending `herald/html/base_email.html`.
  Send from `transaction.on_commit`, because every request runs in a transaction
  (`ATOMIC_REQUESTS`). Chapter emails use `support.emails.SupportCopyMixin` (S21).
- **Feature catalog:** every new page gets an entry in
  `thetatauCMT/guides/fixtures/feature_registry.json` in the same change. Verify with
  `load_feature_registry --dry-run` and `pytest thetatauCMT/guides`. A `url_name` must answer a
  GET, and `url_kwargs` only understands `@username`, `@chapter_slug` and `@region_slug`, so
  registered pages use the slug-free "current competition" URLs. See
  [feature-registry.md](feature-registry.md).
- **Anonymizer:** register every new model in `anonymizer/competitions.py` in the same step as
  `makemigrations`, or `core/tests/test_anonymizer.py` fails.
- **Wording:** see S1. Every form submission shows a specific success message. Empty values
  show "None".
- **Front end:** no inline `<script>` blocks or inline event handlers in new templates; pass data
  with `json_script` and use a static JS file. Everything must work in the light, dark and
  system themes.
- **Housekeeping:** scoped `makemigrations competitions support` (so known third-party drift is
  not generated). Run black and flake8 on the files you touched only, never a whole directory.
- **Test gotchas** (from the Bigs and Littles and CSS builds, still current):
  - Use the `auto_login_user` fixture. It creates the Risk Management signature the middleware
    demands.
  - `UserFactory` leaves `current_status` blank. Pass `status="active"` (or another status).
  - Two `ChapterFactory()` calls can return the same chapter. Pass `name=` with a real
    `GREEK_ABR` value such as `"alpha"`, `"beta"`, `"delta"` or `"epsilon"` (there is no
    `"gamma"`).
  - `UserFactory(make_officer=True)` first saves a random role, which can be a National Officer
    role and so put the user in `natoff`. For a plain Regent use
    `support.tests.factories.make_regent()`; for a PD Chair give the `pd chair` role explicitly.
  - Superuser tests need `@override_settings(DEBUG=True)` to get past the 2FA middleware.
  - Under `freeze_time`, Config rows created in one test share `created`, so
    `Config.get_value` (latest by `created`) is ambiguous: update the row instead.
  - Known order-dependent flaky tests exist (see
    `.github/copilot-memory/thetatauCMT-status.md`); re-run the file alone before blaming a
    change.

## Codebase facts that shape the design

Checked against the code on 2026-11-20.

1. **Nothing like this exists yet.** No app, model or template mentions a competition, a judge
   or a rubric. The nearest patterns: awards (yearly cycles and chapter-level grants,
   [awards/services.py](../../thetatauCMT/awards/services.py)); transitions (a Config-driven
   reminder ladder and uploaded attachments,
   [transitions/services.py](../../thetatauCMT/transitions/services.py)); biglittle (manager
   roles in Config, a chapter-scoped member picker); support (list-valued Config settings, the
   view-only rule and the CSS email digest).
2. **The site runs on Arizona time.** `TIME_ZONE = "America/Phoenix"` with `USE_TZ = True`
   ([base.py](../../config/settings/base.py)). Arizona has no daylight saving time, so in
   December 11:59 pm Eastern is 9:59 pm on the site's clock. Ballots already pin a deadline to
   another zone: `BALLOT_CLOSE_ZONE = ZoneInfo("America/Los_Angeles")` and `ballot_closes_at()`
   in [ballots/models.py](../../thetatauCMT/ballots/models.py).
3. **Every upload is public today.** Production stores files on Google Cloud Storage with
   `GS_DEFAULT_ACL = "publicRead"` ([production.py](../../config/settings/production.py)), so
   anyone with a file's URL can open it without signing in. Paths are predictable, for example
   `submissions/<type>/<chapter-slug>_<filename>`
   ([submissions/models.py](../../thetatauCMT/submissions/models.py)). Local dev has no Google
   credentials and uses `FileSystemStorage`.
4. **Private files with expiring links would come almost free** (not used: Q11 B chose
   stored-like-other-uploads). django-storages 1.14.6
   `GoogleCloudStorage.url()` returns a signed, expiring URL (v4) for any storage whose ACL is
   not `publicRead` while `querystring_auth` is on, signing with the service-account
   credentials the site already loads (`GS_CREDENTIALS` in base.py). The awards app streams a
   file through Django instead (`GrantArtifactDownloadView`, `FileResponse`), which is fine for
   small certificates but ties up a web worker for a 50 MB deck.
5. **No site-wide upload limit.** `FILE_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB) only decides memory
   versus a temporary file; limits are per form (5 MB in `attendance/forms.py` and
   `biglittle/forms.py`). File types are checked with django-upload-validator's
   `FileTypeValidator` (python-magic), as in `transitions.models.ReportAttachment`.
6. **The existing Submissions app does not fit.** `submissions.Submission` is a chapter-score
   submission: saving it recalculates the chapter's score for its `ScoreType`, and its files are
   public with predictable names.
7. **Tasks cannot target opted-in chapters.** `tasks.TaskDate` rows apply to every chapter of a
   school type ([tasks/models.py](../../thetatauCMT/tasks/models.py)), so competition deadlines
   are not Tasks; they live on the rounds.
8. **The Surveys app is a generic survey tool** (django-survey-and-report). Its answers are not
   tied to chapters or rounds in a way the competition could query, so the intent form is a
   plain form.
9. **The two roles involved.** "professional development director" is a National Officer role
   (`NATIONAL_OFFICER`, so in `NAT_OFFICERS`, and `core.models.resolve_config_actor` resolves
   it). The chapter "pd chair" is a committee chair role (`COMMITTEE_CHAIR`): not in the
   officer group, so `OfficerRequiredMixin` and `request.is_officer` do not cover a PD Chair
   ([core/models.py](../../core/models.py)).
10. **Member pickers.** `users:autocomplete` returns nothing unless the requester is in the
    officer or National Officer group ([users/views.py](../../thetatauCMT/users/views.py)
    `UserAutocomplete`), so a PD Chair cannot use it, and neither can an Admin who is in neither
    group. With `chapter` forwarded as `false` it searches every member.
    `biglittle:member-autocomplete` (`BigLittleMemberAutocomplete`) is chapter-scoped and open to
    any signed-in member, but it leaves out PNMs, who may be on a team.
11. **Finding role holders and their emails needs care.**
    `Chapter.get_current_officers_council_specific(roles)` only searches the five executive
    officers, so it never finds a PD Chair who is not also an executive officer. And
    `Chapter.get_email_specific(roles)` reads an `email_<role>` field with no default, so a
    committee role such as `pd chair` raises `AttributeError` (today's callers pass executive
    roles only). Use `chapter.members.filter(current_roles__contains=[role])` and
    `chapter.generic_email_for_role("regent")`
    ([chapters/models.py](../../thetatauCMT/chapters/models.py)).
12. **The Viewflow task list is for National Officers only.** `AllTaskListView` is patched with
    `NatOfficerRequiredMixin` in [core/views.py](../../core/views.py), so a judge who is an
    alumnus or volunteer would have no workflow inbox (Q5).
13. **Regions.** `Region.directors` lists each region's Regional Directors
    (`user.director_regions`). "regional director" is in `NAT_OFFICERS`, so RDs are in the
    National Officer group. A "National" region (slug `national`, from
    `regions/fixtures/national_region.json`) exists besides the geographic ones, so per-region
    limits must ignore it; candidate chapters are flagged by `Chapter.candidate_chapter`, not by
    region
    ([regions/models.py](../../thetatauCMT/regions/models.py)). The local database has 109
    active chapters (anonymized, so region names are not real).
14. **Scheduled tasks run daily only.** PythonAnywhere offers daily tasks, and weekly or monthly
    jobs gate themselves ([deploy.md §7](../deploy.md#7-scheduled-tasks-pythonanywhere-daily)).
    The transitions reminder ladder (`_current_reminder_threshold`, `last_reminder_offset_sent`)
    sends only the most urgent step crossed, so a missed day never replays old steps.
15. **Config.** `Config.get_value(key)` returns the newest row's rich text with the tags
    stripped. Lists (one value per line) need `support.services.config_list`, and
    `support.services.css_manager_ids` is the model for turning usernames, emails and role names
    into users ([support/services.py](../../thetatauCMT/support/services.py)). New keys are
    seeded in `configs/fixtures/default_configs.json` with `"pk": null`; never run
    `loaddata default_configs` in production.
16. **Chapter Support Specialists.** `ViewOnlyCSSMiddleware`
    ([support/middleware.py](../../thetatauCMT/support/middleware.py)) refuses every request
    other than GET, HEAD, OPTIONS or TRACE from a CSS viewing a chapter, except a short list of
    personal actions, and marks the page's forms so their buttons show disabled. New pages are
    covered without extra code. Regent emails reach CSSs through
    `support.emails.SupportCopyMixin`, with a `SupportDigestEntry.Kind`; adding a kind changes
    the field's choices, so it needs a `support` migration
    ([support/models.py](../../thetatauCMT/support/models.py)).
17. **Awards can record chapter results.** Award types already exist at the chapter level, cycles
    can be a year, a term or an event, and `awards.services.grant_award(award_type, cycle,
    recipient, granted_by, ...)` writes the audit trail; grants appear on chapter pages and Award
    Winners. `resolve_or_create_year_cycle(year)` finds or makes a year's cycle.
18. **Home page cards.** `core.views.HomeView` already adds "here's what's on you right now" cards
    (the Role Guide and "My Transition Report Obligations"), which is where the competition card
    goes (S24).
19. **Navigation.** [base.html](../../thetatauCMT/templates/base.html) has the Chapter, Members,
    Activity, Forms and (National Officers only) National menus. The guides have no PD Chair
    role guide.
20. **Every request is a transaction** (`ATOMIC_REQUESTS = True` in every settings file), so an
    email sent during a request that later rolls back would still have gone out.
21. **PostgreSQL 12.** `UNIQUE ... NULLS NOT DISTINCT` needs PostgreSQL 15, so a unique
    constraint over a nullable column lets duplicates through when the column is empty.

## Proposed design

### Data model (NECCWI-1)

Built in `thetatauCMT/competitions/models.py`, migrations `0001_initial` and
`0003_delete_whole_rounds` (restricted deletes, below); `0002_award_types` adds the Q24 award
types. Every model except the
email log has `created` and `modified` from `core.models.TimeStampedModel`. Every date and time
is stored in UTC, and entered and shown in the competition's time zone (S4). The rules the
database enforces are listed with each table; the others are checked when a form or Django
admin saves.

**`Competition`**: one per academic year (S2).

| Field | Type | Notes |
|---|---|---|
| `name`, `short_name` | Text | "National Engineering Case Competition", "NECC" |
| `year_label` | Text | "2026-2027" |
| `slug` | Slug, unique | "necc-2026-2027"; used in page addresses |
| `case_title` | Text | "Reduce energy usage in your community" |
| `case_description`, `about`, `resources` | Rich text | The case; purpose, timeline and awards; links |
| `announcement` | File, optional | An optional download for members |
| `contact_role` | Text | A National Officer role, checked on save; default the Professional Development Director. The `CASE_COMPETITION_CONTACT` setting overrides it (S38) |
| `contact_email` | Email, optional | Used instead of the role holder's own email |
| `time_zone` | Choice | Eastern (default), Central, Mountain, Arizona or Pacific |
| `intent_opens_at`, `intent_closes_at` | Date and time, optional | The intent window; the database refuses one that closes before it opens |
| `is_published` | Yes/no, default no | Members see the competition only when yes (S3) |
| `created_by` | User, set null | Filled in by Django admin |

**`KeyDate`**: dates shown on the page; they drive nothing. `competition`, `date`, `label`,
`description`, `link`. Ordered by date.

**`Round`**: a judged stage. Unique on (`competition`, `number`). The database refuses a window
that closes before it opens, and a judging deadline before the window closes.

| Field | Type | Notes |
|---|---|---|
| `competition`, `number`, `name` | | 1 "Proposal", 2 "Final submission" |
| `selection` | `advance` or `places` | Round 1 chooses qualifiers; Round 2 awards places |
| `eligibility` | `participants` or `advanced` | Who can submit and gets the reminders: the chapters taking part, or the previous round's qualifiers (never for round 1) |
| `instructions` | Rich text | Format, length, what to include |
| `opens_at`, `closes_at` | Date and time | The window |
| `grace_minutes` | Whole number, default 10 | S7 |
| `judging_closes_at` | Date and time, optional | The judges' deadline, for E8 |
| `score_min` | Whole number, default 1 | The lowest score per criterion (Q18) |
| `advance_per_region`, `advance_total`, `min_average_to_advance` | Optional numbers | 2, 20 and empty this year (S17) |
| `places` | Whole number, optional | 2 for the final; required when the round awards places |
| `share_feedback`, `share_scores`, `share_rank` | Yes/no | What chapters see when results come out (Q21: yes, no, no) |
| `reminder_days_before_open`, `reminder_days_before_close`, `judge_reminder_days` | Days separated by commas | "7", "3,1,0" and "7,3,1" (Q14); empty means none |
| `results_published_at`, `results_published_by` | Date and time, user | Publishing Round 1, or announcing the winners |
| `rubric_locked_at` | Date and time, optional | S15; Django admin shows the rubric read only while it is set |

**`RubricCriterion`**: `round`, `name` (unique in the round), `description`, `max_points`
(default 5; at least 1, and at least the round's lowest score), `order`.

**`SubmissionItem`**: what a round collects. `round`, `label` (unique in the round),
`description`, `kind` (`file` or `link`), `file_types` (PDF, PowerPoint, Word, Excel or CSV,
image; at least one for a file), `max_size_mb` (default 50), `required`, `order`.

**`Participant`**: a chapter taking part ("Chapters taking part" in Django admin). Unique on
(`competition`, `chapter`); `created` is when it registered.

| Field | Type | Notes |
|---|---|---|
| `competition`, `chapter` | Foreign keys | Only an active chapter can be added (S22) |
| `source` | `intent`, `admin` or `submission` | How it registered (Q7, Q9) |
| `contacts` | Many users | The main contacts in charge of the submission (Q6, Q8) |
| `team_size_estimate`, `note` | Optional | Q8 |
| `declared_by` | User, set null | Who registered it; Django admin fills it in |
| `withdrawn_at`, `withdrawn_by` | Optional | S23 |

**`Entry`**: a chapter's submission for one round. Unique on (`round`, `chapter`), and on
(`round`, `place`) when a place is set; places start at 1.

| Field | Type | Notes |
|---|---|---|
| `public_id` | UUID, unique | Used in page addresses, like `transitions` |
| `round`, `chapter` | Foreign keys | |
| `title`, `summary` | Text (200), text (1,000 characters) | Q10 |
| `submitted_at` | Date and time, optional | The first time it was complete (S6) |
| `last_saved_at`, `last_saved_by`, `last_saved_on_behalf` | | `last_saved_on_behalf` when a manager saved it (S7) |
| `deadline_override` | Date and time, optional | A manager's extension for this chapter (S7) |
| `eligible`, `ineligible_reason` | Yes/no (default yes), text | S9 |
| `advanced` | Yes/no, optional | The Round 1 decision ("Qualified") |
| `place` | Whole number, optional | Round 2: 1 or 2 |
| `decided_by`, `decided_at` | User, date and time | Who confirmed the selection |
| `manager_note` | Text | Managers only |

**`EntryMember`** (Q10 A): `entry`, `user`, `team_role`, `order`. Unique on (`entry`, `user`).

**`EntryFile`**: `public_id`; `entry`; `item` (restricted: an item with files cannot be deleted
on its own, but deleting its whole round or competition removes the entries and files too;
migration 0003); `file` or `link` (the database refuses a row with neither); `original_name`; `size`;
`uploaded_by`; `replaced_at` (empty while current); `created` is when it arrived. One current
file per (`entry`, `item`). Stored with the site's other uploads at
`competitions/<competition>/round-<n>/<chapter>/<random folder>/<file name>` (Q11 B, S10).

**`Judge`**: `round`, `user`, `added_by`, `removed_at` (a removed judge's scorecards stop
counting; nothing is deleted). Unique on (`round`, `user`).

**`Assignment`**: one entry for one judge. `public_id` (the scorecard page's address), `judge`,
`entry`, `stepped_aside_at`, `step_aside_reason` (S11). Unique on (`judge`, `entry`). Saving
checks that both belong to the same round and that the judge is not from the entry's chapter.

**`Scorecard`**: one per assignment. `feedback` (to the chapter, unsigned), `feedback_hidden`
(S18), `private_note` (managers only), `submitted_at` (empty while a draft), `total` (set when
submitted).

**`CriterionScore`**: `scorecard`, `criterion` (restricted, like `EntryFile.item`), `points` (empty in a partial draft;
between the round's lowest score and the criterion's highest, checked on save), `comment`,
`comment_hidden` (S18). Unique on (`scorecard`, `criterion`).

**`NotificationLog`**: one row per email that the daily command or a publish button sends. Its
unique `key` names what was sent, to whom and for which date, for example
`closes_soon:<round>:<chapter>:3:<close date>`, and a send whose key is already there is
skipped. Because the key includes the date counted from, moving a window's date starts its
reminders over (S32). Also `kind`, `competition`, `round`, `chapter`, `user`, `recipients` and
`sent_at`. Read only in Django admin, where deleting a row lets that email go out again. One
unique key also sidesteps PostgreSQL 12's gap with empty columns (Codebase facts 21). Receipts
(E5) go out on every complete save and are not logged.

The `support` app gains one digest kind, `case_competition` (migration `support` 0003), for the
chapter emails Chapter Support Specialists read in their daily digest (S21).

### Round lifecycle

Nothing is stored as a state; each round's state comes from its dates.

```text
 upcoming -> open ------------------------------> judging -----------------> published
           opens_at        closes_at + grace minutes          a manager publishes
           (E2 before)     (E3, E4; chapters submit)          (E6, E7, E8;     (E9, or E10 for
                                                               judges score)    the final)
```

- **Upcoming:** the round shows its dates. E2 goes out the set number of days before opening.
- **Open:** members of the chapter save entries. A chapter with an extension stays open until its
  own deadline.
- **Judging:** judges see the complete, eligible entries (an extended entry once its extension
  ends) and fill in scorecards. Managers see the scores.
- **Published:** scorecards lock. Chapters see their results as the round's settings allow, and
  the selected entries are visible to every signed-in member (Q22 A). For the final round,
  "published" is the announcement.

### Scoring and selection

- A judge's total is the sum of their criterion scores. Only submitted scorecards count, and an
  assignment the judge stepped aside from counts for nothing.
- An entry's score is the average of its counted totals. Managers also see each criterion's
  average, the number of scorecards in, and the spread between the highest and lowest total.
- Within each region, entries are ranked by score; equal scores are flagged as ties.
- Pre-selection (Q20 A) marks the top `advance_per_region` eligible entries in each region, above
  `min_average_to_advance` when it is set. If that comes to more than `advance_total`, the page
  says so and managers decide; nothing is dropped automatically.
- Publishing needs a decision (qualified or not) on every eligible entry. It warns about
  scorecards still missing and lets a manager publish anyway after confirming.

### Email inventory

"Chapter recipients" is the list from Q13 (A and C): the named contacts, the five chapter
officers, the holders of `CASE_COMPETITION_CHAPTER_ROLES` (the PD Chair when blank), and the
chapter's generic officer and chapter addresses.

| # | Email | To | When | To CSSs (digest) |
|---|---|---|---|---|
| E1 | You are registered (welcome, key dates, where to submit) | Chapter recipients | A chapter registers itself: the intent form, or its first submission. Chapters added in Django admin get the next reminder instead (S30) | Yes |
| E2 | The window opens soon | Chapter recipients of eligible chapters with nothing complete | `reminder_days_before_open` days before opening (7); skipped for a chapter welcomed (E1) in the previous 3 days | Yes |
| E3 | The window is open | The same | The first daily run after opening | Yes |
| E4 | The window closes soon, or tonight | The same, while still incomplete | `reminder_days_before_close` days before closing (3, 1, and 0 for the closing day) | Yes |
| E5 | Submission received | Whoever saved it, plus chapter recipients | Each save that leaves the entry complete, including a manager's upload on behalf | Yes |
| E6 | The window has closed: summary | Managers | The first daily run after closing: how many submitted, which registered chapters did not, a link | No |
| E7 | Judging is open | Each judge of the round | The first daily run after closing, or when a judge is added later | No |
| E8 | Scorecards due | Judges with unsubmitted scorecards | `judge_reminder_days` days before the judging deadline (7, 3, 1) | No |
| E9 | Results | Chapter recipients of every chapter with an entry in the round | When a manager publishes the Round 1 results | Yes |
| E10 | The winners | Chapter recipients of every finalist chapter | When the winners are announced | Yes |

Every email links to a CMT page, never to a file, so the CMT checks who is asking before it shows
a file's link (Q11 B: the link itself opens for anyone who has it). Replies go to the
competition contact. Every scheduled email comes from the one daily command (Q14).

### Pages

| URL | Name | Who | What |
|---|---|---|---|
| `/competitions/` | `competitions:list` | Members | Current and past competitions |
| `/competitions/current/` | `competitions:current` | Members | Redirects to the current competition (for the catalog) |
| `/competitions/<slug>/` | `competitions:detail` | Members | Case, dates, rubric, resources, and a "Your chapter" panel |
| `/competitions/<slug>/intent/` | `competitions:intent` | Members of the chapter | Register, name contacts, withdraw or rejoin |
| `/competitions/<slug>/round/<n>/submit/` | `competitions:submit` | Members of the chapter | The entry form |
| `/competitions/<slug>/round/<n>/submit/<chapter>/` | `competitions:submit_on_behalf` | Managers | The same form, on the chapter's behalf, at any time until results (S7) |
| `/competitions/<slug>/round/<n>/extension/<chapter>/` | `competitions:extension` | Managers | One chapter's extended deadline, in Eastern (S7) |
| `/competitions/current/submit/` | `competitions:submit_current` | Members of the chapter | Redirects to the open round's form (for the catalog) |
| `/competitions/entry/<uuid>/` | `competitions:entry` | As the permission matrix | One entry: details, files, and its result and feedback once published |
| `/competitions/file/<uuid>/` | `competitions:file` | As the permission matrix | Checks access, then sends the browser to the stored file |
| `/competitions/<slug>/round/<n>/results/` | `competitions:results` | As Q22 | The Regional Qualifiers, or the winners and finalists |
| `/competitions/current/results/` | `competitions:results_current` | Signed in | Redirect to the latest published results (for the catalog) |
| `/competitions/judging/` | `competitions:judging` | Judges | My Judging |
| `/competitions/judging/<uuid>/` | `competitions:scorecard` | That judge; managers read it and hide comments | One scorecard |
| `/competitions/<slug>/manage/` | `competitions:manage` | Managers; National Officers read only | Chapters taking part and their status |
| `/competitions/current/manage/` | `competitions:manage_current` | The same | Redirect (for the catalog) |
| `/competitions/<slug>/round/<n>/judges/` | `competitions:judges` | Managers | Judges and their progress |
| `/competitions/<slug>/round/<n>/scores/` | `competitions:scores` | Managers | Scores, ranking, selection, publishing |
| `/competitions/current/scores/` | `competitions:scores_current` | Managers | Redirect to the round being judged (for the catalog) |
| `/competitions/<slug>/export/<kind>/` | `competitions:export` | Managers | CSV downloads (S26) |
| `/competitions/member-autocomplete/` | `competitions:member-autocomplete` | Signed in | Chapter-scoped member picker |
| `/competitions/judge-autocomplete/` | `competitions:judge-autocomplete` | Managers | Every-member picker for judges |

## Work items

### NECCWI-1: App, models, migration, Django admin, anonymizer

Built 2026-11-20:

- New app `thetatauCMT/competitions/` (`CompetitionsConfig`, shown as "Case Competition"),
  added to `LOCAL_APPS` in `config/settings/base.py` after `support` and before
  `email_signals`.
- The models in [Data model](#data-model-neccwi-1) and migration `0001_initial`. Uploads use the
  default storage (Q11 B), each in a folder with a random name (`models.entry_file_path`).
- `SupportDigestEntry.Kind.CASE_COMPETITION` (`case_competition`, "Case Competition email") and
  migration `support` 0003; the `CSS_REALTIME_EMAILS` description lists the new code.
- Django admin (`competitions/admin.py`):
  - Every competition page runs, and is drawn, in the competition's time zone
    (`CompetitionTimeZoneMixin`; Gotchas 1), and says so at the top of its dates.
  - Competition, with key dates, rounds and "Chapters taking part" inline. Chapters and their
    contacts are typed-to-search fields; a chapter added there is recorded as added in Django
    admin, by whoever saved it (Q9).
  - Round, with the rubric and the items it collects inline. The rubric is read only while
    `rubric_locked_at` is set, with a warning on the page (S15).
  - A "Copy to a new year" action: copies the competition, key dates, rounds, rubrics and items
    one year later, keeping each time of day in the competition's zone, unpublished, with a free
    slug. Never chapters, entries, judges or scores (`services.copy_to_next_year`).
  - Admins for chapters taking part, entries (team and files inline), judges, assignments,
    scorecards (scores inline) and the email log (read only), as an escape hatch.
- `anonymizer/competitions.py`: the setup and judge rows are kept; every row holding what
  chapters and judges wrote or uploaded, and the email log, is dropped.
- Config rows `CASE_COMPETITION_MANAGERS` and `CASE_COMPETITION_CHAPTER_ROLES` in
  `thetatauCMT/configs/fixtures/default_configs.json` (blank values mean the defaults).

Done when:

- [x] Models, migration, admin, anonymizer in place;
  `makemigrations competitions support --check` is clean
- [x] The database refuses: a second entry for one chapter in one round; a second current file
  for one item; a file row with neither a file nor a link; a second scorecard for one
  assignment; a second score for one criterion; a second registration for one chapter; a
  window that closes before it opens; a judging deadline before the close; a repeated round
  number; two entries with the same place; the same logged email twice
- [x] Saving explains: a first round taking qualifiers, places missing, a contact role that is
  not a National Officer role, an inactive chapter, points out of range
- [x] Admin times round-trip in Eastern: 11:59 pm entered is stored as 4:59 am UTC the next day
  and shown as 11:59 pm (and the test fails without the time zone handling)
- [x] Chapters added on the competition page record who added them; a closed chapter is refused
- [x] "Copy to a new year" copies the setup only, keeps times of day across daylight saving time,
  and never reuses a slug
- [x] Every admin list and record page opens
- [x] `core/tests/test_anonymizer.py` passes
- [x] Pause: you reviewed the models ("Looks good. Please proceed.")

### NECCWI-2: Rules and permissions

Built 2026-11-20 in `competitions/services.py` (permissions, windows, eligibility, registering, recipients, entries, the "Your chapter" panel and the home card) and `uploads.py` (file checks, S34). Judging rules are in `judging.py`. Tests: `tests/test_rules.py`, `tests/test_uploads.py`.

Extend `thetatauCMT/competitions/services.py` (NECCWI-1 put the "Copy to a new year" code there):

- Settings: `manager_ids()` and `can_manage(user)`: Admins, plus `CASE_COMPETITION_MANAGERS`
  read with `support.services.config_list` and resolved like `css_manager_ids` (usernames,
  emails, National Officer roles; blank means `professional development director`); "view as
  member" switches it off (Q4). `email_roles()`: `CASE_COMPETITION_CHAPTER_ROLES`, kept to values
  in `core.models.ALL_ROLES`; blank means `{"pd chair"}`. It only adds email recipients (Q13);
  it grants nothing (Q6 B).
- `current_competition(user=None)`: the newest published competition; for managers, the newest
  one published or not.
- Time: `round_state(round, now=None)` (`upcoming`, `open`, `judging`, `published`),
  `deadline_for(round, chapter)` (with any extension), and `accepts_upload(round, chapter,
  now=None)` (with the grace minutes). Format with `Competition.format_time` (built).
- People: `is_chapter_member(user, chapter)` (S29: current members and PNMs, by their own
  chapter); `can_register(user, competition, chapter)` (a member, while the intent window is
  open); `can_update_participation(user, participant)` (a member, until the last round closes,
  S31); `can_submit(user, round, chapter)` (a member, as Q26 says, Q7 and the window);
  `can_view_entry(user, entry)` and `can_view_file(user, entry_file)` (the
  [Permission matrix](#permission-matrix)); `is_judge(user, round)`; `can_score(user,
  assignment)`; `can_view_status(user)` (S19).
- Who takes part: `eligible_chapters(round)` (registered and not withdrawn, for `participants`;
  the previous round's qualifiers, for `advanced`) and `register(...)`, idempotent, which also
  undoes a withdrawal; `withdraw(participant, by)`.
- `chapter_recipients(chapter, competition)` (Q13 A and C): the contacts' emails, plus
  `chapter.council_emails()` (the five officers and the chapter's generic addresses), plus the
  personal emails of whoever holds `email_roles()` in the chapter, found as Codebase facts 11
  describes.
- `entry_is_complete(entry)` and `missing_items(entry)` (S6).

Done when:

- [x] Every rule has tests, including: managers by username, email and role; the blank default;
  "view as member"; any current member or PNM may register and submit while an alumnus may not
  (Q6 B, S29); contacts can be updated after the intent window (S31); Q26 as answered; an
  unregistered chapter submitting (Q7); window edges in Eastern with the grace minutes and an
  extension; a CSS passes the viewing checks and is refused on POST by the existing middleware;
  a National Officer using the region bar sees status but no files; a judge sees files only
  after the close; nobody from another chapter sees anything before results

### NECCWI-3: This year's setup, the one-time fixture

Built 2026-11-20, as you asked (Q3): normally the setup is done in Django admin; this year it is
a one-time fixture of what was taken from the announcement.

- `thetatauCMT/competitions/fixtures/necc_2026_2027.json`: the competition (unpublished), 8 key
  dates, the intent window, and both rounds with their windows, instructions, items, rubrics and
  settings, as in [This year's setup](#this-years-setup-the-one-time-fixture). Times carry their
  Eastern offset. Fixed primary keys (1 for the competition), so it is loaded once, right after
  the migration and before anyone adds a competition in Django admin.
- No `load_competition` command (Q3). `dbseed` does not load this fixture.

Done when:

- [x] It loads, and loading it twice adds nothing
- [x] The proposal closes at December 11, 11:59:59 pm Eastern (December 12, 4:59:59 am UTC); the
  final closes at May 28, 2027, 11:59:59 pm Eastern
- [x] Every loaded row passes the models' own checks (`full_clean`)
- [x] The final round's dates confirmed (Q25); a change is an edit in Django admin

### NECCWI-4: Competition page, list, menu link, home page card

Built 2026-11-20: `views.py`, `urls.py`, `context_processors.case_competition` (two lazy values per request), templates in `templates/competitions/`, the card in `pages/home.html`. Tests: `tests/test_views.py`, `tests/test_pages_render.py`.

Build:

- `competitions:list`: published competitions, newest first; managers also see unpublished ones,
  marked.
- `competitions:current`: redirects to the current competition, or to the list with a message
  when there is none.
- `competitions:detail`: the case, about, resources, announcement, key dates and each round's
  window (in Eastern) and rubric. A "Your chapter" panel (`id="your-chapter"`) for the viewer's
  `current_chapter`: registered or not (with the intent button while open), each round's status
  and checklist (with Submit or Edit for members of the chapter, S29), and the result once
  published (NECCWI-12). A CSS standing in and a National Officer (the chapter chosen in the
  region bar, Feedback 8) see it view only. Managers get a Manage button.
- The "Case Competition" menu item in the Activity menu (S24), from one cached query per request
  (Gotchas 11).
- The home page card, from `HomeView.get_context_data` (S24).

Done when:

- [x] Members see published competitions only, managers see all, times show in Eastern
- [x] The panel shows the right state and buttons for a member, a PNM, an alumnus, a National
  Officer using the region bar, a registered and an unregistered chapter, before, during and
  after the window
- [x] The menu item and the card appear only when they should

### NECCWI-5: Taking part

Built 2026-11-20 (`IntentView`, `ManageView`, `ExportView`, `MemberAutocomplete`).

Build:

- `competitions:member-autocomplete`: chapter-scoped, signed-in members only, the viewer's own
  chapter, PNMs and members included, departed statuses left out (modeled on
  `BigLittleMemberAutocomplete`; Codebase facts 10).
- `competitions:intent` (members of the chapter, Q6 B): register the chapter while the intent
  window is open (the Q8 fields); afterwards, while registered, change the contacts, team size
  and note, or withdraw and rejoin, until the last round closes (S31). Sends E1 on
  registration.
- No page for adding chapters: Admins add them in Django admin (Q9, built in NECCWI-1).
- `competitions:manage` (managers; National Officers read only, S19): a table of the chapters
  taking part: chapter, region, how they registered, contacts, date, and each round's status
  (not started or in progress before the chapter's deadline, incomplete or not submitted after
  it, submitted with the time; S37), with filters by region and status. A chapter that cannot
  enter the final shows "Not selected". Managers also get the extension and on-behalf links
  (NECCWI-6), an edit link to the registration (for Admins), and the CSV download (S26).

Done when:

- [x] Registering while the intent window is open and not after; updating contacts after it
  closes; withdrawing and rejoining; registering twice updates rather than duplicates
- [x] National Officers see the table without any change buttons; members are turned away
- [x] The picker is scoped to the chapter, needs sign-in, includes PNMs and leaves out departed
  members

### NECCWI-6: Submitting

Built 2026-11-20 (`SubmitView`, `EntryDetailView`, `EntryFileView`, `ExtensionView`; `forms.EntryForm` and the team formset). The PowerPoint and Google Slides cases are tested with files built the way those programs write them (S34).

Build:

- `competitions:submit` and `competitions:submit_current`: the entry form, with the title,
  summary and team list (Q10), and one upload or link field per item, each with its help text,
  file types and size limit. Members of the chapter, as Q26 says, while `accepts_upload` is
  true. A replaced file is
  kept (`replaced_at`). The page shows the checklist and the deadline in Eastern. With Q7 A, the
  first save from an unregistered chapter registers it (`source=submission`).
- Checks per item: the extension and the detected content type (Gotchas 3), the size, and the
  required items, each with a clear message.
- `competitions:entry`: the read-only entry page, by `can_view_entry`.
- `competitions:file`: checks `can_view_file`, then redirects to the stored file's address
  (Q11 B). Pages and emails only ever link to this view, never to the address itself.
- Managers: "Upload on behalf" (the same form, at any time, `on_behalf`) and "Extend the
  deadline" (a date and time in Eastern), from the participants page (S7).
- E5 after every save that leaves the entry complete, on commit.

Done when:

- [x] Before and after the window, within the grace minutes, with an extension, and a manager on
  behalf after the close
- [x] A wrong type, a file too large and a missing required item are refused; a .pptx and a .pdf
  saved by PowerPoint and by Google Slides are accepted; a renamed executable is refused
- [x] Replacing a file keeps the old one, and judges and members see only the current one
- [x] Every visibility rule for the entry page and the file link, including a member of another
  chapter (404), a judge before the close (404), and after publishing as Q22 says
- [x] The receipt goes out once per complete save, never for an incomplete one, and never when
  the request rolls back

### NECCWI-7: The daily command and chapter emails

Built 2026-11-20: `notifications.py` (every email, E1 to E10), `reminders.py` (the ladder), the command `case_competition_daily`. Tests: `tests/test_reminders.py`.

Build:

- Herald notifications in `competitions/notifications.py`, and templates, for E1 to E5 and E6;
  chapter emails use `SupportCopyMixin` with the `case_competition` digest kind (S21); reply-to
  the competition contact.
- `services.send_scheduled(now=None, dry_run=False)`, for each round of each published
  competition:
  - E2, E3 and E4 to each eligible chapter without a complete entry. Only the most urgent step
    already crossed is sent, once, logged with a key that includes the date counted from
    (`NotificationLog`), so missed steps are skipped and a moved date starts over (Q14, S32).
    Steps are counted in Eastern calendar days. E2 is skipped for a chapter welcomed in the
    previous 3 days.
  - E6 to managers on the first run after the close.
- Command `case_competition_daily [--dry-run]`, printing what it sent: **the only scheduled task
  for the competition** (Q14). NECCWI-9 adds the judge emails and late assignments to it.
  Scheduled daily, in the US morning.

Done when:

- [x] Each step goes out once, on the right Eastern day, only to chapters without a complete
  entry; withdrawn chapters get nothing; an `advanced` round reaches only the qualifiers
- [x] A second run on the same day sends nothing; a run after a gap sends only the current step;
  moving the close date starts the closing reminders over without repeating a sent step
- [x] A chapter added in Django admin gets the reminder due that day on the next run (S30)
- [x] `--dry-run` sends and writes nothing
- [x] Chapter emails create CSS digest entries

### NECCWI-8: Release 1 wrap-up

Done 2026-11-20: the catalog area, `seed_case_competition_demo --stage open|judging|results|final`, deploy.md ?4.1, ?4.2, ?5.2, ?7 and ?8.4, management_commands.md. Browser check in light and dark themes with the demo: a member saved a complete entry with a PDF, and a manager pre-selected and published.

Build:

- Feature catalog area `case-competition` ("Case Competition"): the competition
  (`competitions:current`), registering (`competitions:current` with `url_fragment`
  `your-chapter`), submitting (`competitions:submit_current`) and the status page
  (`competitions:manage_current`, National Officer audience). See S28.
- `seed_case_competition_demo` (local QA only; never in production): a published demo
  competition with this year's rounds and rubric (read from the fixture) and eight chapters from
  three regions, at a chosen stage. At `--stage judging` (Feedback 4) the proposal window closed
  three days ago: six entries are complete, one is incomplete and one chapter submitted nothing.
  Three demo judges are part way through (Avery: five submitted and a draft; Blake: three
  submitted, a draft, one stepped aside for a conflict of interest and one to start; Casey: none
  yet, and never given her own chapter's entry), and two entries tie for second in a region with
  two places. They sign in as `necc-judge-avery@demo.thetatau.local` (also `-blake`, `-casey`)
  with the password `necc-demo-judge`. `--judge <email>` adds an existing account as a judge
  with nothing scored.
- Docs: `docs/deploy.md` §4.1 (the one-time fixture), §5.2 (the Config keys), §7 (the daily
  command) and a new §8 section for this release; `docs/management_commands.md`.
- Q27 B only: a migration creating the "Case Competition" permission group.
- Full test run and a browser check in light and dark themes.

Done when:

- [x] `load_feature_registry --dry-run` is clean and `pytest thetatauCMT/guides` passes
- [x] The full suite passes (known flaky tests aside)
- [x] The Release 1 manual checks in [Verification](#verification) are done

### NECCWI-9: Judges and assignments

Built 2026-11-20 in `judging.py` (`add_judge`, `sync_assignments`, `daily`) and `JudgesView`. Tests: `tests/test_judging.py`.

Build:

- `competitions:judges` (managers): add judges to a round with a manager-only member picker
  that searches every member (`competitions:judge-autocomplete`; not `users:autocomplete`, which
  returns nothing to an Admin outside the officer and National Officer groups), remove them, and
  see each judge's progress. Judges are people with CMT accounts only (Q16 A).
- Assignments: when judging opens, or a judge is added later, one for each judge and each
  eligible complete entry, except the judge's own chapter (S11). The daily command and a
  "Refresh" button add late entries (extensions). Removing a judge deletes nothing, but their
  scorecards stop counting. (Q17 B adds the "assign N judges to each proposal" button and manual
  changes.)
- E7 and E8, and adding late assignments, in the same daily command (Q14).

Done when:

- [x] Every judge gets every entry except their own chapter's; late entries are added; withdrawn
  and ineligible entries are not
- [x] E7 goes out once per judge per round, and each E8 step once, only to judges with scorecards
  to do

### NECCWI-10: Judging pages

Built 2026-11-20 (`MyJudgingView`, `ScorecardView`, `judging.save_scorecard`).

Build:

- `competitions:judging`: the judge's rounds and assignments with their status (not started,
  draft, submitted), the deadline and progress.
- `competitions:scorecard`: the entry (title, summary, the team with majors and class years,
  file links), the rubric with a labelled score for each criterion, a comment under each
  (Q19), the overall feedback and the private note; "Save draft" and "Submit"; "Step aside"
  with a reason (S11). Read only once results are published (S13).
- The rubric locks on the first save (S15).

Done when:

- [x] Only the assigned judge can open a scorecard; anyone else gets a 404
- [x] Out-of-range points are refused; Submit needs every criterion and the overall feedback; a
  draft can be partial
- [x] The total is stored on Submit and updated on a later change; the card is read only after
  publishing

### NECCWI-11: Scores and selection

Built 2026-11-20 (`ScoresView`, `judging.score_rows`, `preselect`, `selection_warnings`).

Build:

- `competitions:scores` (managers): one row per entry, grouped by region: the rank in the
  region, scorecards in and expected, the average total, and the decision (or place) and
  eligibility controls. Each criterion's average, the spread and the judges' scorecards open in
  a row under the entry, one at a time or all at once with "Open every entry", which the browser
  remembers (owner, 2026-11-23: the criterion columns pushed the decision and eligibility off
  the screen). Managers open any scorecard, hide a comment from the chapter (S18), and mark an
  entry ineligible with a reason (S9).
- Selection (Q20 A): "Pre-select" marks the top entries per region; managers change any of
  them; warnings for ties, the limits and missing scorecards; "Confirm selection" records who
  and when.
- CSV downloads of every score by judge and criterion (S26).

Done when:

- [x] Averages leave out drafts and stepped-aside assignments; ranks and ties are right;
  pre-selection keeps to both limits and the minimum
- [x] Only managers reach the page

### NECCWI-12: Publishing results

Built 2026-11-20 (`judging.publish_results`, `send_results`, `grant_awards`, `ResultsView`; S33).

Build:

- "Publish results" (a POST from the scores page): needs a decision on every eligible entry,
  warns about missing scorecards, and asks to confirm. Sets `results_published_at` and `_by`,
  and locks the scorecards.
- The chapter's result in the "Your chapter" panel and on the entry page: qualified or not, and
  the feedback the round's settings allow (Q21), judges unnamed, hidden comments left out.
- `competitions:results`: the Regional Qualifiers by region, for every signed-in member (Q22 A).
- E9, on commit.
- Q24 A: a data migration adds the three chapter award types (found or made by name), and
  publishing grants "NECC Regional Qualifier" to each qualifier with
  `awards.services.grant_award` in the year's cycle (`resolve_or_create_year_cycle`), when
  awards are switched on.

Done when:

- [x] Before publishing only managers see results; afterwards each chapter sees its own as
  configured, the qualifiers' proposals are visible as Q22 says, and the others stay private
- [x] Publishing twice does nothing more; each chapter gets E9 once; each award is granted once
- [x] Unpublishing (Django admin only) hides the results again, but does not take back awards or
  emails; the admin warns about this

### NECCWI-13: Final round

Built 2026-11-20: the same code, with `set_place` and "Announce winners" on the scores page.

Build:

- Round 2 has `eligibility=advanced`: only the qualifiers can submit, and only they get E2 to
  E4. Judges, assignments and scorecards work as in Round 1.
- Places: on the scores page managers record first and second place, which nobody else sees.
- "Announce winners" (Q23 A), a POST from the scores page: sets `results_published_at`; the
  winners appear on the competition page and the list; the final submissions become visible to
  every signed-in member (Q22 A); E10; the Q24 awards.

Done when:

- [x] A chapter that did not qualify cannot submit and gets no reminders
- [x] The places stay hidden from everyone else, including judges and National Officers, until
  the announcement
- [x] Announcing happens once: emails once, awards once

### NECCWI-14: Release 2 and 3 wrap-up

Done 2026-11-20: the catalog entries (My Judging, results, scores), the Regent role guide step "Enter the Case Competition", deploy.md ?8.4 covering all three releases, the seed command's later stages.

Build:

- Catalog entries for My Judging (`competitions:judging`), the Regional Qualifiers (through a
  slug-free `competitions:results_current` redirect) and the scores page.
- Role guides: a step in the Regent guide ("Register for the Case Competition and submit")
  linking the catalog entry. A PD Chair role guide would be new; it is left out unless you ask.
- Docs: `docs/deploy.md` §8 for Releases 2 and 3; the seed command extended to judging and
  results.
- Full test run and browser checks.

Done when:

- [x] Catalog checks and the full suite pass
- [x] The Release 2 and 3 manual checks are done

## Verification

```bash
docker exec thetataucmt_local_django python manage.py makemigrations competitions support --check --dry-run
docker exec thetataucmt_local_django pytest thetatauCMT/competitions -v --tb=short
docker exec thetataucmt_local_django pytest core/tests/test_anonymizer.py thetatauCMT/guides thetatauCMT/support -q
docker exec thetataucmt_local_django python manage.py load_feature_registry --dry-run
docker exec thetataucmt_local_django python manage.py loaddata necc_2026_2027
docker exec thetataucmt_local_django python manage.py case_competition_daily --dry-run
docker exec thetataucmt_local_django python manage.py anonymize_db --check_only
docker exec thetataucmt_local_django pytest --tb=no -q
```

The `loaddata` line loads this year's setup into the local database (once; NECCWI-3). The tests
load it into the test database themselves.

Manual checks after `seed_case_competition_demo` (local emails go to the file email backend; the
sent emails are listed in Django admin under Herald's sent notifications):

- Release 1: the competition page as a plain member, a PNM, an alumnus, a chapter officer and a
  manager, in light and dark themes; registering, then naming contacts after the intent window,
  withdrawing and rejoining; adding chapters in Django admin, with times in Eastern; submitting a
  PDF and a PowerPoint, replacing one, and a refused file; a file link opened by a member of
  another chapter; the daily command on different days (with `freeze_time` or the demo's
  dates).
- Release 2: adding judges; a judge's draft and submitted scorecards; stepping aside; the scores
  page, pre-selection and publishing; a chapter's result and feedback; the Regional Qualifiers
  page as a member of another chapter.
- Release 3: a qualifier's final submission; a non-qualifier refused; places hidden until the
  announcement; the winners on the competition page and on the chapter's awards.

## Deployment notes

Production is PythonAnywhere (see [deploy.md](../deploy.md)). No new Python packages or
environment variables. The step-by-step runbook is
[deploy.md ?8.4](../deploy.md#84-upgrading-into-the-case-competition-release); all three
releases ship in one deploy, by Wednesday, December 2. In short:

1. The standard update flow: `migrate` (`competitions` 0001 to 0005, `support` 0003),
   `collectstatic` with the production settings, Reload.
2. `python manage.py loaddata necc_2026_2027`, **once**, right after the migration (NECCWI-3,
   S27).
3. `python manage.py load_feature_registry`.
4. Optional Config rows: `CASE_COMPETITION_MANAGERS`, `CASE_COMPETITION_CHAPTER_ROLES`,
   `CASE_COMPETITION_CONTACT` (S38; set the first and last while the Professional Development
   Director role is vacant). Never `loaddata default_configs` in production. No permission group
   (Q27 A).
5. Schedule `case_competition_daily` as one daily task in the US morning (Q14).
6. Check the dates in Django admin, then smoke test large uploads with an unpublished copy, and
   delete it (S35).
7. Add this year's chapters in Django admin ("Chapters taking part", Q9; S30), tick "Published",
   and add the judges before December 11.

## Out of scope for the first version

- Applying the dues reductions (Central Office does that in QuickBooks), and paying or tracking
  the $400 grants. Say if you want a "grant paid" date on each qualifier.
- Chapter score points for taking part.
- Calendar (iCal) entries, or chapter Tasks, for the competition dates.
- A document viewer in the page, and downloading every file as one ZIP (S10, S26).
- Counting slides automatically (S9).
- Adjusting scores for harsh or generous judges (S16).
- More than one team per chapter (S5).
- Public pages without sign-in (Q22 A), outside judges without CMT accounts (Q16 A), and private
  file storage with expiring links (Q11 B).
- A CMT page for adding chapters (Q9: Django admin) or for editing the setup (Q3: Django admin).

## Decisions log

Answers move here from [Questions for review](#questions-for-review), with the date and any
follow-up they caused.

| # | Decision | Date | Follow-up |
|---|---|---|---|
| Q1 | A (default): the CMT takes this year's proposals; "we will need to deploy this soon". | 2026-11-20 | The release plan stands: Release 1 live on December 2. |
| Q2 | The proposal window and judging deadline as the defaults. Final submissions due Friday, May 28; final judging deadline Friday, June 25; Convention Saturday, July 17. The dates must be easy to update. | 2026-11-20 | Every date is a field on the competition or a round in Django admin, entered in Eastern (S32). Read as 2027 and 11:59 pm; Q25 confirms that and asks when the final window opens. |
| Q3 | **A, changed:** set up in Django admin, not loaded by a command; this year is "a one time fixture load of the extracted rubric and setup information". The rubric is stored in a model and may change from year to year. | 2026-11-20 | NECCWI-3 is now the fixture `necc_2026_2027` (built); no `load_competition` command (S27 rewritten). Rubric: `RubricCriterion` rows on each round. Q27 asks who gets Django admin access. |
| Q4 | A (default): Admins plus `CASE_COMPETITION_MANAGERS`; blank means the Professional Development Director. | 2026-11-20 | Config row seeded (NECCWI-1). |
| Q5 | A (default): no Viewflow. | 2026-11-20 | None. |
| Q6 | **B:** any member of the chapter declares intent and submits; the intent can be updated to add the main contacts in charge of the submission. | 2026-11-20 | Permission matrix rewritten. S29 defines "member" (current members and PNMs); S31 lets a registered chapter update its contacts after the intent window. `CASE_COMPETITION_CHAPTER_ROLES` now only adds email recipients (Q13). Q26 asks whether named contacts should become the only ones who can change the entry. |
| Q7 | A (default): any active chapter can submit, which registers it. | 2026-11-20 | None. |
| Q8 | A (default): contacts, estimated team size, an optional note; "mainly for us to know how many chapters are interested". | 2026-11-20 | None. |
| Q9 | **In Django admin, "nothing fancy".** | 2026-11-20 | Built: "Chapters taking part" on the competition's admin page, with type-to-search chapter and contact fields, recording who added each one. No CMT page for it (NECCWI-5 trimmed). Chapters added there get the next daily reminder rather than a welcome email (S30). |
| Q10 | A (default): title, summary, the file, an optional team list. | 2026-11-20 | None. |
| Q11 | **B:** stored like other uploads, under names nobody can guess. | 2026-11-20 | No private storage or expiring links (NECCWI-1, NECCWI-6). Each upload goes in a folder with a random name (built); the CMT shows a file's link only to people allowed to see it, but the link opens for anyone who has it. S10 changed. |
| Q12 | A (default): final report, final presentation, grant spending summary, optional video link. | 2026-11-20 | In the fixture's Round 2. |
| Q13 | **A and C:** the named contacts, the five chapter officers, the PD Chair and the chapter's generic addresses; replies to the competition contact; CSSs by digest. | 2026-11-20 | `chapter_recipients` (NECCWI-2): contacts, `Chapter.council_emails()` and the holders of `CASE_COMPETITION_CHAPTER_ROLES` (blank means the PD Chair). |
| Q14 | A (default) schedule, all in **one daily command**. | 2026-11-20 | `case_competition_daily` sends every scheduled email (E2, E3, E4, E6, E7, E8) and adds late judging assignments; no other scheduled task (NECCWI-7, 9; Shared preamble). |
| Q15 | A (default): every email in the inventory. | 2026-11-20 | None. |
| Q16 | A (default): anyone with a CMT account. | 2026-11-20 | No outside-judge accounts. |
| Q17 | A (default): every judge scores every proposal except their own chapter's. | 2026-11-20 | None. |
| Q18 | A (default): 1 to 5 per criterion, every criterion counting the same. | 2026-11-20 | In the fixture: `max_points` 5 on each criterion, `score_min` 1 on each round. |
| Q19 | A (default). | 2026-11-20 | None. |
| Q20 | A (default): pre-select the top two in each region; managers confirm. | 2026-11-20 | None. |
| Q21 | A (default): qualified or not, plus unsigned feedback. | 2026-11-20 | In the fixture: `share_feedback` yes, `share_scores` and `share_rank` no. |
| Q22 | A (default): every signed-in member sees the qualifiers' proposals. | 2026-11-20 | The planned per-round `gallery_audience` setting was dropped; the rule is fixed. |
| Q23 | A (default): a manager presses "Announce winners" at Convention. | 2026-11-20 | The planned `Round.announce_at` was dropped. Convention (July 17, 2027) is a key date only. |
| Q24 | A (default): three chapter award types. | 2026-11-20 | None. |
| S24 | **Your change:** the "Case Competition" link goes in the Activity menu, not the Chapter menu. | 2026-11-20 | NECCWI-4. |
| Q25 | A (default): the final window opens Friday, May 21, 2027, at 12:00 am Eastern and closes Friday, May 28, 2027, at 11:59 pm Eastern; final judging deadline Friday, June 25, 2027, at 11:59 pm Eastern; Convention Saturday, July 17, 2027. | 2026-11-20 | None: the fixture already has these dates (NECCWI-3). |
| Q26 | A (default): any member of the chapter can change the entry until the close; every save records who made it, and the receipt goes to the chapter after every complete save. | 2026-11-20 | None: `can_submit` checks membership only (NECCWI-2). |
| Q27 | A (default): only Admins use Django admin; managers use the CMT pages. | 2026-11-20 | No permission group or deploy step for managers (NECCWI-8). |
| Review | "Looks good. Please proceed." The models are approved; build the rest. | 2026-11-20 | NECCWI-2 onward. |
| Feedback 1 | Never tell users that something is changed in Django admin. | 2026-11-20 | Pages, messages, emails and the catalog no longer mention it. A registration added by an Admin reads "Added by national" (migration 0004). Once results are published, the scores page and its messages say the decisions are final. Admins keep a pencil icon on the status page to edit a registration. |
| Feedback 2 | An entry that can no longer be changed is not "In progress": mark unfinished entries "Incomplete". | 2026-11-20 | S37: after the chapter's deadline an unfinished entry is "Incomplete", and a chapter that saved nothing is "Not submitted", on the status page (and its progress line), the chapter's panel and home card, the entry and submit pages and the CSV. |
| Feedback 3 | A chapter not selected for the final cannot submit it; only the proposal can be entered without an intent to compete. | 2026-11-20 | The rules already refused them; now the wording says so too (the competition and intent pages, the welcome email, the catalog), the extension page refuses a chapter that cannot enter, and the status page marks it "Not selected". |
| Feedback 4 | A competition in the judging phase to look at, with example judges. | 2026-11-20 | `seed_case_competition_demo --stage judging` (NECCWI-8): this year's rubric, three demo judges part way through, a tie at a region's limit. The scores page now lists the pre-selection's warnings, such as that tie, before Pre-select is pressed. |
| Feedback 5 | "It is not clear where to go to judge my assigned chapters"; judges should get a notification bubble like other to-dos. | 2026-11-21 | S24 rewritten: the ballots pattern for judges (a counted scales icon at the top of every page and a reminder at the top of the home page, replacing the judge line on the home card), "My Judging" with the count in the Activity and account menus, a "where you stand" note per round on the competition page, and "Score this entry" (or "Finish your scorecard") on an entry's page. Only judges pay for the count: everyone else stops at the one query that already decides the menu link. |
| Feedback 6 | On the scores page the Decision and Eligible columns are hard to see; put the criterion columns and the spread in a sub-row that opens when needed. | 2026-11-23 | NECCWI-11: each entry's row keeps the rank, scorecards, average, decision and eligibility; a chevron opens a row under it with each criterion's average (full names), the spread and the scorecards, which moved there from the entry cell. "Open every entry" and "Close every entry" do all of them, and the browser remembers "open" across the reload after each save. The table now fits a 1,000-pixel-wide screen. |
| Feedback 7 | Roles are often vacant (no Professional Development Director now): who gets the emails and the footer then? A Config should override who gets replies. | 2026-11-23 | Before: only Admins managed, and replies, the footer and the managers' email fell back to Central Office. Now S38: the new `CASE_COMPETITION_CONTACT` setting decides the contact ahead of the competition's own contact role and email, the managers' email follows it when nobody is named a manager, and the competition's admin page shows "Contact now". `CASE_COMPETITION_MANAGERS` still decides who manages; it accepts usernames and emails, so name people there while the role is vacant (migration 0005 only changes a help text). |
| Feedback 8 | As a National Officer, the competition page should follow the chapter chosen in the region bar and show its status for each form (intent, proposal, final), not always my own chapter. | 2026-11-23 | S29 and NECCWI-4: the chapter panel shows the region bar's chapter (`current_chapter`), headed "Chapter" rather than "Your chapter" when it is not the viewer's own: its registration with how and when it registered, and each round's status, view only. Anyone who sees every chapter's status (S19) gets this; "View the entry" appears only where the permission matrix allows, so a National Officer opens a chapter's entry only once it is showcased after results. |

## Gotchas for the build

1. **Time zones in forms and the admin.** Django parses and shows `DateTimeField` values in the
   current time zone, which is Arizona time. Django admin is handled (NECCWI-1,
   `admin.CompetitionTimeZoneMixin`): each page runs inside
   `timezone.override(competition.zone)`, **and is rendered inside it too**, because an admin
   page is a template response that would otherwise render after the view returns, outside the
   override (showing Arizona times while saving Eastern ones). CMT pages and forms with a time
   must do the same, and templates show times with `Competition.format_time`. Test the edges with
   `freeze_time`: 11:59:59 pm Eastern on December 11 is 4:59:59 am UTC on December 12 and
   9:59:59 pm on the site's clock.
2. **Upload addresses** (Q11 B): `models.entry_file_path` puts each upload in a folder with a
   random name and keeps the original name, cleaned with `get_valid_filename` (which drops
   accents and brackets) and cut to 100 characters with the extension kept. Show
   `EntryFile.original_name` on pages, not the stored name.
3. **PowerPoint content types vary.** python-magic may report a .pptx as the presentation type,
   `application/zip` or `application/octet-stream` (seen locally for a Word file), and a .ppt as
   `application/vnd.ms-powerpoint`, `application/CDFV2` or `application/x-ole-storage`, depending
   on the libmagic version. Built (S34): `uploads.py` checks the file's own structure instead
   (`%PDF-`, the image signatures, the OLE header, and `[Content_Types].xml` plus `ppt/`,
   `word/` or `xl/` inside an Office zip), so it does not depend on libmagic at all.
4. **Send emails on commit** (Codebase facts 20), so a refused or rolled-back save never emails.
5. **Unique constraints and empty columns** on PostgreSQL 12 (Codebase facts 21): the models use
   conditional constraints where a column can be empty, and the email log uses one unique `key`.
6. **Role holders and emails:** never `get_current_officers_council_specific` or
   `get_email_specific` with `pd chair` (Codebase facts 11).
7. **Catalog links** cannot carry the competition slug (Shared preamble), hence the `current`
   redirect URLs.
8. **Member pickers:** `users:autocomplete` only answers the officer and National Officer groups
   (Codebase facts 10); members use `competitions:member-autocomplete` and managers use
   `competitions:judge-autocomplete`.
9. **A CSS and pages that change data on GET:** the view-only middleware only refuses non-GET
   requests, so no competition page may change data on a GET.
10. **Emails link to pages, never to files**, so the CMT checks who is asking before showing a
    file's link. The stored file's address opens for anyone who has it (Q11 B).
11. **Base template cost:** the menu item runs on every page; compute the current competition once
    per request (a context processor that caches on the request), not in several template tags.
    The judges' count (S24) is lazy too and runs only after the existing "judges anything" check
    says yes, so members who do not judge pay that one query for both the menu link and the count.
12. **Large uploads on PythonAnywhere:** a 50 MB upload has to reach the web worker and then
    Google Cloud Storage within one request. Try one in production before December 4 (Deployment
    notes 8); lower the default size limit if it struggles.
13. **Fixtures need `modified`.** `loaddata` saves rows raw, so `auto_now` never fills
    `modified`; every row in a fixture for these models must carry `created` and `modified`, as
    `necc_2026_2027.json` does.
14. **`PROTECT` blocks deleting the parent too** (found in the build). Deleting a competition
    cascades to its items and its entries' files, but a `PROTECT` key from the files to the items
    refuses the whole delete. `RESTRICT` allows it when the protected rows go in the same delete
    (S35).
15. **Data migrations and fixed-pk fixtures.** On a brand-new database `migrate` runs before
    `loaddata award_types`, whose fixed pks 1 to 30 would overwrite rows a migration made at pk 1
    to 3. Migration 0002 therefore skips an empty table, and `judging.award_type_for` makes a
    missing type at publish time (S33).
16. **Tests that freeze the clock.** Log in after moving the clock: sessions last two weeks from
    the last save, and a jump of weeks signs the test client out. `UserStatusChange` and
    `UserRoleChange` decide "current" against an import-time `TODAY`, so the factories' random
    dates can disagree with a frozen date; `tests/factories.member()` sets `current_status`
    directly and `give_role()` starts its roles in 2020.
17. **Cached querysets in tests.** After a queryset has been iterated, `.count()` returns the
    cached length; count again with a fresh queryset after more emails are sent.
18. **The CSS state is cached on the user object** for the request (`support.services.css_state`).
    A test that adds an assignment after the user was loaded calls `clear_css_state(user)`.

## Unrelated issue noticed during planning

Because production stores every upload as public-read (Codebase facts 3), the disciplinary
process's charging letters, meeting minutes, results letters and ledger sheets
(`discipline/<chapter-slug>/<user-id>/<chapter-slug>_<user-id>_<original file name>`,
`forms.models.get_discipline_upload_path`) can be opened by anyone who has a file's link, with no
sign-in. The original file name is the only part that is hard to guess, and a forwarded link works
forever. The same goes for Transition Report attachments and other uploads. The competition
chose to store its files the same way (Q11 B), so nothing changes here; private storage with
expiring links (Codebase facts 4) remains an option for those fields later (existing files would
need their access changed in Google Cloud Storage). Not part of this feature.

Status: Open.
