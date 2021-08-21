from .production import *  # noqa
from .production import env

INSTALLED_APPS += ["bandit", "django_middleware_global_request"]

MIDDLEWARE += ["django_middleware_global_request.middleware.GlobalRequestMiddleware"]
CURRENT_URL = "https://venturafranklin.pythonanywhere.com"
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
