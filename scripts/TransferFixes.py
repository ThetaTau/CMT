from forms.models import StatusChange
from django.db.models import Q


def run():
    statuses = StatusChange.objects.filter(~Q(reason="transfer"))
    for status in statuses:
        status.new_school = None
        status.save_only()
