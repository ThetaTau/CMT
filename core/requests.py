import core.dummies.requests as dummy
from django.conf import settings
from requests import *

def is_running_local_env():
    return settings.ENV == "local"

get = dummy.get if is_running_local_env() else get
post = dummy.post if is_running_local_env() else post
