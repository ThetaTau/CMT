from django.core.management.base import BaseCommand

from os import system

class Command(BaseCommand):
    help = "Seed the database with essential items"

    SEED_MODELS = [
        { "app": "scores",      "file": "scoretypes"                },
        { "app": "tasks",       "file": "tasks"                     },
        { "app": "forms",       "file": "badges"                    },
        { "app": "chapters",    "file": "chapters"                  },
        { "app": "users",       "file": "groups"                    }
    ]

    def handle(self, *args, **kwargs):
        for model in Command.SEED_MODELS: self._seed_data(model)
        self._manage_cmd("task_dates")
    
    def _seed_data(self, model):
        self._load_data(self._data_load_path(model))

    def _data_load_path(self, model):
        return f"thetatauCMT/{model['app']}/fixtures/{model['file']}.json"
    
    def _load_data(self, *args):
        all_args = ("loaddata",) + args + ("--verbosity", "3")
        self._manage_cmd(*all_args)

    def _manage_cmd(self, *args):
        args_list = ' '.join([ str(arg) for arg in args if arg ])
        system(f"python manage.py {args_list}")
