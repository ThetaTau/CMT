# Management Commands
### Update Balances
To update the balances of chapters

    python manage.py update_balances file_path
    # eg. python manage.py update_balances secrets/Balances090518.csv
### Export Forms
To send the central office the recent forms

    python manage.py export_forms %PASSWORD% date_start
    # python manage.py export_forms %PASSWORD% 20180917
Optional:

    # -date_end 20180920
    # Form to not send to central
    # -exclude 'mscr, init, depledge, coop, oer'
### Sync Members
To sync members with an export from the central office
The most recent export will automatically be found
in the google drive folder
    
    python manage.py sync_members
### Ballot Reminders
Re-sends an open ballot to everyone who has not voted. National Officers holding
a voting role are emailed individually; each chapter that still owes a vote gets
one email whose copy list widens the longer the chapter sits on it. Ballots are
also emailed once when they are created, from the create-a-ballot page.

| Days open | Chapter recipients |
|---|---|
| 0 (initial) | Regent and Scribe |
| 7 | Regent and Scribe |
| 14 | every chapter officer |
| 21 and every 7 days after | every chapter role holder (chairs and advisers included) plus the Regional Director(s) and the region mailbox |

Schedule this daily. A ballot is only emailed on days that are an exact multiple
of 7 from when it opened, so the ladder lands on the right day whatever weekday
the ballot was created on, plus one final reminder on the due date itself.
Voting closes at 5pm Pacific on the due date, after which the ballot stops
appearing as open and no further reminders go out.

    python manage.py ballot_reminders --dry-run
    python manage.py ballot_reminders
    # --ballot <slug> to limit, --override to ignore the 7 day cadence

### Load Feature Registry
To load or refresh the feature catalog, guided tours and role guides from the
in-repo fixture. Idempotent — rows are upserted by natural key, and anything
missing from the fixture is deactivated rather than deleted. `dbseed` runs it.

    python manage.py load_feature_registry --dry-run
    python manage.py load_feature_registry

See [specs/feature-registry.md](specs/feature-registry.md) for the file format
and how to announce, retire or flag an entry.
### Seed Guides Demo
To populate a QA environment with announcements, a recently released feature and
tour/acknowledgement history so the whole guides feature can be walked through.

    python manage.py seed_guides_demo --force
    python manage.py seed_guides_demo --flush --seed 42 --force

See [specs/guides-qa.md](specs/guides-qa.md) for the walkthrough script.
### Populate Job Majors
To load the curated job board major list from
`thetatauCMT/jobs/fixtures/job_majors.json`. Each entry is a canonical major
plus the spellings seen in the wild (typos, ampersands, degree suffixes,
department names) that collapse into it. Jobs and saved searches tagged with a
variant are repointed at the canonical row before the variant is removed.
Names are stored lowercase, matching what the job form's autocomplete creates,
so a major a member types resolves to the curated row. Majors in the database
but absent from the fixture are reported, never deleted. Safe to re-run.

    python manage.py populate_job_majors --dry-run
    python manage.py populate_job_majors
    # --path points at an alternate fixture

To consolidate a new spelling, add it to the `aliases` list of the right entry
and re-run. The command refuses to run if one spelling maps to two canonicals.
