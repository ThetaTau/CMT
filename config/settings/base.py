"""
Base settings to build other settings files upon.
"""

import warnings
from pathlib import Path

import environ
import rollbar
from google.oauth2 import service_account

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# thetataucmt/
APPS_DIR = ROOT_DIR / "thetatauCMT"
env = environ.Env()
ENV = "base"

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(ROOT_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
BYPASS_CAPTCHA = env.bool("BYPASS_CAPTCHA", False)
# RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY")
# RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY")
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
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(ROOT_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://postgres:test@localhost:5432/thetatauCMT"),
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
    "django.contrib.humanize",  # Handy template tags
    "dal",
    "dal_select2",
    # core.apps.GuardedViewflowFrontendConfig subclasses viewflow.frontend's
    # AppConfig (same name/label) to swap in queue/inbox/archive list views that
    # tolerate stale task rows (#952) -- see core/flows.py GuardedFrontendViewSet.
    "core.apps.GuardedViewflowFrontendConfig",
    "oauth2_provider",
    "corsheaders",
    "django.contrib.admin",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "address",
    "django_tables2",
    "django_filters",
    "django_bootstrap5",
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
    # core.material_admin.SecureMaterialAdminConfig subclasses material.admin's
    # AppConfig (same name/label) so the admin frontend module mounts at
    # settings.ADMIN_URL instead of the hard-coded /admin/.
    "core.material_admin.SecureMaterialAdminConfig",
    "import_export",
    "dbbackup",
    "watson",
    "django_ckeditor_5",
    "django_recaptcha",
    "report_builder",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "allauth_2fa",
    "hcaptcha",
    "termsandconditions",
    "bootstrapform",  # used by django-survey-and-report
    "survey",  # This is django-survey-and-report
    "simple_history",
    "django_userforeignkey",
]

LOCAL_APPS = [
    "thetatauCMT.users.apps.UsersConfig",
    "thetatauCMT.chapters.apps.ChaptersConfig",
    "thetatauCMT.jobs.apps.JobsConfig",
    "thetatauCMT.events.apps.EventsConfig",
    "thetatauCMT.regions.apps.RegionsConfig",
    "thetatauCMT.scores.apps.ScoresConfig",
    "thetatauCMT.submissions.apps.SubmissionsConfig",
    "thetatauCMT.forms.apps.FormsConfig",
    "thetatauCMT.tasks.apps.TasksConfig",
    "thetatauCMT.finances.apps.FinancesConfig",
    "thetatauCMT.ballots.apps.BallotsConfig",
    "thetatauCMT.surveys.apps.SurveysConfig",
    "thetatauCMT.announcements.apps.AnnouncementsConfig",
    "thetatauCMT.notes.apps.NotesConfig",
    "thetatauCMT.objectives.apps.ObjectivesConfig",
    "thetatauCMT.trainings.apps.TrainingsConfig",
    "thetatauCMT.configs.apps.ConfigsConfig",
    "thetatauCMT.contact_sync.apps.ContactSyncConfig",
    "thetatauCMT.attendance.apps.AttendanceConfig",
    "thetatauCMT.nominations.apps.NominationsConfig",
    "thetatauCMT.awards.apps.AwardsConfig",
    "thetatauCMT.email_tracking.apps.EmailTrackingConfig",
    "thetatauCMT.guides.apps.GuidesConfig",
    # Added after any apps which contain models for which to create signals
    "email_signals",
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
    "oauth2_provider.backends.OAuth2Backend",
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
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
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
    "django_otp.middleware.OTPMiddleware",
    "allauth_2fa.middleware.AllauthTwoFactorMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.common.BrokenLinkEmailsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "watson.middleware.SearchContextMiddleware",
    "core.middleware.OfficerMiddleware",
    "core.middleware.RMPSignMiddleware",
    "termsandconditions.middleware.TermsAndConditionsRedirectMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django_userforeignkey.middleware.UserForeignKeyMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "core.middleware.RequireSuperuser2FAMiddleware",
    "rollbar.contrib.django.middleware.RollbarNotifierMiddleware",  # Last
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://\w+\.thetatau\.org$",  # Should allow ed.thetatau.org
    r"^https://\w+\.\w+\.thetatau\.org$",  # Should allow studio.ed.thetatau.org
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

# FORM RENDERER
# ------------------------------------------------------------------------------
# TemplatesSetting-based renderer so overrides in TEMPLATES.DIRS win over app
# template dirs (needed to override django_recaptcha/includes/js_v3.html).
# https://docs.djangoproject.com/en/4.2/ref/settings/#form-renderer
FORM_RENDERER = "core.renderers.DivTemplatesSetting"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
import django as _django  # noqa: E402

_DJANGO_FORMS_TEMPLATES = str(Path(_django.__file__).parent / "forms" / "templates")
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        # Project templates first (so overrides win); Django's built-in forms
        # templates last so TemplatesSetting form renderer can locate them
        # without needing django.forms in INSTALLED_APPS (which would clash
        # with the local `forms` app label).
        "DIRS": [str(APPS_DIR / "templates"), _DJANGO_FORMS_TEMPLATES],
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
                "thetatauCMT.utils.context_processors.feature_flags",
                "thetatauCMT.utils.context_processors.incident_report",
                "thetatauCMT.guides.context_processors.whats_new",
            ],
        },
    }
]
# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# https://django-tables2.readthedocs.io/en/latest/pages/custom-rendering.html#available-templates
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
# Report Builder requires false, https://gitlab.com/burke-software/django-report-builder/-/issues/286
CSRF_COOKIE_HTTPONLY = False
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
DEFAULT_FROM_EMAIL = "cmt@thetatau.org"
DJANGO_EMAIL_LIVE = env.bool("DJANGO_EMAIL_LIVE", True)
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.filebased.EmailBackend",
)
EMAIL_FILE_PATH = str(ROOT_DIR / "email_tests")
EMAIL_TIMEOUT = 5
# Email open/click tracking (Mailjet native, surfaced via django-anymail).
# These toggle Mailjet's TrackOpens / TrackClicks on every outgoing message.
EMAIL_TRACK_OPENS = env.bool("EMAIL_TRACK_OPENS", default=True)
EMAIL_TRACK_CLICKS = env.bool("EMAIL_TRACK_CLICKS", default=True)
# MailerLite API token (used by another part of the org). When set, the member
# email-communication page also pulls each member's MailerLite subscriber
# activity. https://developers.mailerlite.com/api/subscribers
MAILERLITE_API_KEY = env("MAILERLITE_API_KEY", default="")
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
    "formatters": {"verbose": {"format": "%(levelname)s %(asctime)s %(module)s " "%(process)d %(thread)d %(message)s"}},
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "survey": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}


# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", False)
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_LOGIN_METHODS = {"email"}
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_ADAPTER = "thetatauCMT.users.adapters.AccountAdapter"
# https://django-allauth.readthedocs.io/en/latest/configuration.html
SOCIALACCOUNT_ADAPTER = "thetatauCMT.users.adapters.SocialAccountAdapter"

OAUTH2_PROVIDER = {
    "OIDC_ENABLED": True,
    "OAUTH2_VALIDATOR_CLASS": "core.auth.CustomOAuth2Validator",
    "SCOPES": {
        "openid": "OpenID Connect scope",
    },
}

# Your stuff...
# ------------------------------------------------------------------------------
ROLLBAR = {
    "access_token": env("ROLLBAR_ACCESS", default=""),
    "environment": "development" if DEBUG else "production",
    "root": str(ROOT_DIR),
    "branch": "master",
    "capture_username": True,
    "capture_email": True,
}

rollbar.init(**ROLLBAR)

# Executive Director — username / email used to assign viewflow review tasks
# (premature alumnus, disciplinary process, resignation, H&S education, etc.)
# and as the fallback recipient for chapter-officer notifications that need to
# reach a live person at the Central Office. Overridable via the
# ``EXECUTIVE_DIRECTOR`` env var so a new ED can be swapped in without a code
# change. Value must equal ``User.username`` for the ED account.
EXECUTIVE_DIRECTOR = env("EXECUTIVE_DIRECTOR", default="Jim.Gaffney@thetatau.org")

GOOGLE_API_KEY = env("GOOGLE_API_KEY", default="TESTING")
if GOOGLE_API_KEY == "TESTING":
    # Try and load from secrets file
    try:
        with open(str(ROOT_DIR / "secrets" / "GOOGLE_API_KEY")) as key_file:
            GOOGLE_API_KEY = key_file.read()
    except FileNotFoundError:
        warnings.warn("GOOGLE_API_KEY is not set in environment or secrets folder!")

FILE_STORAGE_TO_USE = "django.core.files.storage.FileSystemStorage"
try:
    GOOGLE_APPLICATION_CREDENTIALS = env(
        "GOOGLE_APPLICATION_CREDENTIALS",
        default=r"secrets\chaptermanagementtool-e11151065a69.json",
    )
    GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
        str(ROOT_DIR / "secrets" / "chaptermanagementtool-e11151065a69.json")
    )
