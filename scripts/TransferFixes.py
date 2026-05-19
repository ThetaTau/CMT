from django.db.models import Q

from thetatauCMT.forms.models import StatusChange


def run():
    statuses = StatusChange.objects.filter(~Q(reason="transfer"))
    for status in statuses:
        status.new_school = None
        status.save_only()
