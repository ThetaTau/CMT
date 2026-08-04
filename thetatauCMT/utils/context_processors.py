from html import unescape

from django.conf import settings


def settings_context(_request):
    """Settings available by default to the templates context."""
    # Note: we intentionally do NOT expose the entire settings
    # to prevent accidental leaking of sensitive information
    return {"DEBUG": settings.DEBUG}


def feature_flags(_request):
    """Expose config-driven feature flags to every template.

    Each flag is read live from the ``configs.Config`` table, so toggling the
    matching Config row takes effect on the next request without a redeploy.
    Features are enabled unless a Config row disables them (see
    ``Config.feature_enabled``). Templates reference these context variables
    (not the raw Config keys) so the keys can change without touching templates.
    """
    from thetatauCMT.configs.models import Config

    return {
        "feature_awards_enabled": Config.feature_enabled("FEATURE_AWARDS"),
        "feature_jobs_enabled": Config.feature_enabled("FEATURE_JOBS"),
        "feature_events_calendar_enabled": Config.feature_enabled("FEATURE_EVENTS_CALENDAR"),
    }


def incident_report(_request):
    """Expose the config-driven Incident Report form URL to every template.

    Read live from the ``configs.Config`` key ``INCIDENT_REPORT_URL`` so the
    central office can repoint the form without a redeploy. Anything that is
    not an ``http(s)`` link is dropped so an edited Config value cannot put a
    ``javascript:`` URL in the site footer; a blank result hides the section.
    """
    from thetatauCMT.configs.models import Config

    url = unescape(Config.get_value("INCIDENT_REPORT_URL", clean=True)).strip()
    if not url.lower().startswith(("http://", "https://")):
        url = ""
    return {"incident_report_url": url}
