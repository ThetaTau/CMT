# Guides QA script

The feature discovery work (TWI-1…TWI-13) spans four surfaces — the Feature Catalog,
What's New, the Role Guides and the rebuilt Forms landing — and almost every rule in it is about
*who sees what*. That is exactly the kind of thing unit tests confirm and humans still get wrong, so
this is the manual pass before release.

## Seed the environment

```bash
docker exec thetataucmt_local_django python manage.py seed_guides_demo --flush --seed 42 --force
```

The command prints the accounts to use — three personas at different stages of "have I seen this
yet?", plus the current holder of each duty role in your database. Log in as those. It creates a
`[DEMO]`-prefixed feature released today and four announcements (member, officer, treasurer-only, and
one non-dismissible), and nothing else; `--flush` removes exactly what it made.

If a duty role prints `none in this database`, use `manage.py shell` to grant it, or QA that role
against a database that has one — the command deliberately does not manufacture officers, because
creating `UserRoleChange` rows fires the officer notification emails.

## The audience ladder

`public < member < officer < natoff`, and it is a floor, not a match: an officer sees everything a
member sees. Superusers are treated as `natoff`. Check each rung.

| Signed in as | Catalog `/features/` | What's New | Role Guides |
|---|---|---|---|
| **Anonymous** | Only the *Getting in* area. A sign-in prompt at the top. | Nothing. | Redirected to sign in. |
| **Plain member** | Every `member` area. **No** *Forms & workflows* officer-only entries, no `natoff` areas (*Regions & national* admin tooling). | The `[DEMO]` member announcement, the pinned notice, and the demo feature. **Not** the officer or treasurer announcements. | The index lists all ten guides but says you hold no office; no "This is your role" badge on any. |
| **Chapter officer** | Adds the officer entries: status changes, officer election report, audits, RMP signatures. | Adds the `[DEMO]` officers-only announcement. | Your office's guide is badged "This is your role"; the account menu's *What am I responsible for?* goes straight to it when you hold exactly one office. |
| **National officer** | Adds *Regions & national*: national attendance upload, the attendance match queue, the officer directory. | Everything above. | The **National Officer** guide is always yours, whatever your office — a Grand Regent holds no role a guide is written for. A Regional Director gets both that and their own. |
| **Superuser** | Same as national officer. **`awards:import_upload` must not appear** — it is `SuperuserRequiredMixin` tooling and lives only in the Administrator tools block at the bottom of the Forms landing. | Everything. | Same as national officer. |

Two paths where a leak is most likely, and both must be checked explicitly:

1. **A national officer with "Hide national officer functionality" toggled on** (`natoff_hidden`).
   Every surface must drop to the member view — no `natoff` areas in the catalog, no natoff
   announcements. If `natoff` content survives the toggle, the toggle is not being read.
2. **A national officer impersonating a chapter officer via `UserAlter`.** The catalog, Role Guide and
   Forms landing must all reflect the *impersonated* user's chapter and office, not the real one.
   The chapter shown in "Your open items" is the giveaway.

## Role targeting

Role targeting is *emphasis*, never permission. A treasurer sees the same catalog as any other
officer; what changes is what is pulled forward.

- Catalog cards for your role carry a **"Part of your Treasurer duties"** pill. The Audit form
  carries one for every chapter officer, so a Regent sees it too.
- The Forms landing's **"Who submits it"** column names every officer who owes the thing, not just
  one. The Audit must list all five chapter officers.
- **"Only show what's mine"** on the catalog and **"Only show forms for my role"** on the Forms landing
  filter to those cards. Toggling off must bring everything back — nothing is permanently hidden.
- The Forms landing shows a pinned **"For your role"** table above the groups.
- The `[DEMO] Treasurers only` announcement appears for a treasurer and for nobody else, regardless of
  audience — check it does *not* show for a regent.

## Role Guides `/features/role/`

For each seeded role, open the guide and confirm:

- **"Your open items"** lists only `Task`s whose owner is that role, only for *your* chapter, and only
  ones still outstanding. Complete a task elsewhere in the app and it must leave this table.
- **"What you will do, and when"** lists the steps in order, each with a cadence pill (Once / Every
  term / Every year / Ongoing). A step pointing at a feature you cannot see must be **absent**, not
  greyed out.
- **"Tools you have access to"** links land on the right area of the catalog, which must open that
  area's accordion panel rather than scrolling to a closed one.
- On a **national** guide, a second **"National officer tools"** list carries everything gated to
  National Officers that no role tags. A plain member reading the same guide must see neither list.
- A member holding no office gets the index with an explanatory note — **not** a 404.
- The catalog itself links back: your own guide is offered in a banner at the top, and a member with
  no office gets a link to the index instead.

## Catalog accordion

The catalog is 120-odd entries across sixteen areas, so every area is collapsed on arrival and the
filters have to drive the accordion or they would appear to do nothing:

- Each area header carries a count of the cards inside it, which follows the filters.
- **Expand all** opens every visible area and switches to **Collapse all**; closing a panel by hand
  switches it back.
- Clicking an area chip opens that area. Clicking **Everything** collapses back down.
- Typing in the search box opens every area holding a match. Clearing it collapses those again — but
  an area you opened yourself stays open.
- Loading `/features/#area-awards` directly opens *Awards*.

## What's New

- The *seen nothing* persona gets the modal on first page load; the *seen everything* persona must not
  see it at all.
- "Got it" clears the item everywhere — the modal, the `New` badge on the catalog card, and the count.
  Reload to confirm it stayed cleared.
- The non-dismissible `[DEMO]` announcement has **no** "Got it" button and survives a reload.
- `/features/whats-new/` lists the archive including things already acknowledged.

## Forms landing `/forms/`

The rebuilt page is registry-driven, so the risk is a form silently disappearing.

- Every group renders: membership, officer & chapter administration, risk & compliance, money,
  recognition & voting, national administration, and "Everything else".
- Due dates and cadence appear on rows whose feature has a `task`, and they match `/tasks/`.
- Search filters rows and the group headings hide when empty; clearing the box restores everything.
- The Administrator tools block appears **only** for superusers.

## Both themes

Repeat a short pass in **dark mode**: catalog cards, badges and pills, the What's New
modal, and the Forms landing tables. Contrast on the `New` badge and the cadence pills is the usual
casualty.

## Clean up

```bash
docker exec thetataucmt_local_django python manage.py seed_guides_demo --flush --force
```

Note that `--flush` on its own still re-seeds; it is a clean reseed, not a teardown. To leave nothing
behind, flush and then delete the `[DEMO]` rows from the admin, or restore the database.

## Related

- [feature-registry.md](feature-registry.md) — the fixture everything is driven from.
