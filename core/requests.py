import core.stubs.requests as stub
from django.conf import settings
from requests import *

def is_running_local_env():
    return settings.ENV == "local"

get = stub.get if is_running_local_env() else get
post = stub.post if is_running_local_env() else post
