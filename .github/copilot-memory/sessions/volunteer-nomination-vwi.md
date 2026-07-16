# Volunteer Nomination work items (VWI-*)

## Task
Build a config-driven, viewflow-based Volunteer Nomination lifecycle.
Per-WI workflow: (1) propose models/migrations FIRST + PAUSE, (2) flow nodes,
(3) views/forms/templates, (4) tests per acceptance criterion.

## Key codebase facts (viewflow 1.11.0, Django 4.2)
- Flows live in `<app>/flows.py`; viewflow `ViewflowFrontendConfig.ready()` does
  `autodiscover_modules('flows')` -> imports EVERY app's flows.py. NO ModuleMixin
  AppConfig needed for the flow to register (users app is plain AppConfig + flows.py).
- Decorate flow: `@register_factory(viewset_class=FilterableFlowViewSet)` (from core.flows).
- URLs auto-created under `viewflow:<app_label>:<processmodel_lower>:start` etc.
  (e.g. `viewflow:forms:hseducation:start`). Frontend mounted at `^workflow/`.
- Flow API: `from viewflow import flow`; `from viewflow.base import Flow, this`;
  `from viewflow.compat import _`. Nodes: flow.Start(View), flow.StartFunction,
  flow.View, flow.If(cond).Then().Else(), flow.Switch().Case(cond).Default(),
  flow.Handler(func), flow.Function(func, task_loader=...), flow.Split/Join, flow.End.
  `.Next(this.x)`, `.Assign(lambda act: <User>)`, `.Permission("auth.perm")`.
- Process model: `class X(Process, EmailSignalMixin)` in `<app>/models.py`
  (`from viewflow.models import Process`). Factory sets `flow_class = XFlow`.
- Start view = `class V(LoginRequiredMixin, CreateProcessView)` (from
  viewflow.flow.views), model=, form_class=, `activation_done()` calls
  `self.activation.done()`.
- Placeholder/stub node pattern (navigable, testable):
  `flow.Function(this.placeholder, task_loader=lambda ft,t: t)` +
  `@method_decorator(flow.flow_func) def placeholder(self, act, task): act.prepare(); act.done()`.
- Config: `Config.get_value(key)` (configs app, key/value CKEditor). 
- Reviewer assign examples: `.Assign(lambda act: User.objects.get(username=settings.EXECUTIVE_DIRECTOR))`.
- core.models: NAT_OFFICERS (list of role strings), NAT_OFFICERS_CHOICES [(role,Title)],
  CHAPTER_OFFICER, EnumClass, TimeStampedModel. `multiselectfield.MultiSelectField` used in codebase.
- Tests: `core/factories.py TaskFactory` (create Task at a node, runs activation);
  forms/tests/test_flows.py (import/roundtrip). Factory `flow_class = XFlow`.
- Run tests: `podman exec thetataucmt_local_django pytest <path> -v --tb=short`.
- New local app: add to LOCAL_APPS in config/settings/base.py; add anonymizer/<app>.py
  or `anonymize_db --check_only` fails (only affects that cmd, not tests).

## Proposed design (PENDING USER CONFIRMATION - paused after models)
- New app `thetatauCMT/nominations/`.
- `Nomination(Process)` fields: nominee FK User null, nominee_name, nominee_email,
  nominator FK User, level (EnumClass Chapter/Regional/National),
  recommended_positions MultiSelectField(NAT_OFFICERS_CHOICES),
  reason TextField, discussed_with_nominee bool, not_interested bool,
  consent_token UUID unique, + flow-state: consent_status
  (pending/interested/not_interested/follow_up_later), vetting_passed null-bool,
  interview_passed null-bool, training_completed bool, confirmed null-bool,
  appointed bool, + step notes TextFields.
- DECISION (user, 2026-07-12): use EXISTING config system (configs.Config key/value),
  NOT a dedicated model. `get_reviewer_for(node_key)` reads `Config.get_value(node_key)`
  (keys: VolunteerReviewer, VettingReviewer, Interviewer, TrainingAdministrator,
  Confirmer, AppointmentProcessor, CentralOffice); value = username/email OR a
  NAT_OFFICERS role name. Resolve: username/email match > current role holder
  (User.current_roles__contains=[role]) > CentralOffice config > EXECUTIVE_DIRECTOR > None.
- Answers to paused Qs: app=NEW nominations app (auto-decided); reviewer store=EXISTING
  Config; extra flow-state fields=YES.
- Flow: Start(NominationCreateView) -> consent(View) -> If interested -> vetting(View)
  -> If pass -> interview(View) -> If pass -> training(View) -> confirmation(View)
  -> If confirm -> appointment(View) -> End(appointed). Branches: not_interested->End(closed);
  vetting/interview fail -> rejection Handler -> End; confirm deny -> denial -> End.

## POST-VWI polish (2026-07-13) — 14 change requests
1. nominee must be a member (form requires nominee; drop non-member path)
2. profile "Nominate" button + base nav link
3. after submit -> redirect to nominee profile + profile note "submitted for consideration" (regular users have NO workflow-site access)
4. reason help text: shared with nominee
5. consent form shows what they were nominated for
6. not_interested stored/visible on User admin
7. User admin -> link to profile page
8. process_list.html shows nominee + nominee chapter
9. nominee kept updated via email at each step + process tracking on profile
10. natoff page: list of nominations + status + link to nominate
11. follow-up updates last_contacted (mostly done - verify)
12. NominationContact log model + inline on admin (all contacts captured)
13. level -> multi-select (level + interested_level); interested in multiple levels
14. profile nominate button greyed if not_interested + note; owner can override; form lets member submit own interest overriding not_interested
Plan: models(13,12)+migration -> User helpers(6,14) -> forms(1,4,14) -> views(2,3,10) -> templates -> admin(6,7,12) -> emails(9)+contact log(12). Run tests after each group.

## Status
- VWI-1: DONE (2026-07-12).
- VWI-2: DONE (2026-07-12). Start view/form (built in VWI-1) refined: exact
  not-interested block message ("This person has indicated they are not
  interested."), multi-submission allowed. 7 HTTP view tests in
  nominations/tests/test_views.py. Full suite 1694 pass / 17 skip / 0 fail.
- VWI-3: DONE (2026-07-12). Tokenized no-login consent: consent_token_expires +
  interested_positions/level fields (migration 0002); tokens.py util; herald
  NomineeConsentNotification + template; send_consent_request Handler (start ->
  handler -> nominee_consent); public NomineeConsentView at
  nominations/consent/<uuid:token>/ completes the waiting task via
  services.complete_consent_task; NomineeConsentForm. 15 tests in
  test_consent.py. Full suite 1709 pass / 17 skip / 0 fail.
- VWI-4: DONE (2026-07-12). Follow-up loop + re-contact hook. last_activity +
  last_contacted fields (migration 0003). follow_up_end End REPLACED by parked
  follow_up_wait flow.Function looping back to send_consent_request. Re-contact
  hook services.recontact_nomination(nomination) = follow_up_wait.run(task) ->
  reissues token+email -> returns to nominee_consent. + is_awaiting_follow_up,
  nominations_awaiting_follow_up(before). 10 tests in test_follow_up.py; updated
  2 existing follow_up tests. Full suite 1719 pass / 17 skip / 0 fail. Next:
  vetting/interview/training/confirmation/appointment node UIs, or VWI-12 daily
  command (calls recontact_nomination).
