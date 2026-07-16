# Mailjet open/read-receipt tracking (herald + all app email)

## Goal
Read receipts (opens) + click/bounce/etc for herald emails AND all app email, using
Mailjet's NATIVE tracking via django-anymail (already installed 13.0). NO custom pixel.

## Verified facts
- herald 0.3.0: SentNotification statuses = Pending/Success/Failed/UserDisabled only.
  _send() builds EmailMultiAlternatives + mail.send(). NO open tracking / webhooks.
- anymail Mailjet backend: message.track_opens/track_clicks -> TrackOpens/TrackClicks.
  message.metadata -> Mailjet EventPayload (echoed back as Payload -> event.metadata).
- anymail webhook: anymail/mailjet/tracking/ -> `tracking` signal (AnymailTrackingEvent:
  event_type, message_id=str(MessageID), recipient, metadata, tags, click_url,
  user_agent, timestamp, reject_reason, mta_response, esp_event).
- anymail post_send signal (args message, status, esp_name); status.recipients[email].message_id
  = Mailjet MessageID. post_send uses send_robust BUT anymail RE-RAISES receiver exceptions
  -> receiver MUST be defensive (try/except, never raise).
- webhook `tracking` dispatched via signal.send (not robust) -> receiver raise => HTTP500 retry
  -> receiver MUST be defensive.
- Webhook security: ANYMAIL["WEBHOOK_SECRET"]="user:pass" basic auth (warns if unset).
- EMAIL_BACKEND wiring: base default filebased; production -> anymail mailjet; staging ->
  core.email.MyHijackBackend; test -> locmem (locmem does NOT fire anymail signals -> no
  test-suite impact). DJANGO_EMAIL_LIVE gates.
- User has email + email_school; User.emails property = {email, email_school}. allauth EmailAddress.
- DEFAULT_AUTO_FIELD BigAutoField. Local apps under thetatauCMT/<app>, label = <app>.
- Anonymizer: NEW local app REQUIRES anonymizer/<app>.py or anonymize_db --check_only fails.
  SentNotification is register_clean (PII). Mirror for tracking models.

## Correlation chain
1. send -> post_send -> TrackedEmail(message_id, recipient, subject, metadata, user).
2. herald SentNotification post_save -> link recent TrackedEmail (subject+recipient+time window).
3. Mailjet webhook -> tracking signal -> match TrackedEmail by message_id(+recipient),
   record EmailTrackingEvent + update opened_at/open_count/etc. get_or_create TrackedEmail
   if missing (webhook may arrive w/o prior post_send record).

## Files (new app thetatauCMT/email_tracking/)
- apps.py (ready() imports signals), models.py (TrackedEmail, EmailTrackingEvent),
  signals.py (post_send, tracking, SentNotification post_save; all defensive),
  admin.py, migrations/0001, management/commands/register_mailjet_webhook.py (uses requests),
  tests/ (test_signals, test_backend, test_webhook).
- anonymizer/email_tracking.py (register_clean both models).
- core/email.py: TrackingEmailBackendMixin + TrackingMailjetBackend; MyHijackBackend gets mixin.
- config/settings/base.py: add app to LOCAL_APPS (before email_signals), EMAIL_TRACK_OPENS/CLICKS
  defaults True, ANYMAIL webhook secret from env.
- config/settings/production.py: EMAIL_BACKEND=core.email.TrackingMailjetBackend, WEBHOOK_SECRET.
- config/urls.py: path("anymail/", include("anymail.urls")).
- docs/email_tracking_setup.md.

## Status: DONE — 17 tests pass, full suite 1787 pass / 17 skip / 0 fail.
Details captured in /memories/repo/thetatauCMT-status.md (top entry).

## Follow-up DONE (2026-07-13): admin member-communication lookup via live Mailjet API
mailjet-rest==1.7.0 wrapper (mailjet_api.py), MemberCommunicationView/MessageHistoryView/
MemberAutocomplete (natoff-gated), forms.py, urls.py, member_communication.html template,
profile link. +18 tests. Full suite 1805 pass / 17 skip / 0 fail. GOTCHAS: no underscore-
prefixed template keys; don't name context key `messages` (collides w/ Django messages).

