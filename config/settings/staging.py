from .production import *  # noqa
from .production import env

INSTALLED_APPS += ["bandit", "django_middleware_global_request"]

MIDDLEWARE += ["django_middleware_global_request.middleware.GlobalRequestMiddleware"]
CURRENT_URL = "https://venturafranklin.pythonanywhere.com"

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
