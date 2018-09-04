# Generated by Django 2.0.3 on 2018-06-15 18:31
import datetime
import warnings
from django.db import models
from django.core.management import BaseCommand
from django.utils import timezone
from core.models import TODAY_END
from users.models import User, UserRoleChange, UserStatusChange


class Command(BaseCommand):
    # Show this when the user types help
    help = "Clear duplicate status for members"

    # A command must define handle()
    def handle(self, *args, **options):
        dup_status = User.objects.filter(
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END)\
                .annotate(models.Count('id'))\
                .order_by()\
                .filter(id__count__gt=1)
        for user in dup_status:
            active_status = user.status.get(status='active')
            other_statuss = user.status.filter(~models.Q(status='active'),
                                           start__lte=TODAY_END,
                                           end__gte=TODAY_END
                                           )
            for other_status in other_statuss:
                if other_status.status == 'Colony':
                    other_status.delete()
                    continue
                other_status.end = active_status.start - datetime.timedelta(days=1)
                other_status.save()
