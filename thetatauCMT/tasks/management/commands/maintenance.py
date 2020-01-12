import os
import logging
from django.conf import settings
from django.core.management import BaseCommand


logger = logging.getLogger(__name__)
MAINTENANCE_FILE = settings.ROOT_DIR + 'maintenance_active'


# The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Set site in maintenance mode"

    def add_arguments(self, parser):
        parser.add_argument('on', action='store_true')
        parser.add_argument('off', action='store_true')

    # A command must define handle()
    def handle(self, *args, **options):
        on = options.get('on', False)
        off = options.get('off', True)
        logger.info(f'Maintenance mode will be turned on: {on}; off: {off}')
        if on:
            'create a file that will mean maintenance mode is active'
            open(MAINTENANCE_FILE, 'w').close()
            logger.info('Maintenance mode started')
        if off:
            'remove maintenance mode file'
            if os.path.isfile(MAINTENANCE_FILE):
                os.remove(MAINTENANCE_FILE)
                logger.info('Maintenance mode stop')
