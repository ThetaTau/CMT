from django.conf import settings
from requests import *  # noqa: F403

import core.stubs.requests as stub


def is_running_local_env():
    return settings.ENV == "local"


get = stub.get if is_running_local_env() else get  # noqa: F405
post = stub.post if is_running_local_env() else post  # noqa: F405