## Follow-up 2 DONE (2026-07-13): 4 refinements to member-communication page
(1) button moved to profile header (2nd line, w-100 flex break); (2) pagination (page_size 25,
Limit/Offset, get_messages_for_email now returns {"data","total","count"}, Prev/Next);
(3) ShowSubject=true added; (4) combined w/ internal tracking (fallback to TrackedEmail/
EmailTrackingEvent when API unconfigured/errors; source badges). +4 tests (39 in app).
Full suite 1809 pass / 17 skip / 0 fail. GOTCHA: Django templates can't `is not None` -> has_tracking bool.

## Follow-up 3 DONE (2026-07-13): pagination count fix
Mailjet /message Total == page Count (not grand total) -> has_next always False (user saw only 25).
Fixed: has_next = full-page heuristic; NEW get_message_count(email) via countOnly=1 for real total.
+4 tests (43 in app). Full suite 1813 pass / 17 skip / 0 fail. GOTCHA: view tests hitting _from_api
must patch BOTH get_messages_for_email AND get_message_count.

## Follow-up 4 DONE (2026-07-13): all-emails + date/subject search
(1) _emails_for_user gathers email+email_school+allauth EmailAddress. (2) date (FromTS/ToTS server-side)
+ subject (client-side; Mailjet can't filter subject) search. Two modes: browse=API pagination,
search=scan 200/addr + in-memory filter+paginate. _from_local applies filters in SQL too.
+5 tests (48 in app). Full suite 1818 pass / 17 skip / 0 fail.

## Follow-up 5 DONE (2026-07-13): async table load
Shell page renders instantly (no API in get_context_data); table loads via AJAX from NEW
MemberCommunicationResultsView (communication/results/, renders _results.html partial).
Vanilla-JS: form submit + pagination + history all update ONLY #comm-results (fetch + pushState;
delegated listeners). Table-content view tests now GET the results url. +3 tests (51 in app).
Full suite 1821 pass / 17 skip / 0 fail.

## Follow-up 6 DONE (2026-07-13): consolidate mixin + reuse autocomplete
NationalOfficerRequiredMixin -> ONE copy in core.views (configurable redirect/message);
attendance/events/nominations/email_tracking import it, deleted local copies + trimmed unused imports.
email_tracking form reuses users:autocomplete (forward chapter=false; is_officer_group includes natoff);
removed MemberAutocomplete + url + 2 tests. Fixed latent config/urls.py SETTINGS_MODULE-None crash
under override_settings. Full suite 1819 pass / 17 skip / 0 fail. flake8 clean.

## Follow-up 9 DONE (2026-07-14): live-connect fixes + campaign-grouped history + navbar
Verified live with real key (email venturafranklin@gmail.com). FIXES:
(1) ENDPOINT BUG: activity endpoint is `/api/subscribers/{id}/activity-log` NOT `/activity`
(/activity 404s "Resource does not exist"). Fixed get_subscriber_activity; 404->[]. Real entry
shape {log_name, created_at "YYYY-MM-DD HH:MM:SS", properties:{campaign_id, campaign_name}}.
activity_subject reads properties.campaign_name.
(2) TYPED-EMAIL "doesn't search" was just the /activity 404; now works (probe: 5 grouped rows).
(3) CAMPAIGN-GROUPED HISTORY: _mailerlite_rows groups activity by campaign (key c:{campaign_id}
or s:{subject}) into ONE row/campaign via _mailerlite_group_row (opens=count email_open,
clicks=count link_click, status Clicked>Opened>Sent>latest, history_events list). Added
_mailerlite_event/_mailerlite_group_key/_mailerlite_group_row; removed old _mailerlite_row.
_MAILERLITE_LABELS + _STATUS_BADGE got real log_names.
(4) TEMPLATE _results.html: MailerLite "History" button reuses js-history handler with NO
data-history-url + pre-rendered hidden <tr id=mlhist-{{forloop.counter}} data-loaded="1"> (toggle
only, no fetch). (5) MULTI-EMAIL already worked; added test. (6) NAVBAR link "Member Email
Communication" (email_tracking:member_communication) in natoff National dropdown in base.html.
Tests: api endpoint->/activity-log + _FakeSession /activity-log route + 404 test + properties test;
view +3 (typed-email-no-mailjet, groups-by-campaign, checks-all-member-emails). email_tracking 79.
FULL SUITE 1861 pass / 17 skip / 0 fail. flake8 clean. Probe gotcha: sys.path.insert(0,"/app").


