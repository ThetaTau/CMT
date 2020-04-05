from .production import *  # noqa
from .production import env

INSTALLED_APPS += ['bandit', 'django_middleware_global_request']

MIDDLEWARE += ['django_middleware_global_request.middleware.GlobalRequestMiddleware']
CURRENT_URL = 'https://venturafranklin.pythonanywhere.com'
EMAIL_BACKEND = 'core.email.MyHijackBackend'

BANDIT_EMAIL = ['cmt@thetatau.org', ]
