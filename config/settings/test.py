"""
With these settings, tests run faster.
"""

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = False
CURRENT_URL = "http://testserver"
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="VFWqVoswHkeXrThYKjkVMsHKke3WHa2Umux7DhhJRBTC8vwNllCOMo7X5GTFod4X",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

DATABASES = {
    "default": env.db("DATABASE_URL_TEST", default="postgres://thetatau:test@postgres:5432/testcmt"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    }
}

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG  # noqa F405
TEMPLATES[-1]["OPTIONS"]["loaders"] = [  # type: ignore[index] # noqa F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    )
]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# https://docs.djangoproject.com/en/dev/ref/settings/#email-host
EMAIL_HOST = "localhost"
# https://docs.djangoproject.com/en/dev/ref/settings/#email-port
EMAIL_PORT = 1025

# SYSTEM CHECKS
# ------------------------------------------------------------------------------
# Silence checks that are expected/irrelevant in the test environment.
# django_recaptcha uses test keys intentionally; urls.W005 (non-unique
# namespaces) is a known structural quirk, not a regression.
SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error", "urls.W005"]

# DEPRECATION WARNINGS
# ------------------------------------------------------------------------------
# Treat Django's own DeprecationWarning as errors so regressions from the
# 3.2→4.2 upgrade (and future 4.2→5.x prep) surface immediately in pytest.
# RemovedInDjango50Warning (subclass of DeprecationWarning) is caught here;
# RemovedInDjango51Warning (subclass of PendingDeprecationWarning) is not.
#
# Known future-work warning still present in app code (out of scope for 4.2):
#   django.contrib.postgres.aggregates.StringAgg() without default= argument
#   → will change behaviour in Django 5.0.  Fix: add default="" to each call
#   in core/models.py and thetatauCMT/forms/views.py before the 5.x upgrade.
import warnings  # noqa: E402

warnings.filterwarnings("error", category=DeprecationWarning, module="django")

# Your stuff...
# ------------------------------------------------------------------------------
