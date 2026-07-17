# Awards QA seed data (`seed_awards_demo`)

`seed_awards_demo` (AWI-14) populates the database with a coherent, cross-referenced
set of Awards data so the whole feature (AWI-1…AWI-13) can be QA'd end-to-end.

```bash
docker exec thetataucmt_local_django python manage.py seed_awards_demo --force
docker exec thetataucmt_local_django python manage.py seed_awards_demo \
    --flush-awards --seed 42 --scale medium --force
```

## Flags

| Flag | Purpose |
|---|---|
| `--flush-awards` | Delete existing **`[DEMO]`** awards data (only) before seeding. Never touches members, chapters, regions, or any non-demo awards row. |
| `--seed <int>` | Seed the RNG + Faker for reproducible output. |
| `--scale <small\|medium\|large>` | Volume of generated grants / nominations / members (default `small`). |
| `--force` | Required when `settings.DEBUG` is off (production-like). Without it the command refuses to run. |

## Guardrails

- All generated records are tagged with a `[DEMO] ` prefix (award / cycle names, and
  any demo member / chapter / region created only when the environment is empty).
- **Reuses** existing members, chapters, and regions when present; only creates the
  minimum demo supporting records if none exist.
- Idempotent: catalog objects are `get_or_create`d, grants/artifacts are
  existence-checked, and nominations are created only up to the target count, so
  re-running never duplicates. `--flush-awards` gives a fully clean reseed.

## What gets created

- **AwardTypes** — one per level (member, chapter, region, alumni, active, PNM,
  national), mixing `direct` / `nomination_workflow`, `one_time` / `recurring`,
  single- vs multiple-winner, and multi-nomination on/off, plus one **retired** award.
- **AwardCycles** — a past year (2019, 2023), the current year, a current **term**,
  and an **event**-type cycle (linked to an existing Event when one is present).
- **EligibilityRules** — member-status (active / alumni / PNM), chapter-scope,
  region-scope, and a custom-hook stub.
- **AwardGrants** — member / chapter / region recipients; every `source`
  (`direct`, `nomination`, `import`); at least one **backdated** and one **revoked**
  grant; and a **group grant** producing one individual grant per member. One grant
  is created through the real `direct_grant` service (exercises eligibility + winner rules).
- **AwardNominationProcess** — pending (in review), approved (with a resulting grant),
  and rejected (with a reason), routed to the config-driven approver.
- **GrantArtifacts** — one generated certificate and one uploaded letter.
- **OfficerBadges** — a couple of national-officer icons, with the demo approver given
  a national-officer role so inline name icons render.
- **Config** — `AwardApprover` points at the seeded demo approver so the nomination
  reviewer queue is populated.

## Suggested QA walkthrough

| Feature area | Where to look |
|---|---|
| Award catalog (AWI-1/2/4) | Django admin → Award Types / Award Cycles / Eligibility Rules. |
| Direct grant (AWI-5) | `/awards/grant/` as an officer; confirm winner/eligibility enforcement. |
| Nomination + approval (AWI-6/7) | Viewflow inbox for the demo approver; see pending / approved / rejected. |
| Certificates (AWI-8) | A grant's certificates page; one generated + one uploaded artifact. |
| Notifications / digest (AWI-9) | `python manage.py award_digest --dry-run` over a seeded month. |
| Profile badges / inline icons (AWI-10) | The demo approver's profile (award badges + officer icon). |
| Public dashboard (AWI-11) | `/awards/directory/` — filter by type / level / cycle / chapter / region. |
| Reports / exports + history (AWI-12) | `/awards/history/member/<username>/`; officer CSV / Excel export. |
| Bulk import + match queue (AWI-13) | `/awards/import/` then `/awards/import/queue/` as an admin. |

Run with `--flush-awards` any time to reset the demo dataset to a clean, consistent state.
