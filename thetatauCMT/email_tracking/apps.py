from django.apps import AppConfig


class EmailTrackingConfig(AppConfig):
    name = "thetatauCMT.email_tracking"
    verbose_name = "Email Tracking"

    def ready(self):
        # Wire up the anymail post_send / tracking receivers and the herald
        # SentNotification linkage. Importing the module registers the receivers.
        from . import signals  # noqa: F401
