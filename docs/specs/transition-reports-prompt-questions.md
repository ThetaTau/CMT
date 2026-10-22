# Transition Report prompt questions, draft for officer review

This is discussion material for TRWI-2's Default Prompt Set, specifically the
Pre-Launch Checklist item "get a pass from someone who has actually held a
chapter office before the prompt set is seeded to production" (`prompt_key`
values become immutable once shipped, so this is the point to argue over
wording, not after).

**How to use this:** walk each position's list with someone who has actually
held it (or is currently in it). Cut anything that doesn't get a real answer
in practice, reword anything that reads as vague, and merge duplicates. What
survives becomes the actual seeded prompts (`seed_transition_prompt_set.py`).
Nothing here is final.

**Format:** every list is capped at 10 questions, ordered successes to
failures to reference material to forward-looking (the same principle the
shipped prompt set already follows). Each question is meant to produce one
paragraph or a short list, not an essay: if a question needs more than
that to answer honestly, it's probably two questions.

**Coverage check:** across all the lists below, most questions still map to
one of the 8 themes the app already tags reports by (success, failure,
contacts, expertise, calendar, systems, continuity, advice, risk). If a
position's final list drops one of these entirely, that's worth flagging
explicitly rather than losing by accident.

---

## Required chapter officer positions

One tailored set per position (`ReportTemplate.position_key`), grounded in
what the app's own role guides (`guides/fixtures/feature_registry.json`)
say each position is actually accountable for.

### Regent

1. What's the current status of the chapter's national tasks, and is anything already overdue?
2. What's the chapter's current score, and which categories are dragging it down?
3. Who are the other officers, and how is each one actually doing? Who needs support?
4. What goals did you set with your Regional Director this term, and how much progress was made?
5. What's unresolved or in motion right now that lands on your successor's desk day one?
6. What went well this term that your successor should keep doing?
7. What didn't go well, and what would you do differently?
8. Who outside the chapter (RD, adviser, a national office contact) should your successor know, and how do they reach them?
9. What's coming up on the calendar to prepare for (health & safety programs, the annual audit, award/OSM nominations)?
10. What's the biggest risk to the chapter's standing right now?

### Vice Regent

1. What's the status of the current candidate class, and is the pledge form filed?
2. What does new member education actually look like week to week, beyond what's on file?
3. Have pledge pins been ordered for the current class? Who's the vendor and what's the lead time?
4. Is anything blocking the next initiation (paperwork, a candidate missing from the roster, an incomplete requirement)?
5. What went well in the candidate program this term that your successor should keep doing?
6. What didn't go well, and what would you do differently?
7. Who do you coordinate with day to day (New Member Educator, Scribe), and how does that handoff work?
8. What's the timeline your successor needs to hit for the next candidate class?
9. Is there an unresolved issue with a current or recent candidate your successor should know about?
10. What surprised you about this role that nobody warned you about?

### Scribe

1. Is the roster fully current right now, or are there known gaps your successor is inheriting?
2. Are there pending status changes (graduation, withdrawal, alumnus requests) not yet filed?
3. Was the most recent officer election already reported, or is that still outstanding?
4. What's your system for keeping the roster updated week to week?
5. How do you track attendance, and is anything currently behind?
6. What went well this term that your successor should keep doing?
7. What didn't go well, and what would you do differently?
8. What's the biggest risk to roster accuracy right now?
9. Where do you keep your own working notes, if anywhere outside the system?
10. What's unfinished that lands on your successor's desk day one?

### Treasurer

1. What's the chapter's current balance/standing with national, and is anything on it unexplained?
2. Are dues fully collected for this term? If not, who's outstanding and why?
3. Is the H&S fee paid for the year?
4. Is there anyone overdue who needs to be referred for collections?
5. What's the state of the chapter's physical inventory (badges, jewelry, ritual equipment)?
6. What went well with the chapter's finances this term that your successor should keep doing?
7. What didn't go well, and what would you do differently?
8. Where do the account/banking records live, and who else has access?
9. What's coming up that your successor needs to budget or plan for?
10. What's the single biggest financial risk to the chapter right now?

### Corresponding Secretary

1. Has this year's Gear article been submitted? If not, what's the plan and deadline?
2. Has the alumni newsletter gone out this year, and how current is the alumni list it went to?
3. How do you keep alumni contact details updated as they change?
4. Have you set up contact sync (Google/Microsoft), or is this still done manually?
5. What went well in alumni/external communication this term that your successor should keep doing?
6. What didn't go well, and what would you do differently?
7. Which alumni or outside contacts are most worth staying in touch with?
8. What's unfinished that lands on your successor's desk day one?
9. What surprised you about this role that nobody warned you about?
10. Any advice for keeping this from becoming a once-a-year scramble?

