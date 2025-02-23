from django.core.management.base import BaseCommand

from os import system

class Command(BaseCommand):
    help = "Seed the database with essential items"

    SEED_MODELS = {
        "scores.scoretype": { "app": "scores", "file": "scoretypes" },
        "tasks.task tasks.taskdate": { "app": "tasks", "file": "tasks" },
        "forms.badge": { "app": "forms", "file": "badges" },
        "chapters.chapter chapters.chaptercurricula": { "app": "chapters", "file": "chapters" },
        "auth.group": { "app": "users", "file": "groups", "natural": True }
    }

    def handle(self, *args, **kwargs):
        for name in Command.SEED_MODELS:
            self._seed_data(name, Command.SEED_MODELS[name])
    
    def _seed_data(self, model_name, model):
        natural_key = "--natural-foreign" if "natural" in model.keys() else ""
        self._load_data(natural_key, model_name, self._data_load_path(model))

    def _data_load_path(self, model):
        return f"thetatauCMT/{model["app"]}/fixtures/{model["file"]}.json"
    
    def _load_data(self, *args):
        self._manage_cmd("loaddata", args + ["--verbosity", "3"])

    def _manage_cmd(self, *args):
        args_list = ' '.join([ str(arg) for arg in args ])
        system(f"python manage.py {args_list}")
