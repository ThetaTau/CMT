from .base import *  # noqa
from .base import env

ENV = "local"

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="f8zvMcBMilBUUgIbOM8DDvqeodEcTlA0Uo3FyK81m1SUVzI5Tvv4hzw8T3CrZinK",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = [
    "localhost",
    "0.0.0.0",
    "127.0.0.1",
    # ".ngrok-free.app", # DO NOT USE THIS ON WORK PROHIBITED
]
CURRENT_URL = "http://localhost:8000"
# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    }
}

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://thetatau:test@postgres:5432/thetatauCMT",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DBBACKUP_CONNECTORS = {
    "default": {
        "CONNECTOR": "dbbackup.db.postgresql.PgDumpBinaryConnector",
        # This is needed for restore on local dev machine
        "SINGLE_TRANSACTION": False,
    }
}

if False:
    EMAIL_BACKEND = "anymail.backends.mailjet.EmailBackend"
    ANYMAIL = {
        "MAILJET_API_KEY": env("MAILJET_API_KEY"),
        "MAILJET_SECRET_KEY": env("MAILJET_SECRET_KEY"),
    }
    INSTALLED_APPS += ["anymail"]

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG  # noqa F405

# WhiteNoise
# ------------------------------------------------------------------------------
# http://whitenoise.evans.io/en/latest/django.html#using-whitenoise-in-development
INSTALLED_APPS = ["whitenoise.runserver_nostatic"] + INSTALLED_APPS  # noqa F405


# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
# INSTALLED_APPS += ["debug_toolbar"]  # noqa F405
# # https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
# MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa F405
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.templates.TemplatesPanel",
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.profiling.ProfilingPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env("USE_DOCKER", default="no") == "yes":
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

# Your stuff...
# ------------------------------------------------------------------------------

ACCOUNT_EMAIL_VERIFICATION = "none"
SILENCED_SYSTEM_CHECKS = ["captcha.recaptcha_test_key_error", "urls.W005"]

# dj_anonymizer DO NOT ADD TO PRODUCTION
# ------------------------------------------------------------------------------
# https://dj-anonymizer.readthedocs.io
INSTALLED_APPS = ["dj_anonymizer"] + INSTALLED_APPS  # noqa F405

# https://stackoverflow.com/a/62341274/3166424
SHELL_PLUS = "ipython"

SHELL_PLUS_PRINT_SQL = True

NOTEBOOK_ARGUMENTS = [
    "--ip",
    "0.0.0.0",
    "--port",
    "8888",
    "--allow-root",
    "--no-browser",
]

IPYTHON_ARGUMENTS = [
    "--ext",
    "django_extensions.management.notebook_extension",
    "--debug",
]

IPYTHON_KERNEL_DISPLAY_NAME = "Django Shell-Plus"

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
# GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE = r"E:\workspace\CMT\thetatauCMT\secrets\ChapterManagementTool-b239bceff1a7.json"
