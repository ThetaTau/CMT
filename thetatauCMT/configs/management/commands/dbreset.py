from django.core.management.base import BaseCommand

from os import system


class Command(BaseCommand):
    help = "Clear the database and reload with base information and new superuser"

    RESET_COMMANDS = ["flush", "migrate", "collectstatic", "createsuperuser", "dbseed"]

    def handle(self, *args, **kwargs):
        for cmd in Command.RESET_COMMANDS:
            self._manage_cmd(cmd)

    def _manage_cmd(self, *args):
        args_list = " ".join([str(arg) for arg in args])
        system(f"python manage.py {args_list}")