### Pledge/New Member Educator

1. What does new member education actually cover week to week, beyond what's on file?
2. Are all current candidates showing up correctly on the roster/pledge form?
3. Are education sessions being logged as events consistently?
4. Have the required health & safety programs been delivered to this class?
5. Has anyone depledged this term, and is the reason understood (even in general terms)?
6. What went well in the program this term that your successor should keep doing?
7. What didn't go well, and what would you do differently?
8. Who do you coordinate with closely (Vice Regent, Scribe), and how does that handoff work?
9. What's the calendar of remaining sessions/milestones before initiation?
10. What surprised you about this role that nobody warned you about?

### Risk Management Chair

1. Has everyone signed the Risk Management Policies this term? Who's outstanding?
2. Have the required health & safety programs actually been delivered this year, not just reported?
3. What upcoming events need a risk plan before they happen?
4. Has anything actually gone wrong this term (an incident, a close call, a complaint), even if handled quietly?
5. What went well in how the chapter managed risk this term that your successor should keep doing?
6. What didn't go well, and what would you do differently?
7. Is there anything in the chapter's bylaws relevant to a recurring risk issue?
8. Who do you go to first when something happens?
9. What's the one risk you worry about most that hasn't happened yet?
10. What surprised you about this role that nobody warned you about?

---

## Generic sets (position type defaults)

These apply whenever a specific position doesn't have (or doesn't need) its
own tailored set above (`ReportTemplate.position_key=""` for that
`position_type`).

### Committee Chair (generic)

No role guide exists yet for committee chairs generally, so this leans on
general program-leadership concerns rather than app-specific detail. Treat it
as the rougher draft of the set above.

1. Who served on your committee, and who should be asked back?
2. What recurring events/programs does this committee run, and what's the timeline for each (venue, vendors, booking deadlines)?
3. What did this actually cost vs. what was budgeted, and where were the surprises?
4. What drove (or killed) member participation this term?
5. What went well that your successor should keep doing?
6. What didn't go well, and what would you do differently?
7. Who outside the chapter (vendors, advisers, other chapters) is worth knowing for this role?
8. What's unfinished that lands on your successor's desk day one?
9. If your successor does only three things in their first 30 days, what should they be?
10. What surprised you about this role that nobody warned you about?

### National Officer (generic, also covers Council)

The app's own National Officer role guide says outright that "which parts
you live in depends on your seat: the Grand Treasurer works from balances
and audits, the Grand Scribe from officer records and forms, the Grand
Marshal from scores and tasks." That variation is exactly why this is one
shared generic set rather than 10 individual ones per position: there
isn't enough common ground across "Regional Director" and "Educational
Foundation Board of Director" to make position-specific questions
meaningful without guessing. Council positions (Grand Regent, Grand Scribe,
etc.) share this same set for the same reason.

If, after discussion, a specific seat (e.g. Grand Treasurer) turns out to
need real position-specific questions, give it its own
`position_key`-specific template later, the same pattern as the Treasurer
override among chapter officers, rather than trying to force it into this
generic set.

1. What did you actually spend your time on in this role, day to day?
2. Which chapters or regions need particular attention right now, and why?
3. What's in motion at the governance level (policy changes, proposals, pending decisions) that isn't finished?
4. What went well this term that your successor should keep doing?
5. What didn't go well, and what would you do differently?
6. Who are the key contacts (staff, other national officers, vendors/partners) your successor needs, and what does each help with?
7. What tools, accounts, or shared files does this role depend on, and where do they live?
8. What's unfinished that lands on your successor's desk day one?
9. If your successor does only three things in their first 30 days, what should they be?
10. What surprised you about this role that nobody warned you about?

### Regional Director

Unlike the other National Officer seats, Regional Director has rich,
specific grounding in the app's own role guide (region dashboard, chapter
scores/balances side by side, the pending event review queue, goals set
per chapter), so it gets a tailored `position_key`-specific set rather than
sharing the generic National Officer one above.

1. What went well in how you supported the region this term that your successor should keep doing?
2. What didn't go well, and what would you do differently?
3. Which chapters in your region need the most attention right now, and why (score, balance, officer turnover, etc.)?
4. What patterns have you spotted that are region-wide rather than isolated to one chapter?
5. Which chapters have a Treasurer/balance situation worth watching, even if it hasn't become a real problem yet?
6. Are there chapters technically running but not really functioning (low event turnout, an officer team that's checked out)?
7. What goals did you set with each chapter, and which are on track vs. falling behind?
8. Who are the key contacts in your region (officers, advisers, chapter contacts) your successor needs, and what does each help with?
9. What's unfinished or in motion (a chapter visit, an escalation, a pending nomination) that lands on your successor's desk day one?
10. What surprised you about this role that nobody warned you about?