except FileNotFoundError:
    warnings.warn("Google credentials not found! Missing secrets/chaptermanagementtool-e11151065a69.json")
else:
    # GoogleCloudStorage LINK https://console.cloud.google.com/storage/browser/theta-tau?authuser=3&folder=true&organizationId=true&project=chaptermanagementtool
    FILE_STORAGE_TO_USE = "storages.backends.gcloud.GoogleCloudStorage"
    GS_BUCKET_NAME = "theta-tau"
    GS_DEFAULT_ACL = "publicRead"

SOCIALACCOUNT_QUERY_EMAIL = True
# https://console.developers.google.com/apis/credentials?project=chaptermanagementtool&authuser=2
# https://developers.facebook.com/apps/1896435477053569/dashboard/

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
    },
}

# ------------------------------------------------------------------------------
# Contact-sync (region officer → Google / Microsoft Contacts).
# ------------------------------------------------------------------------------
# See docs/contact_sync_setup.md for step-by-step configuration.
# Values default to empty strings so the feature "gracefully unavailable" —
# each provider is only offered in the UI when both a client_id and a
# client_secret are configured. The vCard-download path always works and does
# not require any OAuth configuration.
CONTACT_SYNC_GOOGLE_CLIENT_ID = env("CONTACT_SYNC_GOOGLE_CLIENT_ID", default="")
CONTACT_SYNC_GOOGLE_CLIENT_SECRET = env("CONTACT_SYNC_GOOGLE_CLIENT_SECRET", default="")
CONTACT_SYNC_MICROSOFT_CLIENT_ID = env("CONTACT_SYNC_MICROSOFT_CLIENT_ID", default="")
CONTACT_SYNC_MICROSOFT_CLIENT_SECRET = env("CONTACT_SYNC_MICROSOFT_CLIENT_SECRET", default="")
# Microsoft tenant: 'common' (personal+work), 'organizations' (work only),
# 'consumers' (personal only), or a specific tenant GUID / verified domain.
CONTACT_SYNC_MICROSOFT_TENANT = env("CONTACT_SYNC_MICROSOFT_TENANT", default="common")

IMPORT_EXPORT_USE_TRANSACTIONS = True

DBBACKUP_LOCAL = env.bool("DBBACKUP_LOCAL", default=True)
DBBACKUP_GPG_RECIPIENT = "Frank.Ventura@thetatau.org"
DBBACKUP_CONNECTORS = {
    "default": {
        "CONNECTOR": "dbbackup.db.postgresql.PgDumpBinaryConnector",
        # Sometimes this is needed for restore on local dev machine
        # "SINGLE_TRANSACTION": False,
    }
}
if DBBACKUP_LOCAL:
    DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
    DBBACKUP_STORAGE_LOCATION = env("DBBACKUP_STORAGE_LOCATION", default="database_backups")
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

CKEDITOR_5_ALLOW_ALL_FILE_TYPES = True
CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": {
            "items": [
                "heading",
                "|",
                "bold",
                "italic",
                "link",
                "bulletedList",
                "numberedList",
                "blockQuote",
                "imageUpload",
                "fileUpload",
            ],
        }
    },
    "extends": {
        "blockToolbar": [
            "paragraph",
            "heading1",
            "heading2",
            "heading3",
            "|",
            "bulletedList",
            "numberedList",
            "|",
            "blockQuote",
        ],
        "toolbar": {
            "items": [
                "heading",
                "|",
                "outdent",
                "indent",
                "|",
                "bold",
                "italic",
                "link",
                "underline",
                "strikethrough",
                "code",
                "subscript",
                "superscript",
                "highlight",
                "|",
                "codeBlock",
                "sourceEditing",
                "insertImage",
                "bulletedList",
                "numberedList",
                "todoList",
                "|",
                "blockQuote",
                "imageUpload",
                "|",
                "fontSize",
                "fontFamily",
                "fontColor",
                "fontBackgroundColor",
                "mediaEmbed",
                "removeFormat",
                "insertTable",
            ],
            "shouldNotGroupWhenFull": "true",
        },
        "image": {
            "toolbar": [
                "imageTextAlternative",
                "|",
                "imageStyle:alignLeft",
                "imageStyle:alignRight",
                "imageStyle:alignCenter",
                "imageStyle:side",
                "|",
            ],
            "styles": [
                "full",
                "side",
                "alignLeft",
                "alignRight",
                "alignCenter",
            ],
        },
        "table": {
            "contentToolbar": [
                "tableColumn",
                "tableRow",
                "mergeTableCells",
                "tableProperties",
                "tableCellProperties",
            ],
        },
        "heading": {
            "options": [
                {
                    "model": "paragraph",
                    "title": "Paragraph",
                    "class": "ck-heading_paragraph",
                },
                {
                    "model": "heading1",
                    "view": "h1",
                    "title": "Heading 1",
                    "class": "ck-heading_heading1",
                },
                {
                    "model": "heading2",
                    "view": "h2",
                    "title": "Heading 2",
                    "class": "ck-heading_heading2",
                },
                {
                    "model": "heading3",
                    "view": "h3",
                    "title": "Heading 3",
                    "class": "ck-heading_heading3",
                },
            ]
        },
    },
    "list": {
        "properties": {
            "styles": "true",
            "startIndex": "true",
            "reversed": "true",
        }
    },
}

