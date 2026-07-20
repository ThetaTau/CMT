# Task: Align anonymizer/ files with current models

## Goal
dj_anonymizer requires EVERY model registered (skip/clean/anonym) and EVERY
field either anonymized or in exclude_fields. Models/apps changed a lot.
Prevent exposing real PII on staging, but keep non-sensitive data for testing.

## dj_anonymizer registration modes
- register_skip([Model]) = leave data as-is (non-sensitive)
- register_clean([(Model, AnonymBase)]) = delete all rows
- register_anonym([(Model, Anonym)]) = fake specific fields; rest must be in exclude_fields

## Config
- Only in local.py + staging.py INSTALLED_APPS (NOT production).
- Runs in docker container `thetataucmt_local_django`.

## Plan
1. [ ] Enumerate all models (all apps incl NEW: contact_sync, attendance)
2. [ ] Map vs anonymizer files
3. [ ] Add missing models + fix changed fields
4. [ ] Validate via dj_anonymizer check command in container

## New apps since anonymizer last updated
- contact_sync (UserContactSyncToken, ...)
- attendance (AttendanceRecord, AttendanceStatusTransition, MatchQueueItem)
- events new models: CalendarFeedSubscription
- forms new: Employer, OtherSchool
- users new: UserTag

## KEY FINDINGS (from dj_anonymizer source + diagnostic)
- Validation: `anonymize_db --check_only` (no --soft_mode) raises LookupError
  listing every unregistered model. register_anonym ALSO validates fields at
  import: anonym_fields + exclude_fields (+ auto FK/O2O/M2M/pk) must EXACTLY
  equal model's concrete Field set. Errors surface one-at-a-time.
- **LOADER BUG (must fix):** real cmd imports `anonymizer/<app.name>.py`. Local
  app names are dotted (`thetatauCMT.users`) but files are short (`users.py`),
  so 17 LOCAL files are NEVER imported -> real check reports ~80 missing models.
  Anonymizer currently does NOTHING for local PII. Third-party files load fine
  (address, herald, watson, viewflow, material, report_builder, django_otp,
  termsandconditions, allauth, django_plotly_dash, base).
- FIX loader: add auto-loader to base.py that imports each sibling
  anonymizer/*.py whose basename is NOT an installed app.name (skip base/__init__).
  Uses `importlib.import_module(f"anonymizer.{name}")` (anonymizer has __init__.py,
  /app on sys.path via manage.py). Avoids double-registration of 3rd-party files.

## GAPS TO FIX (from diagnostic, once all files load)
Missing models (10) -> decide skip/clean/anonym after reading:
- attendance: AttendanceRecord, AttendanceStatusTransition, MatchQueueItem(RAW PII->clean)
- contact_sync: UserContactSyncToken (encrypted tokens/secrets -> clean)
- events: CalendarFeedSubscription (uuid token, low risk -> skip)
- forms: Employer(name->skip), OtherSchool(name->skip), RitualProficiency(check)
- jobs: JobPostingBan (skip, consistent w/ jobs app)
- users: UserTag (name/label -> skip)
Field diffs:
- User: add profile_picture (anonymize fake.file_path - it's a face photo/PII),
  exclude unsubscribe_categories (preference, keep for testing)
- StatusChange: REMOVE `employer = fields.function(fake.company)` (employer is now
  an FK to Employer -> auto-excluded relation; was in BOTH lists)

## Status: COMPLETE — check passes ("Check pass successfully")
All edits applied; `anonymize_db --check_only` passes (soft_mode=False).
Removed scratchpad/anon_diag.py. Did NOT run the real anonymize (would fake the
dev DB) — only --check_only, which is the safe validation backup.sh mirrors.

## FINAL DECISIONS
- base.py: add auto-loader importing every anonymizer/*.py whose basename is NOT
  an app.name (bridges dotted-app-name vs short-file-name gap).
- users.py: UserAnonym add profile_picture=fields.function(fake.file_path),
  exclude unsubscribe_categories; register_skip([UserTag]).
- forms.py: StatusChangeAnonym REMOVE employer line; add RitualProficiencyAnonym
  (anonym notes; exclude level,date,memorization,directions,performance,created,
  modified); register_skip Employer, OtherSchool.
- jobs.py: JobPostingBanAnonym (anonym reason; exclude banned_at,created,modified).
- attendance.py NEW: skip AttendanceRecord, AttendanceStatusTransition;
  clean MatchQueueItem (raw uploaded emails/names).
- contact_sync.py NEW: clean UserContactSyncToken (encrypted OAuth secrets).
- events.py: add CalendarFeedSubscription to skip.
- TimeStampedModel = created + modified.
- VALIDATE: docker exec thetataucmt_local_django python manage.py anonymize_db --check_only
