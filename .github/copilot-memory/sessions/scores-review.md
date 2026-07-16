# Scores app review (2026-07-12)

## Goal
Review scores app calc logic, fix bugs, ensure ScoreChapter created properly, simplify while keeping biennium tracking.

## System map
- ScoreType: category. points=max/acad-year, term_points=max/term. type Evt/Sub/Spe. special=eval formula.
- ScoreChapter(YearTermModel): (chapter,type,year,term)->score. unique_together.
- Event/Submission.save(calculate_score=True): type.calculate_score(obj)->obj.score; then type.update_chapter_score(chapter,date).
- chapter_score(chapter,date): Sum(event.score) in semester window, min(total, term_points).
- update_chapter_score: computes current term + opposite term (fall+following spring = 1 acad year), caps fall+spring at points (fall kept whole, spring=remainder). Self-consistent b/c chapter_score re-derives from events.
- annotate_chapter_score: maps ScoreChapter rows to 4 biennium slots: score1=Fall Y0, score2=Spring Y1, score3=Fall Y1, score4=Spring Y2. total=sum.
- score_calculate_extras cmd: Spe types (pledge-ratio, membership, service-hours, gpa, societies) via update_or_create.
- calculate_meeting_attendance (events/models): avg attendance across meeting events in semester, per-event score.

## BUGS FOUND
1. **Boundary off-by-one (CORRECTNESS):** chapter_events/chapter_submissions use date__gt/date__lt (EXCLUSIVE both ends) with date_range()=(Jul1, Jan1)/(Jan1,Jul1). Events on exactly Jul1 or Jan1 score in NEITHER semester (dead zone). FIX: half-open date__gte/date__lt.
2. **Window inconsistency:** calculate_meeting_attendance uses semester_encompass_start_end_date (INCLUSIVE lte/gte) while scoring uses date_range (exclusive). Meeting on boundary grouped in fall but scored in neither. FIX: align meeting attendance to same half-open window as chapter_events.
3. **N+1 + convoluted:** annotate_chapter_score runs scores_values.filter(id=..) per type in loop + offset math. Simplify to a dict lookup keyed by (year,term)->4 slots. Preserve output exactly.
4. **update_score inconsistent:** ScoreChapter.update_score sets term-capped only (no year cap) unlike update_chapter_score. Only used in a test. Delegate to update_chapter_score for single code path.

## OUT OF SCOPE (documented, not changing)
- No delete recalc: no UI delete views for Event/Submission (only admin). Signals too risky (chapter cascade). Skip.
- eval() in calculate_special: admin-controlled DB formulas, existing behavior.

## Test cmds (CONTAINER ONLY)
- podman exec thetataucmt_local_django pytest thetatauCMT/scores -v --tb=short
- events model test: thetatauCMT/events/tests/test_models.py::test_calculate_meeting_attendance (freezes 2026-04-15 mid-spring, dates -15d..-5d, avoids boundary -> my fix safe)

## BIG BUG #5 (fixed): score_calculate_extras wiped service-hours to 0
- service-hours (pk13) is type Evt w/ special "50*(HOURS/(MEMBERS*16))" -> events score 0 (HOURS in calculated_elsewhere).
- Command computes real score from UserSemesterServiceHours + update_or_create, THEN final loop recomputes ALL Evt/Sub -> chapter_score sums events(0) -> OVERWRITES to 0.
- FIX: COMMAND_COMPUTED_SLUGS=[pledge-ratio,membership,service-hours,gpa,societies]; final loop .exclude(slug__in=...). Verified test fails (0.0>0) w/o fix, passes with.

## CHANGES MADE (all done)
1. scores/models.py chapter_events/chapter_submissions: date__gt->date__gte (half-open).
2. events/models.py calculate_meeting_attendance: YearTermModel.date_range + gte/lt (import YearTermModel added). semester_encompass still used at L408 count_events_biennium.
3. scores/models.py annotate_chapter_score: rewrote w/ defaultdict + biennium_slots dict, 1 query (added `from collections import defaultdict`).
4. scores/models.py ScoreChapter.update_score: delegate to update_chapter_score + refresh_from_db.
5. scores/models.py update_chapter_score: cap block -> explicit fall/spring + max(0,...). Same behavior.
6. score_calculate_extras.py: COMMAND_COMPUTED_SLUGS exclude (bug #5).

## TESTS ADDED
- scores/tests/test_models.py: 6 tests (jan/jul boundary, year-cap x2, biennium slot map, neighboring ignore). _clean_type() helper for --reuse-db isolation.
- scores/tests/test_commands.py: NEW, 1 test service-hours not wiped.

## RESULTS
- scores: 30 pass. events+chapters+regions+core+finances+submissions: 554 pass 2 skip 0 fail (pre-existing flaky test_calculate_meeting_attendance + test_chapter_detail_view both PASSED this run).

## NOTED not fixed (out of scope, documented)
- count_events_biennium (events/models L404): `query` undefined when date passed (cls.objects.filter not assigned). Pre-existing, not scores calc. LEFT.
- No delete recalc (no UI delete views). LEFT.
- Command min() caps vs fixture term_points mismatches (societies min20 vs term_points10) = domain config, LEFT.

## Status: DONE, final full-suite verify pending
