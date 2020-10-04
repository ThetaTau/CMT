"""
Base settings to build other settings files upon.
"""
from pathlib import Path

import environ
import warnings

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# thetataucmt/
APPS_DIR = ROOT_DIR / "thetatauCMT"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(ROOT_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "America/Phoenix"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(ROOT_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://postgres:test@localhost:5432/thetatauCMT"
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 'django.contrib.humanize', # Handy template tags
    "dal",
    "dal_select2",
    "viewflow.frontend",
    "django.contrib.admin",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.linkedin_oauth2",
    "allauth.socialaccount.providers.facebook",
    "rest_framework",
    "address",
    "django_tables2",
    "django_filters",
    "bootstrap4",
    "django_extensions",  # https://github.com/pydanny/cookiecutter-django/issues/417
    "herald",
    "multiselectfield",
    "tempus_dominus",
    "easy_pdf",
    "djmoney",
    "betterforms",
    "viewflow",
    "material",
    "material.frontend",
    "material.admin",
    "import_export",
    "dbbackup",
    "watson",
    "ckeditor",
    "ckeditor_uploader",
    "captcha",
]

LOCAL_APPS = [
    "thetatauCMT.users.apps.UsersConfig",
    "thetatauCMT.chapters.apps.ChaptersConfig",
    "thetatauCMT.events.apps.EventsConfig",
    "thetatauCMT.regions.apps.RegionsConfig",
    "thetatauCMT.scores.apps.ScoresConfig",
    "thetatauCMT.submissions.apps.SubmissionsConfig",
    "thetatauCMT.forms.apps.FormsConfig",
    "thetatauCMT.tasks.apps.TasksConfig",
    "thetatauCMT.finances.apps.FinancesConfig",
    "thetatauCMT.ballots.apps.BallotsConfig",
    "thetatauCMT.announcements.apps.AnnouncementsConfig",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "thetatauCMT.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.common.BrokenLinkEmailsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "watson.middleware.SearchContextMiddleware",
    "core.middleware.OfficerMiddleware",
    "core.middleware.RMPSignMiddleware",
    "rollbar.contrib.django.middleware.RollbarNotifierMiddleware",  # Last
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(ROOT_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        "DIRS": [str(APPS_DIR / "templates")],
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-loaders
            # https://docs.djangoproject.com/en/dev/ref/templates/api/#loader-types
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "thetatauCMT.utils.context_processors.settings_context",
            ],
        },
    }
]
# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap4"

# https://django-tables2.readthedocs.io/en/latest/pages/custom-rendering.html#available-templates
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-browser-xss-filter
SECURE_BROWSER_XSS_FILTER = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
DEFAULT_FROM_EMAIL = "cmt@thetatau.org"
DJANGO_EMAIL_LIVE = env.bool("DJANGO_EMAIL_LIVE", True)
if DJANGO_EMAIL_LIVE:
    EMAIL_BACKEND = env(
        "DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
    )
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = str(ROOT_DIR / "email_tests")
EMAIL_TIMEOUT = 5
# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [
    ("""Theta Tau""", "cmt@thetatau.org"),
]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s "
            "%(process)d %(thread)d %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", False)
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_AUTHENTICATION_METHOD = "email"
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_EMAIL_REQUIRED = True
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_ADAPTER = "users.adapters.AccountAdapter"
# https://django-allauth.readthedocs.io/en/latest/configuration.html
SOCIALACCOUNT_ADAPTER = "users.adapters.SocialAccountAdapter"


# Your stuff...
# ------------------------------------------------------------------------------
ROLLBAR = {
    "access_token": env("ROLLBAR_ACCESS", default=""),
    "environment": "development" if DEBUG else "production",
    "root": str(ROOT_DIR),
    "branch": "master",
    "capture_username": True,
}
import rollbar

