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
        return
        from users.models import User, UserStatusChange
        from django.db import models
        from core.models import TODAY_END, forever
        users = User.objects.filter(
            status__status='active',
            status__end__lte=TODAY_END) \
            .annotate(models.Count('status')) \
            .order_by() \
            .filter(status__count=1)
        User.objects.filter(
            status__start_lte=TODAY_END,
            status__end__lte=TODAY_END) \
            .annotate(models.Count('status')) \
            .order_by() \
            .filter(status__count=1)
        # Only have one status, and it is not current, need to fix
        users = User.objects.all() \
            .annotate(models.Count('status')) \
            .order_by() \
            .filter(status__count=1) \
            .filter(
            status__end__lte=TODAY_END)
        for user in users:
            user_status = user.status.get()
            user_status.end = forever()
            user_status.save()

        # Those with no status, need to create active/pnm/alumni status
        # Fix by hand
        # users = User.objects.all()\
        #                .annotate(models.Count('status'))\
        #                .order_by()\
        #                .filter(status__count=0)
        # Edward Monteverde users.UserStatusChange.None      Alumni
        # Tina Demaio users.UserStatusChange.None            Depledge
        # Kirsten Eichelberger users.UserStatusChange.None   Alumni
        # Tyler Daly users.UserStatusChange.None             Alumni

        # Users with no current status
        users = User.objects.exclude(
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END)
        alumnis = users.filter(status__status='alumni')
        for alumni in alumnis:
            user_status = alumni.status.get()
            user_status.start = datetime.datetime.now() - datetime.timedelta(days=1)
            user_status.save()
        actives = users.filter(status__status='active')
        for user in actives:
            user_status = user.status.get(status='active')
            user_status.end = forever()
            user_status.save()
        users = User.objects.exclude(
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END)
        # Somehow missed these, need to alumnize
        alumnis = users.filter(status__status='activepend')
        for alumni in alumnis:
            UserStatusChange(
                user=alumni,
                status='alumni',
                start=datetime.datetime.now() - datetime.timedelta(days=1),
                end=forever()
            ).save()
        users = User.objects.exclude(
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END)
        # The final group should be test group
        for user in users:
            UserStatusChange(
                user=user,
                status='active',
                start=datetime.datetime.now() - datetime.timedelta(days=1),
                end=forever()
            ).save()
        # This cleared duplicate status
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
