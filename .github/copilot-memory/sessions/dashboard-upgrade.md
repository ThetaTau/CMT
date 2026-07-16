# Dashboard Upgrade — Progress

## Package versions (installed + tested in container)
- dash 3.1.1 → **4.4.0** (latest; verified works with django-plotly-dash 2.5.1)
- django-plotly-dash 2.5.0 → **2.5.1**
- plotly 6.2.0 → **6.8.0**

## Done
- [x] `requirements/base.txt` bumped
- [x] `chapters/dashboard.py` modernized: dropped hardcoded `#f9f9f9` panel bg,
      added `_theme_template`, `_apply_theme`, dcc.Interval + dcc.Store +
      clientside_callback that mirrors outer `data-bs-theme` into `theme-store`,
      added `theme` kwarg (default "light") to `members_graph`/`majors_graph`/`gpa_graph`
      so existing tests still work.
- [x] NEW `regions/dashboard.py` — `RegionDashboard` DjangoDash with:
      dcc.Location→region-slug store, region selector dropdown, theme sync,
      6 KPI cards (Total members, PNMs AY, Initiations AY, Prealumni AY,
      Resignations AY, Retention), 2 tabs (Overview / Chapter Activity) with
      7 bar-by-chapter panels (members, initiations, depledges, events,
      submissions, tasks, trainings). Callbacks use lazy model imports.
- [x] `regions/urls.py` imports dashboard to register the DjangoDash app.
- [x] `regions/views.py` — dropped jwt/metabase; kept get_object override
      only for synthetic `candidate_chapter` slug.
- [x] `templates/regions/region_detail.html` — swapped iframe for
      `plotly_direct name="RegionDashboard"`.
- [x] `static/css/project.css` — added `.tt-dashboard-panel`, tabs and
      region-selector theme-aware styles.
- [x] NEW `regions/tests/test_dashboard.py` — 27 tests covering helpers,
      callbacks, and DB integration.
- [x] All chapter dashboard tests (22) still pass.
- [x] All regions tests (51 total incl. new 27) pass.

## Function signature changes
- `chapters/dashboard.py::members_graph(data, years, status, theme="light", year_info=None, **kwargs)` — theme moved into position 4 as default
- `chapters/dashboard.py::majors_graph(data, yearterm, theme="light", **kwargs)` — theme added with default
- `chapters/dashboard.py::gpa_graph(data, years, theme="light", year_info=None, **kwargs)` — theme in position 3 as default
- `chapters/dashboard.py::layout(fig, title, YEARS, theme="light")` — theme added as optional

## Pending / next
- [x] `UserAlterForm` chapter dropdown made dynamic (moved `Chapter.chapter_choices()`
      call into `__init__`).
- [x] `DynamicScopeFilterSetMixin` added in [core/filters.py](core/filters.py):
      rebuilds `chapter`/`region` ChoiceFilter choices on every FilterSet
      instantiation. Skips `ModelChoiceFilter` (auto-generated from
      `Meta.fields`) since it takes `queryset=` not `choices=`.
- [x] Mixin applied to: `BallotCompleteFilter`, `ChapterBalanceListFilter`,
      `AuditListFilter`, `CompleteListFilter`, `AlumniExclusionListFilter`,
      `RiskListFilter`, `EducationListFilter`, `BylawsListFilter`,
      `GearArticleListFilter`, `UserRoleListFilter`, `AdvisorListFilter`.
- [x] Confirmed `events/objectives/trainings` filters already re-evaluate
      choices per-request (in `__init__`) — no fix needed.
- [x] Confirmed `chapters/filters.py` uses `choices=Region.region_choices`
      (callable, no parens) — already dynamic via django-filter's lazy resolution.

## Known-but-not-fixed module-import-time evaluations
Documented these to the user; deferring the fix because it touches many files.
- `core/models.py::TODAY`, `TOMORROW`, `TODAY_START`, `TODAY_END` — frozen
  at worker startup; stale after midnight. Used 84 times across 14 files.
- `core/models.py::current_year_value`, `BIENNIUM_START`, `BIENNIUM_START_DATE`,
  `BIENNIUM_END_DATE`, `BIENNIUM_YEARS`, `BIENNIUM_DATES` — recomputed only
  on worker restart; changes every 2 years at convention.
- `core/filters.py` `BIENNIUM_FILTERS` and `DateRangeFilter.choices` biennium
  options — same story, driven by `BIENNIUM_DATES`.

## Files to change
1. `requirements/base.txt` — bump versions
2. `thetatauCMT/chapters/dashboard.py` — modernize chapter dashboard, add dark mode
3. `thetatauCMT/regions/dashboard.py` — NEW file, RegionDashboard DjangoDash
4. `thetatauCMT/regions/urls.py` — import dashboard to register app
5. `thetatauCMT/templates/regions/region_detail.html` — replace metabase iframe with plotly
6. `thetatauCMT/regions/views.py` — drop jwt/metabase, pass region_slug to template
7. `thetatauCMT/chapters/tests/test_dashboard.py` — update if API changes
8. NEW `thetatauCMT/regions/tests/test_dashboard.py` — basic tests for new dashboard

## Design
- `RegionDashboard` accepts region_slug via initial_arguments; user can switch via dropdown
- Metrics (KPI cards): Total members, PNMs AY, Initiations AY, PreAlums AY, Resignations AY, Retention
- Graph 1: Students by chapter, colored by region
- Graph 2: Initiations by chapter, colored by region
- Tabs: Overview / Chapter Activity (brainstorm: events, tasks, trainings, submissions per chapter)
- Dark mode: clientside callback watches `data-bs-theme` on documentElement, updates dcc.Store
  which figure callbacks read to pick `plotly_white`/`plotly_dark` template

## Container commands
- Test: `podman exec thetataucmt_local_django pytest thetatauCMT/chapters/tests/test_dashboard.py -v --tb=short`
- Install: pip is run at container build time; just update requirements file — but for testing
  after updating we can `podman exec thetataucmt_local_django pip install -U <pkg>`

## Baseline (from repo memory)
- 1203 pass, 19 skipped, 1 pre-existing failure (chapter_detail_view)
