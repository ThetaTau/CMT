# Task: review tasks app + add "archive old TaskDates" feature

## User request
- Review tasks app + task completion throughout app (officers complained).
- Add a way to mark old TaskDates as old/no-longer-needed so only current
  tasks get completed when they should.

## Root-cause bug found
- `Task.incomplete_dates_for_task_chapter` returns dates in window
  [today-2*days_advance, today+days_advance], ordered by date ASC.
- `mark_complete` + `TypeFieldFilteredChapterAdd.form_valid` call `.first()`
  → completes the OLDEST lingering incomplete date, NOT the current one.
- No way to retire an old date. => archive feature fixes this.

## Plan (all in container; podman exec thetataucmt_local_django ...)
1. Model `TaskDate`: add `archived` (BooleanField default False, db_index),
   `archived_reason` (CharField blank), `archived_on` (DateTimeField null).
   + `archive(reason="")` / `unarchive()` helpers.
2. Exclude archived in querysets:
   - Task.all_dates_for_task_chapter
   - Task.incomplete_dates_for_task_chapter
   - TaskDate.incomplete_dates_for_chapter
   - TaskDate.incomplete_dates_for_chapter_next_month
   - TaskDate.dates_for_next_month
   - TaskDate.incomplete_dates_for_chapter_past
   - TaskDate.dates_for_chapter(cls, chapter, include_archived=False)
3. Migration 0008.
4. TaskCompleteView.form_valid: refuse to complete archived date.
5. TaskListView.get_queryset: base = dates_for_chapter(include_archived=True);
   add `archived` ChoiceFilter (default "0"=hide) in TaskListFilter +
   default in _build_request_get + InlineField in TaskListFormHelper.
6. Admin: list_display/list_filter archived + actions mark/restore.
7. Mgmt command archive_old_task_dates (--before / --older-than-days /
   default academic-year-start / --task / --dry-run / --reason).
8. regions/views.py RegionTaskView: qs = TaskDate.objects.filter(archived=False).
9. task_complete.html + task_list.html tweaks.
10. Tests in tasks/tests/ (models, views, command) + run.

## Baseline: 49 pass, 1 skip in tasks/tests (2026-07-11). No pre-existing fails today.
## Migration latest = 0007 -> new 0008.

## PHASE 2 (fix all tests + flakiness) — CI showed 10 fails:
1. test_urls_resolve[events:update[pk]] -> stale kwargs; changed param to
   {year,month,day,event_slug} (events:update is date+slug now). DONE
2. chapters test_chapter_detail_view -> template redesigned; assert chapter.name
   + f"{region} Region" separately (no more "in the ... Region"). DONE
3. events test_calculate_meeting_attendance -> semester-boundary flaky (events
   -15d..-5d straddle Jun/Jul). Added @freeze_time("2026-04-15 12:00:00"). DONE
4-10. 7 tasks/tests/test_views.py date=today tests -> Phoenix(UTC-7) vs UTC:
   DateRangeFilter "today" uses timezone.now() (UTC) but tasks dated
   date.today() (local). Added FROZEN_NOON_UTC="2026-05-15 12:00:00" const +
   @freeze_time on all date=today list tests (incl my 3 archive ones). DONE
+ Un-skipped 2 chapters flaky tests (test_chapter_list_view_chapter_officer/
  _natoff) w/ @freeze_time; verified pass (RMP always signed under freeze,
  officer branch only messages, no redirect). pytest-randomly NOT installed.
Key: freezegun collapses date.today()==now(); noon UTC keeps Phoenix+UTC same day.
## Targeted run: 192 passed. Full suite pending final verify.
