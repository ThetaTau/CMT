import datetime
from forms.models import StatusChange
from users.models import UserStatusChange
from core.models import TODAY


def run():
    """
    python manage.py runscript away_fixes
    """
    aways = StatusChange.objects.filter(
        reason__in=["coop", "covid", "military"], date_end__gt=TODAY
    )
    total = aways.count()
    for count, away in enumerate(aways):
        user = away.user
        print(f"{count + 1}/{total} for user: {user}")
        statuss = user.status.filter(end__gt=TODAY)
        print(f"    status found: {statuss}")
        set_away = False
        for status in statuss:
            if status.status in ["active", "activepend"]:
                # Need to set not current
                status.end = away.date_start - datetime.timedelta(days=1)
                status.save()
            if status.status == "away":
                # Need to set current
                status.end = away.date_end
                status.save()
                set_away = True
        if not set_away:
            UserStatusChange(
                user=user, status="away", start=away.date_start, end=away.date_end,
            ).save()
