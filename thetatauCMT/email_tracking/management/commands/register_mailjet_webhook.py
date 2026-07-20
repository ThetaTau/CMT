"""Register (or list) the Mailjet event webhook that feeds email open tracking.

Mailjet delivers delivery/engagement events (sent, open, click, bounce, blocked,
spam, unsub) to an "event callback URL". django-anymail exposes a receiver for
those at ``/anymail/mailjet/tracking/`` which turns them into the ``tracking``
signal consumed by :mod:`thetatauCMT.email_tracking.signals`.

This command registers that URL with Mailjet's REST API so you don't have to do
it by hand in the Mailjet dashboard. It uses the same ``MAILJET_API_KEY`` /
``MAILJET_SECRET_KEY`` credentials Anymail sends mail with.

Examples::

    # Register using CURRENT_URL + the anymail tracking path
    python manage.py register_mailjet_webhook

    # Register an explicit public URL (e.g. behind a proxy / ngrok)
    python manage.py register_mailjet_webhook --url https://cmt.thetatau.org/anymail/mailjet/tracking/

    # Just show what is currently registered
    python manage.py register_mailjet_webhook --list
"""

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

MAILJET_EVENT_API = "https://api.mailjet.com/v3/REST/eventcallbackurl"

# Mailjet event types Anymail knows how to parse.
EVENT_TYPES = ["sent", "open", "click", "bounce", "blocked", "spam", "unsub"]


class Command(BaseCommand):
    help = "Register the Anymail/Mailjet tracking webhook with Mailjet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            dest="url",
            default=None,
            help=(
                "Full public https URL of the tracking webhook. Defaults to "
                "settings.CURRENT_URL + the anymail mailjet tracking path."
            ),
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_only",
            help="Only list the currently registered event callback URLs.",
        )
        parser.add_argument(
            "--events",
            dest="events",
            default=",".join(EVENT_TYPES),
            help="Comma separated Mailjet event types to register.",
        )

    def _auth(self):
        anymail = getattr(settings, "ANYMAIL", {}) or {}
        api_key = anymail.get("MAILJET_API_KEY")
        secret_key = anymail.get("MAILJET_SECRET_KEY")
        if not api_key or not secret_key:
            raise CommandError(
                "MAILJET_API_KEY / MAILJET_SECRET_KEY are not configured in "
                "settings.ANYMAIL; cannot talk to the Mailjet API."
            )
        return (api_key, secret_key)

    def _default_url(self):
        current = getattr(settings, "CURRENT_URL", "") or ""
        path = reverse("anymail:mailjet_tracking_webhook")
        return current.rstrip("/") + path

    def handle(self, *args, **options):
        auth = self._auth()

        if options["list_only"]:
            response = requests.get(MAILJET_EVENT_API, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json().get("Data", [])
            if not data:
                self.stdout.write("No event callback URLs registered.")
            for item in data:
                self.stdout.write(
                    f"{item.get('EventType'):8} {item.get('Status'):6} "
                    f"backup={item.get('IsBackup')} {item.get('Url')}"
                )
            return

        url = options["url"] or self._default_url()
        if not url.startswith("https://"):
            self.stdout.write(
                self.style.WARNING(
                    f"Webhook URL is not https ({url!r}); Mailjet requires a "
                    "publicly reachable https endpoint in production."
                )
            )

        events = [e.strip() for e in options["events"].split(",") if e.strip()]
        for event_type in events:
            payload = {
                "EventType": event_type,
                "Url": url,
                "Status": "alive",
                "IsBackup": False,
            }
            response = requests.post(MAILJET_EVENT_API, auth=auth, json=payload, timeout=30)
            if response.status_code in (200, 201):
                self.stdout.write(self.style.SUCCESS(f"Registered '{event_type}' -> {url}"))
            elif response.status_code == 400 and "already" in response.text.lower():
                self.stdout.write(f"'{event_type}' already registered -> {url}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed '{event_type}' ({response.status_code}): " f"{response.text[:300]}")
                )

        self.stdout.write("Done. Verify with: python manage.py register_mailjet_webhook --list")