# Define a constant in settings.py to specify file upload permissions
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "authenticated"  # Possible values: "staff", "authenticated", "any"

RECAPTCHA_REQUIRED_SCORE = 0.69

MOOSEND_API_KEY = env("MOOSEND_API_KEY", default=None)

METABASE_SECRET_KEY = env("METABASE_SECRET_KEY", default=None)

# These will be excluded for the terms accept and the officer/RMP middleware
TERMS_EXCLUDE_URL_LIST = {
    "/terms/required/",
    "/accounts/logout/",
    "/rmp/",
    "/forms/rmp/",
    "/electronic_terms/",
    "/forms/pledgeprogram/",
    "/forms/report/",
}

# How long a released feature stays "new" -- it is listed in the What's New feed
# and badged in the catalog for this many days after its released_at date.
NEW_FEATURE_MAX_AGE_DAYS = env.int("NEW_FEATURE_MAX_AGE_DAYS", default=30)

# The unprompted What's New modal never shows more than this many items; the
# rest are one click away on the archive page.
WHATS_NEW_MAX_ITEMS = env.int("WHATS_NEW_MAX_ITEMS", default=5)

CSV_DIRECTORY = Path("csv")  # Define the directory where csv are exported
TEX_DIRECTORY = Path("tex")  # Define the directory where tex files and pdf are exported

LMS_ID = env("LMS_ID", default=None)
LMS_SECRET = env("LMS_SECRET", default=None)

ED_ID = env("ED_ID", default=None)
ED_SECRET = env("ED_SECRET", default=None)
# Base URL of the Open edX (Tutor) instance and the course run(s) every user
# should be enrolled in. Override per-environment via env vars if needed.
ED_HOST = env("ED_HOST", default="https://ed.thetatau.org")
ED_COURSES = env.list("ED_COURSES", default=["course-v1:ThetaTau+TT101+intro"])

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_SIGNAL_DEFAULT_SENDER = DEFAULT_FROM_EMAIL

# EVENTS
# ------------------------------------------------------------------------------
# When a National Officer creates a public event, should it be auto-approved
# (cross-chapter visible immediately) instead of entering the pending queue?
# Configurable per-environment; defaults to auto-approved.
EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC = env.bool("EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC", default=True)

# ATTENDANCE
# ------------------------------------------------------------------------------
# Quorum rule used by the attendance module. Configurable per-environment.
#   "majority"  -> floor(active/2) + 1  (default)
#   "two_thirds" -> ceil(active * 2/3)
#   a float 0<x<=1 -> ceil(active * x)
ATTENDANCE_QUORUM_RULE = env("ATTENDANCE_QUORUM_RULE", default="majority")
# Minimum query length for the privacy-safe cross-chapter guest autocomplete.
ATTENDANCE_GUEST_SEARCH_MIN_LENGTH = env.int("ATTENDANCE_GUEST_SEARCH_MIN_LENGTH", default=2)
# Maximum results returned by the guest autocomplete (never a full roster).
ATTENDANCE_GUEST_SEARCH_MAX_RESULTS = env.int("ATTENDANCE_GUEST_SEARCH_MAX_RESULTS", default=20)
# Minimum confidence (0..1) at which a national-event attendance upload row is
# auto-matched to a member; anything at or below routes to the manual match
# queue (WI-7). Match is auto-accepted only when strictly greater than this.
ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD = env.float("ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD", default=0.60)

# AWARDS
# ------------------------------------------------------------------------------
# Whether revoked awards are shown (in a separate section) on public profiles.
AWARDS_SHOW_REVOKED = env.bool("AWARDS_SHOW_REVOKED", default=False)

# https://django-simple-history.readthedocs.io/en/latest/historical_model.html#filefield-as-a-charfield
SIMPLE_HISTORY_FILEFIELD_TO_CHARFIELD = True
