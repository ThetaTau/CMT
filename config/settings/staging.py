from .production import *  # noqa
from .production import env

INSTALLED_APPS += ["bandit", "django_middleware_global_request"]

MIDDLEWARE += ["django_middleware_global_request.middleware.GlobalRequestMiddleware"]
CURRENT_URL = "https://venturafranklin.pythonanywhere.com"

# PERFORMANCE PROFILING (staging-only)
# ------------------------------------------------------------------------------
# django-silk request/SQL profiler + a lightweight timing middleware that stamps
# every response with X-Perf-* headers. QueryTimingMiddleware is outermost so it
# measures the full stack (silk included); silk records SQL + cProfile detail at
# /silk/ (restricted to superusers below). CACHES (LocMemCache) is inherited from
# production.py.
INSTALLED_APPS += ["silk"]
MIDDLEWARE = [
    "core.middleware.QueryTimingMiddleware",
    "silk.middleware.SilkyMiddleware",
] + MIDDLEWARE


def _silk_superuser_only(user):
    return user.is_superuser


SILKY_AUTHENTICATION = True  # must be logged in to view /silk/
SILKY_AUTHORISATION = True  # ...and pass SILKY_PERMISSIONS
SILKY_PERMISSIONS = _silk_superuser_only
SILKY_PYTHON_PROFILER = True
SILKY_INTERCEPT_PERCENT = 100
SILKY_MAX_RECORDED_REQUESTS = 10**4
SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10

# HOST / HTTPS overrides for the shared *.pythonanywhere.com staging host.
# ------------------------------------------------------------------------------
# Production defaults ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS to the cmt.thetatau.*
# domains, which would reject the staging host — point them at the staging host
# here (still overridable via the same DJANGO_* env vars on PythonAnywhere).
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["venturafranklin.pythonanywhere.com"])
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=["https://venturafranklin.pythonanywhere.com"],
)
# Never assert HSTS preload / includeSubDomains from a shared subdomain we do not
# control; pythonanywhere.com already enforces HTTPS for its subdomains. Keep the
# inherited SSL redirect but disable HSTS pinning on staging.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

if DJANGO_EMAIL_LIVE:
    EMAIL_BACKEND = "core.email.MyHijackBackend"

BANDIT_EMAIL = [
    "cmt@thetatau.org",
]

ACCOUNT_EMAIL_VERIFICATION = "none"
RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY")
RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY")

# dj_anonymizer DO NOT ADD TO PRODUCTION
# ------------------------------------------------------------------------------
# https://dj-anonymizer.readthedocs.io
INSTALLED_APPS = ["dj_anonymizer"] + INSTALLED_APPS  # noqa F405