rollbar.init(**ROLLBAR)
GOOGLE_API_KEY = env("GOOGLE_API_KEY", default="TESTING")
if GOOGLE_API_KEY == "TESTING":
    # Try and load from secrets file
    try:
        with open(str(ROOT_DIR / "secrets" / "GOOGLE_API_KEY")) as key_file:
            GOOGLE_API_KEY = key_file.read()
    except FileNotFoundError:
        warnings.warn("GOOGLE_API_KEY is not set in environment or secrets folder!")
GOOGLE_APPLICATION_CREDENTIALS = env(
    "GOOGLE_APPLICATION_CREDENTIALS",
    default="secrets\chaptermanagementtool-e11151065a69.json",
)
# GoogleCloudStorage LINK https://console.cloud.google.com/storage/browser/theta-tau?authuser=3&folder=true&organizationId=true&project=chaptermanagementtool
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
GS_BUCKET_NAME = "theta-tau"
from google.oauth2 import service_account

GS_DEFAULT_ACL = "publicRead"

GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    str(ROOT_DIR / "secrets" / "chaptermanagementtool-e11151065a69.json")
)

SOCIALACCOUNT_QUERY_EMAIL = True
# https://console.developers.google.com/apis/credentials?project=chaptermanagementtool&authuser=2
# https://www.linkedin.com/developer/apps/5538166/auth
# https://developers.facebook.com/apps/1896435477053569/dashboard/

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email",],
        "AUTH_PARAMS": {"access_type": "online",},
    },
    "linkedin": {
        "SCOPE": ["r_basicprofile", "r_emailaddress",],
        "PROFILE_FIELDS": [
            "id",
            "first-name",
            "last-name",
            "email-address",
            "picture-url",
            "public-profile-url",
        ],
    },
    "facebook": {
        "METHOD": "oauth2",
        "SCOPE": ["email"],
        "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        "INIT_PARAMS": {"cookie": True},
        "FIELDS": [
            "id",
            "email",
            "name",
            "first_name",
            "last_name",
            "verified",
            "locale",
            "timezone",
            "link",
            "updated_time",
        ],
        "EXCHANGE_TOKEN": True,
        "LOCALE_FUNC": lambda request: "en_US",
        "VERIFIED_EMAIL": False,
        "VERSION": "v2.12",
    },
}

IMPORT_EXPORT_USE_TRANSACTIONS = True

DBBACKUP_LOCAL = env.bool("DBBACKUP_LOCAL", default=True)
DBBACKUP_GPG_RECIPIENT = "Frank.Ventura@thetatau.org"
if DBBACKUP_LOCAL:
    DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
    DBBACKUP_STORAGE_LOCATION = env(
        "DBBACKUP_STORAGE_LOCATION", default="database_backups"
    )
    DBBACKUP_STORAGE_OPTIONS = {"location": DBBACKUP_STORAGE_LOCATION}
    DBBACKUP_CLEANUP_KEEP = 2
else:
    DBBACKUP_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
    # 1.1 Mbps is the minimum required to upload 8 MB within the 60 second timeout
    GS_BLOB_CHUNK_SIZE = 5 * 1024 * 1024  # Set 5 MB blob size
    DBBACKUP_STORAGE_OPTIONS = dict(
        credentials=GS_CREDENTIALS,
        bucket_name="theta-tau-database",
        max_memory_size=100 * 1024 * 1024,  # Set 100 MB blob size,
    )

USE_DJANGO_JQUERY = False
JQUERY_URL = False

# Django Plotly Dash
# -------------------------------------
INSTALLED_APPS += ["django_plotly_dash.apps.DjangoPlotlyDashConfig"]
MIDDLEWARE += ["django_plotly_dash.middleware.BaseMiddleware"]

PLOTLY_COMPONENTS = [
    "dash_core_components",
    "dash_html_components",
    "dash_renderer",
    "dpd_components",
]

CKEDITOR_UPLOAD_PATH = "uploads/"
RECAPTCHA_REQUIRED_SCORE = 0.85
SILENCED_SYSTEM_CHECKS = ["captcha.recaptcha_test_key_error"]
