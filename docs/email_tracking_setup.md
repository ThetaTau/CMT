# Email open/read tracking (Mailjet)

The application sends all email through **Mailjet** via
[django-anymail](https://anymail.dev/). Read receipts (opens), click tracking,
bounces, spam complaints and unsubscribes are captured using **Mailjet's own
tracking** — there is no custom open-pixel. Everything is surfaced through
Anymail's normalized webhook events and stored by the `email_tracking` app.

This covers **all** outbound email: django-herald notifications (herald itself
has no open-tracking), allauth emails, and any plain `send_mail()` call.

## How it works

1. **Tracking is enabled on every message.** `core.email.TrackingMailjetBackend`
   (the production `EMAIL_BACKEND`) sets `track_opens` / `track_clicks` on each
   message, which Anymail maps to Mailjet's `TrackOpens` / `TrackClicks`.
   Toggle with the `EMAIL_TRACK_OPENS` / `EMAIL_TRACK_CLICKS` env vars.
2. **Mailjet calls a webhook** for each event (sent, open, click, bounce,
   blocked, spam, unsub). Anymail receives it at
   `/anymail/mailjet/tracking/` and fires its `tracking` signal.
3. **`thetatauCMT.email_tracking.signals`** records each event as an
   `EmailTrackingEvent` and rolls the state up onto a `TrackedEmail`
   (open counts, first/last opened, bounced, etc.), correlating by Mailjet's
   `MessageID`. When the email came from a herald notification, the
   `TrackedEmail` is linked back to herald's `SentNotification` (which stores the
   full rendered content).

View results in the Django admin under **Email Tracking → Tracked emails**
(with a per-message event log) and **Email tracking events**.

## One-time setup

### 1. Environment variables

```bash
# Already required for sending:
export MAILJET_API_KEY='...'
export MAILJET_SECRET_KEY='...'

# Secure the webhook (HTTP basic auth "user:pass"). Use the SAME credentials in
# the webhook URL you register with Mailjet.
export ANYMAIL_WEBHOOK_SECRET='someuser:somelongrandompassword'

# Optional (default true):
export EMAIL_TRACK_OPENS=true
export EMAIL_TRACK_CLICKS=true
```

### 2. Register the webhook with Mailjet

Either register it in the [Mailjet dashboard]
(Account settings → Event notifications / triggers) pointing at:

```
https://<user>:<pass>@cmt.thetatau.org/anymail/mailjet/tracking/
```

…or run the bundled management command (uses the Mailjet REST API):

```bash
# Uses settings.CURRENT_URL + the anymail tracking path
python manage.py register_mailjet_webhook

# or provide the full public https URL (include basic-auth if you set a secret)
python manage.py register_mailjet_webhook \
    --url 'https://someuser:somelongrandompassword@cmt.thetatau.org/anymail/mailjet/tracking/'

# check what is registered
python manage.py register_mailjet_webhook --list
```

> Mailjet requires a publicly reachable **https** endpoint. For local testing,
> expose your dev server with a tunnel and register that URL.

## Looking up a member's communication (National Officers)

Besides the passive webhook tracking above, National Officers / admins can pull
a member's email history **live from Mailjet on demand** at:

```
/email-tracking/communication/
```

- Reachable from any member profile page (National-officer-only section) via the
  **"View email communication"** button, which pre-selects that member.
- You can also pick any member with the search box, or type **any email
  address** to check.
- The page lists every message Mailjet sent to that address (date, subject,
  status, plus the locally-recorded open/click counts). Click **History** on a
  row to expand its full delivery/open/click timeline.

This uses the Mailjet REST API via the
[`mailjet-rest`](https://github.com/mailjet/mailjet-apiv3-python) library
(`message` filtered by `ContactAlt`, then `messagehistory` by message id). It
reuses the same `MAILJET_API_KEY` / `MAILJET_SECRET_KEY` credentials Anymail
sends mail with (falling back to the `MJ_APIKEY_PUBLIC` / `MJ_APIKEY_PRIVATE`
env vars from Mailjet's own examples). No extra configuration is needed beyond
the sending credentials; if they are missing the page shows a clear notice.

## Notes

- If `ANYMAIL_WEBHOOK_SECRET` is not set, Anymail logs a warning that the webhook
  is open to the public — always set it in production.
- Opens/clicks depend on the recipient's email client loading remote images /
  following links, so they are a lower bound (Mailjet caveat, not ours).
- Tracking never blocks or breaks sending: the signal receivers are fully
  defensive and only log on error.
