from django.apps import AppConfig
from material.frontend.apps import ModuleMixin


class FormsConfig(ModuleMixin, AppConfig):
    name = "thetatauCMT.forms"

    def index_url(self):
        return "/"