## Follow-up 8 DONE (2026-07-14): two-way MailerLite sync (unsubscribe + send)
(1) AUTO-UNSUBSCRIBE: when a member globally opts out (UnsubscribeConfirmView POST with
"all" -> unsubscribe_email True) OR User.set_no_contact(), mirror to MailerLite. Hooks call
`from thetatauCMT.email_tracking import mailerlite_sync; mailerlite_sync.unsubscribe_user(user)`
(lazy import). Single-category opt-out does NOT sync (only global). (2) ADMIN ACTION
"Send selected users to MailerLite" on MyUserAdmin (users/admin.py actions list + method,
`from django.contrib import admin, messages`) -> mailerlite_sync.send_users(queryset); guards on
is_configured; message_user summary added/exists/skipped/errors.
NEW mailerlite_api write fns: upsert_subscriber(email,fields,status,groups) POST /api/subscribers;
unsubscribe(email) (get_subscriber; if exists & not already unsub -> upsert status=unsubscribed;
returns bool; NEVER creates); subscribe_if_absent(email,fields) (get_subscriber; if None -> upsert
status=active returns "added" else "exists"; NEVER resurrects unsubscribed). _check now accepts 2xx
(POST returns 201). NEW mailerlite_sync.py: unsubscribe_user(user) (iterates user emails email+
email_school deduped, best-effort, is_configured->0, catches _SYNC_ERRORS=Config/API/requests.
RequestException), send_user(user)->added/exists/skipped, send_users(users)->summary dict.
Tests: test_mailerlite_api +6 (upsert/unsub x3/subscribe x2, _FakeSession got .post), NEW
test_mailerlite_sync.py 8 (fake _User + monkeypatch api), users/test_views +3 (set_no_contact
syncs, unsub-all syncs, single-category no-sync; patch thetatauCMT.email_tracking.mailerlite_sync.
unsubscribe_user), users/test_admin +2 (action delegates when configured / guards when not;
MyUserAdmin(User,AdminSite()) + mock message_user + RequestFactory). NO models/migrations/anonymizer.
Docs updated. flake8 clean. FULL SUITE 1857 pass / 17 skip / 0 fail (~141s). email_tracking 75.
GOTCHA: image was STALE (missing django-ical + mailjet-rest); rebuilt via
`podman-compose -f docker-compose.local.yml build django` (EXIT 0) -> then run/tests green.

## Follow-up 7 DONE (2026-07-14): MailerLite subscriber-activity source
Another org uses mailerlite.com. NEW thetatauCMT/email_tracking/mailerlite_api.py (requests-based,
no SDK): is_configured() (settings.MAILERLITE_API_KEY ONLY, base.py reads env), get_subscriber(email)
(GET /api/subscribers/{quote(email)}, 404->None), get_subscriber_activity(id), get_activity_for_email(email)
(subscriber lookup then activity; [] if not subscriber). Exceptions MailerLiteConfigurationError/APIError.
View _lookup: _mailerlite_rows(emails) FIRST; if mailerlite_rows or is_search -> _search_api(extra_rows=);
else _from_api; on Mailjet error/no-Mailjet -> _from_local(extra_rows=). _mailerlite_row: message_id=""
(no History btn), source="MailerLite", status=activity_type. config/settings/base.py MAILERLITE_API_KEY env.
config/settings/test.py MAILERLITE_API_KEY="" (tests never hit real API). Template: warning must contain
"not configured" substring; MailerLite mentioned in intro. Tests: test_mailerlite_api.py (11, fake session),
+2 view tests (includes_mailerlite_activity, skips_when_unconfigured). Docs updated.
GOTCHA: removed env fallback from _api_key so test.py override is authoritative.
ENV BLOCKER: container thetataucmt_local_django NOT running (port 8000 held by vs_board_local_django);
image was STALE (missing django-ical AND mailjet-rest that were added to requirements) -> ran
`podman-compose build django` to rebuild. My 2 MailerLite view tests already PASSED in a partial run
(they were NOT in the failure list); the 11 failures were all pre-existing mailjet-rest-missing env issues.
NEXT: after rebuild, run email_tracking suite + full suite via
`podman-compose -f docker-compose.local.yml run --rm --no-deps -T django pytest ...` (redirect to file + grep;
PowerShell mangles inline stderr). Then flake8 test files. Then finalize memory numbers.
